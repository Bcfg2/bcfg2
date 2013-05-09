"""This is the Bcfg2 tool for the Gentoo Portage system."""

import re
import Bcfg2.Client.Tools


class Portage(Bcfg2.Client.Tools.PkgTool):
    """The Gentoo toolset implements package and service operations and
    inherits the rest from Toolset.Toolset."""
    name = 'Portage'
    __execs__ = ['/usr/bin/emerge', '/usr/bin/equery']
    __handles__ = [('Package', 'ebuild')]
    __req__ = {'Package': ['name', 'version']}
    pkgtype = 'ebuild'
    # requires a working PORTAGE_BINHOST in make.conf
    _binpkgtool = ('emerge --getbinpkgonly %s', ('=%s-%s', ['name',
                                                            'version']))
    pkgtool = ('emerge %s', ('=%s-%s', ['name', 'version']))

    def __init__(self, logger, cfg, setup):
        self._initialised = False
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, cfg, setup)
        self._initialised = True
        self.__important__ = self.__important__ + ['/etc/make.conf']
        self._pkg_pattern = re.compile(r'(.*)-(\d.*)')
        self._ebuild_pattern = re.compile('(ebuild|binary)')
        self.cfg = cfg
        self.installed = {}
        self._binpkgonly = self.setup.get('portage_binpkgonly', False)
        if self._binpkgonly:
            self.pkgtool = self._binpkgtool
        self.RefreshPackages()

    def RefreshPackages(self):
        """Refresh memory hashes of packages."""
        if not self._initialised:
            return
        self.logger.info('Getting list of installed packages')
        self.installed = {}
        for pkg in self.cmd.run(["equery", "-q",
                                 "list", "*"]).stdout.splitlines():
            if self._pkg_pattern.match(pkg):
                name = self._pkg_pattern.match(pkg).group(1)
                version = self._pkg_pattern.match(pkg).group(2)
                self.installed[name] = version
            else:
                self.logger.info("Failed to parse pkg name %s" % pkg)

    def VerifyPackage(self, entry, modlist):
        """Verify package for entry."""
        if not 'version' in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
                             (entry.get('name')))
            return False

        if not (entry.get('name') in self.installed):
            # Can't verify package that isn't installed
            entry.set('current_exists', 'false')
            return False

        # get the installed version
        version = self.installed[entry.get('name')]
        entry.set('current_version', version)

        if not self.setup['quick']:
            if ('verify' not in entry.attrib or
                entry.get('verify').lower() == 'true'):

            # Check the package if:
            # - Not running in quick mode
            # - No verify option is specified in the literal configuration
            #    OR
            # - Verify option is specified and is true

                self.logger.debug('Running equery check on %s' %
                                  entry.get('name'))
                for line in self.cmd.run(
                    ["/usr/bin/equery", "-N", "check",
                     '=%s-%s' % (entry.get('name'),
                                 entry.get('version'))]).stdout.splitlines():
                    if '!!!' in line and line.split()[1] not in modlist:
                        return False

        # By now the package must be in one of the following states:
        # - Not require checking
        # - Have no files modified at all
        # - Have modified files in the modlist only
        if self.installed[entry.get('name')] == version:
            # Specified package version is installed
            # Specified package version may be any in literal configuration
            return True

        # Something got skipped. Indicates a bug
        return False

    def Remove(self, packages):
        """Deal with extra configuration detected."""
        pkgnames = " ".join([pkg.get('name') for pkg in packages])
        if len(packages) > 0:
            self.logger.info('Removing packages:')
            self.logger.info(pkgnames)
            self.cmd.run("emerge --unmerge --quiet %s" %
                         " ".join(pkgnames.split(' ')))
            self.RefreshPackages()
            self.extra = self.FindExtra()
