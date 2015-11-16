"""This is the Bcfg2 support for pkg."""

import os
import Bcfg2.Options
import Bcfg2.Client.Tools


class Pkgng(Bcfg2.Client.Tools.Tool):
    """Support for pkgng packages on FreeBSD."""

    options = Bcfg2.Client.Tools.Tool.options + [
        Bcfg2.Options.PathOption(
            cf=('Pkgng', 'path'),
            default='/usr/sbin/pkg', dest='pkg_path',
            help='Pkgng tool path')]

    name = 'Pkgng'
    __execs__ = []
    __handles__ = [('Package', 'pkgng'), ('Path', 'ignore')]
    __req__ = {'Package': ['name', 'version'], 'Path': ['type']}

    def __init__(self, config):
        Bcfg2.Client.Tools.Tool.__init__(self, config)

        self.pkg = Bcfg2.Options.setup.pkg_path
        self.__execs__ = [self.pkg]

        self.pkgcmd = self.pkg + ' install -fy'
        if not Bcfg2.Options.setup.debug:
            self.pkgcmd += ' -q'
        self.pkgcmd += ' %s'

        self.ignores = [entry.get('name') for struct in config
                        for entry in struct
                        if entry.tag == 'Path' and
                        entry.get('type') == 'ignore']

        self.__important__ = self.__important__ + \
            [entry.get('name') for struct in config
             for entry in struct
             if (entry.tag == 'Path' and
                 entry.get('name').startswith('/etc/pkg/'))]
        self.nonexistent = [entry.get('name') for struct in config
                            for entry in struct
                            if entry.tag == 'Path' and
                            entry.get('type') == 'nonexistent']
        self.actions = {}
        self.pkg_cache = {}

        try:
            self._load_pkg_cache()
        except OSError:
            raise Bcfg2.Client.Tools.ToolInstantiationError

    def _load_pkg_cache(self):
        """Cache the version of all currently installed packages."""
        self.pkg_cache = {}
        output = self.cmd.run([self.pkg, 'query', '-a', '%n %v']).stdout
        for line in output.splitlines():
            parts = line.split(' ')
            name = ' '.join(parts[:-1])
            self.pkg_cache[name] = parts[-1]

    def FindExtra(self):
        """Find extra packages."""
        packages = [entry.get('name') for entry in self.getSupportedEntries()]
        extras = [(name, value) for (name, value) in self.pkg_cache.items()
                  if name not in packages]
        return [Bcfg2.Client.XML.Element('Package', name=name, type='pkgng',
                                         current_version=version)
                for (name, version) in extras]

    def VerifyChecksums(self, entry, modlist):
        """Verify the checksum of the files, owned by a package."""
        output = self.cmd.run([self.pkg, 'check', '-s',
                               entry.get('name')]).stdout.splitlines()
        files = []
        for item in output:
            if "checksum mismatch" in item:
                files.append(item.split()[-1])
            elif "No such file or directory" in item:
                continue
            else:
                self.logger.error("Got Unsupported pattern %s "
                                  "from pkg check" % item)

        files = list(set(files) - set(self.ignores))
        # We check if there is file in the checksum to do
        if files:
            # if files are found there we try to be sure our modlist is sane
            # with erroneous symlinks
            modlist = [os.path.realpath(filename) for filename in modlist]
            bad = [filename for filename in files if filename not in modlist]
            if bad:
                self.logger.debug("It is suggested that you either manage "
                                  "these files, revert the changes, or ignore "
                                  "false failures:")
                self.logger.info("Package %s failed validation. Bad files "
                                 "are:" % entry.get('name'))
                self.logger.info(bad)
                entry.set('qtext',
                          "Reinstall Package %s-%s to fix failing files? "
                          "(y/N) " % (entry.get('name'), entry.get('version')))
                return False
        return True

    def _get_candidate_versions(self, name):
        """
        Get versions of the specified package name available for
        installation from the configured remote repositories.
        """
        output = self.cmd.run([self.pkg, 'search', '-U', '-Qversion', '-q',
                               '-Sname', '-e', name]).stdout.splitlines()
        versions = []
        for line in output:
            versions.append(line)

        if len(versions) == 0:
            return None

        return sorted(versions)

    def VerifyPackage(self, entry, modlist, checksums=True):
        """Verify package for entry."""
        if 'version' not in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
                             (entry.attrib['name']))
            return False

        pkgname = entry.get('name')
        if pkgname not in self.pkg_cache:
            self.logger.info("Package %s not installed" % (entry.get('name')))
            entry.set('current_exists', 'false')
            return False

        installed_version = self.pkg_cache[pkgname]
        candidate_versions = self._get_candidate_versions(pkgname)
        if candidate_versions is not None:
            candidate_version = candidate_versions[0]
        else:
            self.logger.error("Package %s is installed but no candidate"
                              "version was found." % (entry.get('name')))
            return False

        if entry.get('version').startswith('auto'):
            desired_version = candidate_version
            entry.set('version', "auto: %s" % desired_version)
        elif entry.get('version').startswith('any'):
            desired_version = installed_version
            entry.set('version', "any: %s" % desired_version)
        else:
            desired_version = entry.get('version')

        if desired_version != installed_version:
            entry.set('current_version', installed_version)
            entry.set('qtext', "Modify Package %s (%s -> %s)? (y/N) " %
                      (entry.get('name'), entry.get('current_version'),
                       desired_version))
            return False
        else:
            # version matches
            if (not Bcfg2.Options.setup.quick and
                    entry.get('verify', 'true') == 'true' and
                    checksums):
                pkgsums = self.VerifyChecksums(entry, modlist)
                return pkgsums
            return True

    def Remove(self, packages):
        """Deal with extra configuration detected."""
        pkgnames = " ".join([pkg.get('name') for pkg in packages])
        if len(packages) > 0:
            self.logger.info('Removing packages:')
            self.logger.info(pkgnames)
            self.cmd.run([self.pkg, 'delete', '-y', pkgnames])
            self._load_pkg_cache()
            self.modified += packages
            self.extra = self.FindExtra()

    def Install(self, packages):
        ipkgs = []
        bad_pkgs = []
        for pkg in packages:
            versions = self._get_candidate_versions(pkg.get('name'))
            if versions is None:
                self.logger.error("pkg has no information about package %s" %
                                  (pkg.get('name')))
                continue

            if pkg.get('version').startswith('auto') or \
                    pkg.get('version').startswith('any'):
                ipkgs.append("%s-%s" % (pkg.get('name'), versions[0]))
                continue

            if pkg.get('version') in versions:
                ipkgs.append("%s-%s" % (pkg.get('name'), pkg.get('version')))
                continue
            else:
                self.logger.error("Package %s: desired version %s not in %s" %
                                  (pkg.get('name'), pkg.get('version'),
                                   versions))
            bad_pkgs.append(pkg.get('name'))

        if bad_pkgs:
            self.logger.error("Cannot find correct versions of packages:")
            self.logger.error(bad_pkgs)
        if not ipkgs:
            return dict()
        if not self.cmd.run(self.pkgcmd % (" ".join(ipkgs))):
            self.logger.error("pkg command failed")
        self._load_pkg_cache()
        self.extra = self.FindExtra()
        mark = []
        states = dict()
        for package in packages:
            states[package] = self.VerifyPackage(package, [], checksums=False)
            if states[package]:
                self.modified.append(package)
                if package.get('origin') == 'Packages':
                    mark.append(package.get('name'))
        if mark:
            self.cmd.run([self.pkg, 'set', '-A1', '-y'] + mark)
        return states

    def VerifyPath(self, _entry, _):
        """Do nothing here since we only verify Path type=ignore."""
        return True
