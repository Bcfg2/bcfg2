"""This is the Bcfg2 support for apt-get."""

import os
import sys

import apt.cache

import Bcfg2.Options
import Bcfg2.Client.Tools


class APT(Bcfg2.Client.Tools.Tool):
    """The Debian toolset implements package and service operations
    and inherits the rest from Tools.Tool."""

    options = Bcfg2.Client.Tools.Tool.options + [
        Bcfg2.Options.PathOption(
            cf=('APT', 'install_path'),
            default='/usr', dest='apt_install_path',
            help='Apt tools install path'),
        Bcfg2.Options.PathOption(
            cf=('APT', 'var_path'), default='/var', dest='apt_var_path',
            help='Apt tools var path'),
        Bcfg2.Options.PathOption(
            cf=('APT', 'etc_path'), default='/etc', dest='apt_etc_path',
            help='System etc path')]

    __execs__ = []
    __handles__ = [('Package', 'deb'), ('Path', 'ignore')]
    __req__ = {'Package': ['name', 'version'], 'Path': ['type']}

    def __init__(self, config):
        Bcfg2.Client.Tools.Tool.__init__(self, config)

        self.debsums = '%s/bin/debsums' % Bcfg2.Options.setup.apt_install_path
        self.aptget = '%s/bin/apt-get' % Bcfg2.Options.setup.apt_install_path
        self.dpkg = '%s/bin/dpkg' % Bcfg2.Options.setup.apt_install_path
        self.__execs__ = [self.debsums, self.aptget, self.dpkg]

        path_entries = os.environ['PATH'].split(':')
        for reqdir in ['/sbin', '/usr/sbin']:
            if reqdir not in path_entries:
                os.environ['PATH'] = os.environ['PATH'] + ':' + reqdir
        self.pkgcmd = '%s ' % self.aptget + \
                      '-o DPkg::Options::=--force-confold ' + \
                      '-o DPkg::Options::=--force-confmiss ' + \
                      '--reinstall ' + \
                      '--force-yes '
        if not Bcfg2.Options.setup.debug:
            self.pkgcmd += '-q=2 '
        self.pkgcmd += '-y install %s'
        self.ignores = [entry.get('name') for struct in config
                        for entry in struct
                        if entry.tag == 'Path' and
                        entry.get('type') == 'ignore']
        self.__important__ = self.__important__ + [
            "%s/cache/debconf/config.dat" % Bcfg2.Options.setup.apt_var_path,
            "%s/cache/debconf/templates.dat" %
            Bcfg2.Options.setup.apt_var_path,
            '/etc/passwd', '/etc/group',
            '%s/apt/apt.conf' % Bcfg2.Options.setup.apt_etc_path,
            '%s/dpkg/dpkg.cfg' % Bcfg2.Options.setup.apt_etc_path] + \
            [entry.get('name') for struct in config
             for entry in struct
             if (entry.tag == 'Path' and
                 entry.get('name').startswith(
                     '%s/apt/sources.list' %
                     Bcfg2.Options.setup.apt_etc_path))]
        self.nonexistent = [entry.get('name') for struct in config
                            for entry in struct
                            if (entry.tag == 'Path' and
                                entry.get('type') == 'nonexistent')]
        os.environ["DEBIAN_FRONTEND"] = 'noninteractive'
        self.actions = {}
        if Bcfg2.Options.setup.kevlar and not Bcfg2.Options.setup.dry_run:
            self.cmd.run("%s --force-confold --configure --pending" %
                         self.dpkg)
            self.cmd.run("%s clean" % self.aptget)
            try:
                self.pkg_cache = apt.cache.Cache()
            except SystemError:
                err = sys.exc_info()[1]
                self.logger.info("Failed to initialize APT cache: %s" % err)
                raise Bcfg2.Client.Tools.ToolInstantiationError
            try:
                self.pkg_cache.update()
            except apt.cache.FetchFailedException:
                err = sys.exc_info()[1]
                self.logger.info("Failed to update APT cache: %s" % err)
        self.pkg_cache = apt.cache.Cache()

    def FindExtra(self):
        """Find extra packages."""
        packages = [entry.get('name') for entry in self.getSupportedEntries()]
        extras = [(p.name, p.installed.version) for p in self.pkg_cache
                  if p.is_installed and p.name not in packages]
        return [Bcfg2.Client.XML.Element('Package', name=name, type='deb',
                                         current_version=version)
                for (name, version) in extras]

    def VerifyDebsums(self, entry, modlist):
        """Verify the package contents with debsum information."""
        output = \
            self.cmd.run("%s -as %s" %
                         (self.debsums, entry.get('name'))).stderr.splitlines()
        if len(output) == 1 and "no md5sums for" in output[0]:
            self.logger.info("Package %s has no md5sums. Cannot verify" %
                             entry.get('name'))
            entry.set('qtext',
                      "Reinstall Package %s-%s to setup md5sums? (y/N) " %
                      (entry.get('name'), entry.get('version')))
            return False
        files = []
        for item in output:
            if "checksum mismatch" in item:
                files.append(item.split()[-1])
            elif "changed file" in item:
                files.append(item.split()[3])
            elif "can't open" in item:
                if item.split()[5] not in self.nonexistent:
                    files.append(item.split()[5])
            elif "missing file" in item and \
                 item.split()[3] in self.nonexistent:
                # these files should not exist
                continue
            elif "is not installed" in item or "missing file" in item:
                self.logger.error("Package %s is not fully installed"
                                  % entry.get('name'))
            else:
                self.logger.error("Got Unsupported pattern %s from debsums"
                                  % item)
                files.append(item)
        files = list(set(files) - set(self.ignores))
        # We check if there is file in the checksum to do
        if files:
            # if files are found there we try to be sure our modlist is sane
            # with erroneous symlinks
            modlist = [os.path.realpath(filename) for filename in modlist]
            bad = [filename for filename in files if filename not in modlist]
            if bad:
                self.logger.debug("It is suggested that you either manage "
                                  "these files, revert the changes, or "
                                  "ignore false failures:")
                self.logger.info("Package %s failed validation. Bad files are:"
                                 % entry.get('name'))
                self.logger.info(bad)
                entry.set(
                    'qtext',
                    "Reinstall Package %s-%s to fix failing files? (y/N) "
                    % (entry.get('name'), entry.get('version')))
                return False
        return True

    def VerifyPackage(self, entry, modlist, checksums=True):
        """Verify package for entry."""
        if 'version' not in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
                             (entry.attrib['name']))
            return False
        pkgname = entry.get('name')
        if pkgname not in self.pkg_cache or \
           not self.pkg_cache[pkgname].is_installed:
            self.logger.info("Package %s not installed" % (entry.get('name')))
            entry.set('current_exists', 'false')
            return False

        pkg = self.pkg_cache[pkgname]
        installed_version = pkg.installed.version
        if entry.get('version') == 'auto':
            if pkg.is_upgradable:
                desired_version = pkg.candidate.version
            else:
                desired_version = installed_version
        elif entry.get('version') == 'any':
            desired_version = installed_version
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
            if not Bcfg2.Options.setup.quick \
               and entry.get('verify', 'true') == 'true' \
               and checksums:
                pkgsums = self.VerifyDebsums(entry, modlist)
                return pkgsums
            return True

    def Remove(self, packages):
        """Deal with extra configuration detected."""
        pkgnames = " ".join([pkg.get('name') for pkg in packages])
        self.pkg_cache = apt.cache.Cache()
        if len(packages) > 0:
            self.logger.info('Removing packages:')
            self.logger.info(pkgnames)
            for pkg in pkgnames.split(" "):
                self.pkg_cache[pkg].mark_delete(purge=True)
            self.pkg_cache.commit()
            self.pkg_cache = apt.cache.Cache()
            self.modified += packages
            self.extra = self.FindExtra()

    def Install(self, packages):
        # it looks like you can't install arbitrary versions of software
        # out of the pkg cache, we will still need to call apt-get
        ipkgs = []
        bad_pkgs = []
        for pkg in packages:
            pkgname = pkg.get('name')
            if pkgname not in self.pkg_cache:
                self.logger.error("APT has no information about package %s"
                                  % pkgname)
                continue
            if pkg.get('version') in ['auto', 'any']:
                try:
                    ipkgs.append("%s=%s" % (
                        pkgname,
                        self.pkg_cache[pkgname].candidate.version))
                except AttributeError:
                    self.logger.error("Failed to find %s in apt package "
                                      "cache" % pkgname)
                continue
            avail_vers = self.pkg_cache[pkgname].versions.keys()
            if pkg.get('version') in avail_vers:
                ipkgs.append("%s=%s" % (pkgname, pkg.get('version')))
                continue
            else:
                self.logger.error("Package %s: desired version %s not in %s"
                                  % (pkgname, pkg.get('version'), avail_vers))
            bad_pkgs.append(pkgname)
        if bad_pkgs:
            self.logger.error("Cannot find correct versions of packages:")
            self.logger.error(bad_pkgs)
        if not ipkgs:
            return dict()
        if not self.cmd.run(self.pkgcmd % (" ".join(ipkgs))):
            self.logger.error("APT command failed")
        self.pkg_cache = apt.cache.Cache()
        self.extra = self.FindExtra()
        states = dict()
        for package in packages:
            states[package] = self.VerifyPackage(package, [], checksums=False)
            if states[package]:
                self.modified.append(package)
        return states

    def VerifyPath(self, entry, _):  # pylint: disable=W0613
        """Do nothing here since we only verify Path type=ignore."""
        return True
