"""This is the Bcfg2 support for apt-get."""
__revision__ = '$Revision$'

# suppress apt API warnings
import warnings
warnings.filterwarnings("ignore", "apt API not stable yet",
                        FutureWarning)
import apt.cache
import os

import Bcfg2.Client.Tools
import Bcfg2.Options

# Options for tool locations
opts = {'install_path': Bcfg2.Options.CLIENT_APT_TOOLS_INSTALL_PATH,
        'var_path': Bcfg2.Options.CLIENT_APT_TOOLS_VAR_PATH,
        'etc_path': Bcfg2.Options.CLIENT_SYSTEM_ETC_PATH}
setup = Bcfg2.Options.OptionParser(opts)
setup.parse([])
install_path = setup['install_path']
var_path = setup['var_path']
etc_path = setup['etc_path']
DEBSUMS = '%s/bin/debsums' % install_path
APTGET = '%s/bin/apt-get' % install_path
DPKG = '%s/bin/dpkg' % install_path

class APT(Bcfg2.Client.Tools.Tool):
    """The Debian toolset implements package and service operations and inherits
    the rest from Toolset.Toolset.

    """
    name = 'APT'
    __execs__ = [DEBSUMS, APTGET, DPKG]
    __handles__ = [('Package', 'deb'), ('Path', 'ignore')]
    __req__ = {'Package': ['name', 'version'], 'Path': ['type']}

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.Tool.__init__(self, logger, setup, config)
        path_entries = os.environ['PATH'].split(':')
        for reqdir in ['/sbin', '/usr/sbin']:
            if reqdir not in path_entries:
                os.environ['PATH'] = os.environ['PATH'] + ':' + reqdir
        self.pkgcmd = '%s ' % APTGET + \
                      '-o DPkg::Options::=--force-overwrite ' + \
                      '-o DPkg::Options::=--force-confold ' + \
                      '-o DPkg::Options::=--force-confmiss ' + \
                      '--reinstall ' + \
                      '--force-yes '
        if not self.setup['debug']:
            self.pkgcmd += '-q=2 '
        self.pkgcmd += '-y install %s'
        self.ignores = [entry.get('name') for struct in config \
                        for entry in struct \
                        if entry.tag == 'Path' and \
                        entry.get('type') == 'ignore']
        self.__important__ = self.__important__ + \
                             ["%s/cache/debconf/config.dat" % var_path,
                              "%s/cache/debconf/templates.dat" % var_path,
                              '/etc/passwd', '/etc/group',
                              '%s/apt/apt.conf' % etc_path,
                              '%s/dpkg/dpkg.cfg' % etc_path] + \
                             [entry.get('name') for struct in config for entry in struct \
                              if entry.tag == 'Path' and \
                              entry.get('name').startswith('%s/apt/sources.list' % etc_path)]
        self.nonexistent = [entry.get('name') for struct in config for entry in struct \
                              if entry.tag == 'Path' and entry.get('type') == 'nonexistent']
        os.environ["DEBIAN_FRONTEND"] = 'noninteractive'
        self.actions = {}
        if self.setup['kevlar'] and not self.setup['dryrun']:
            self.cmd.run("%s --force-confold --configure --pending" % DPKG)
            self.cmd.run("%s clean" % APTGET)
            try:
                self.pkg_cache = apt.cache.Cache()
            except SystemError:
                e = sys.exc_info()[1]
                self.logger.info("Failed to initialize APT cache: %s" % e)
                raise Bcfg2.Client.Tools.toolInstantiationError
            self.pkg_cache.update()
        self.pkg_cache = apt.cache.Cache()
        if 'req_reinstall_pkgs' in dir(self.pkg_cache):
            self._newapi = True
        else:
            self._newapi = False

    def FindExtra(self):
        """Find extra packages."""
        packages = [entry.get('name') for entry in self.getSupportedEntries()]
        if self._newapi:
            extras = [(p.name, p.installed.version) for p in self.pkg_cache
                      if p.is_installed and p.name not in packages]
        else:
            extras = [(p.name, p.installedVersion) for p in self.pkg_cache
                      if p.isInstalled and p.name not in packages]
        return [Bcfg2.Client.XML.Element('Package', name=name, \
                                         type='deb', version=version) \
                                         for (name, version) in extras]

    def VerifyDebsums(self, entry, modlist):
        output = self.cmd.run("%s -as %s" % (DEBSUMS, entry.get('name')))[1]
        if len(output) == 1 and "no md5sums for" in output[0]:
            self.logger.info("Package %s has no md5sums. Cannot verify" % \
                             entry.get('name'))
            entry.set('qtext', "Reinstall Package %s-%s to setup md5sums? (y/N) " \
                      % (entry.get('name'), entry.get('version')))
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
                self.logger.error("Package %s is not fully installed" \
                                  % entry.get('name'))
            else:
                self.logger.error("Got Unsupported pattern %s from debsums" \
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
                self.logger.debug("It is suggested that you either manage these "
                                  "files, revert the changes, or ignore false "
                                  "failures:")
                self.logger.info("Package %s failed validation. Bad files are:" % \
                                 entry.get('name'))
                self.logger.info(bad)
                entry.set('qtext',
                          "Reinstall Package %s-%s to fix failing files? (y/N) " % \
                          (entry.get('name'), entry.get('version')))
                return False
        return True

    def VerifyPackage(self, entry, modlist, checksums=True):
        """Verify package for entry."""
        if not 'version' in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
                             (entry.attrib['name']))
            return False
        pkgname = entry.get('name')
        if self.pkg_cache.has_key(pkgname):
            if self._newapi:
                is_installed = self.pkg_cache[pkgname].is_installed
            else:
                is_installed = self.pkg_cache[pkgname].isInstalled
        if not self.pkg_cache.has_key(pkgname) or not is_installed:
            self.logger.info("Package %s not installed" % (entry.get('name')))
            entry.set('current_exists', 'false')
            return False

        pkg = self.pkg_cache[pkgname]
        if self._newapi:
            installed_version = pkg.installed.version
            candidate_version = pkg.candidate.version
        else:
            installed_version = pkg.installedVersion
            candidate_version = pkg.candidateVersion
        if entry.get('version') == 'auto':
            if self._newapi:
                is_upgradable = self.pkg_cache._depcache.is_upgradable(pkg._pkg)
            else:
                is_upgradable = self.pkg_cache._depcache.IsUpgradable(pkg._pkg)
            if is_upgradable:
                desiredVersion = candidate_version
            else:
                desiredVersion = installed_version
        elif entry.get('version') == 'any':
            desiredVersion = installed_version
        else:
            desiredVersion = entry.get('version')
        if desiredVersion != installed_version:
            entry.set('current_version', installed_version)
            entry.set('qtext', "Modify Package %s (%s -> %s)? (y/N) " % \
                      (entry.get('name'), entry.get('current_version'),
                       desiredVersion))
            return False
        else:
            # version matches
            if not self.setup['quick'] and entry.get('verify', 'true') == 'true' \
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
                try:
                    if self._newapi:
                        self.pkg_cache[pkg].mark_delete(purge=True)
                    else:
                        self.pkg_cache[pkg].markDelete(purge=True)
                except:
                    if self._newapi:
                        self.pkg_cache[pkg].mark_delete()
                    else:
                        self.pkg_cache[pkg].markDelete()
            try:
                self.pkg_cache.commit()
            except SystemExit:
                # thank you python-apt 0.6
                pass
            self.pkg_cache = apt.cache.Cache()
            self.modified += packages
            self.extra = self.FindExtra()

    def Install(self, packages, states):
        # it looks like you can't install arbitrary versions of software
        # out of the pkg cache, we will still need to call apt-get
        ipkgs = []
        bad_pkgs = []
        for pkg in packages:
            if not self.pkg_cache.has_key(pkg.get('name')):
                self.logger.error("APT has no information about package %s" % (pkg.get('name')))
                continue
            if pkg.get('version') in ['auto', 'any']:
                if self._newapi:
                    ipkgs.append("%s=%s" % (pkg.get('name'),
                                            self.pkg_cache[pkg.get('name')].candidate.version))
                else:
                    ipkgs.append("%s=%s" % (pkg.get('name'),
                                            self.pkg_cache[pkg.get('name')].candidateVersion))
                continue
            if self._newapi:
                avail_vers = [x.ver_str for x in \
                              self.pkg_cache[pkg.get('name')]._pkg.version_list]
            else:
                avail_vers = [x.VerStr for x in \
                              self.pkg_cache[pkg.get('name')]._pkg.VersionList]
            if pkg.get('version') in avail_vers:
                ipkgs.append("%s=%s" % (pkg.get('name'), pkg.get('version')))
                continue
            else:
                self.logger.error("Package %s: desired version %s not in %s" \
                                  % (pkg.get('name'), pkg.get('version'),
                                     avail_vers))
            bad_pkgs.append(pkg.get('name'))
        if bad_pkgs:
            self.logger.error("Cannot find correct versions of packages:")
            self.logger.error(bad_pkgs)
        if not ipkgs:
            return
        rc = self.cmd.run(self.pkgcmd % (" ".join(ipkgs)))[0]
        if rc:
            self.logger.error("APT command failed")
        self.pkg_cache = apt.cache.Cache()
        self.extra = self.FindExtra()
        for package in packages:
            states[package] = self.VerifyPackage(package, [], checksums=False)
            if states[package]:
                self.modified.append(package)

    def VerifyPath(self, entry, _):
        """Do nothing here since we only verify Path type=ignore."""
        return True
