"""This is the Bcfg2 tool for the Gentoo Portage system."""
__revision__ = '$Revision$'

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
    pkgtool = ('emerge --getbinpkgonly %s', ('=%s-%s', ['name', 'version']))

    def __init__(self, logger, cfg, setup):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, cfg, setup)
        self.__important__ = self.__important__ + ['/etc/make.conf']
        self.cfg = cfg
        self.installed = {}
        self.RefreshPackages()

    def RefreshPackages(self):
        """Refresh memory hashes of packages."""
        ret, cache = self.cmd.run("equery -q list '*'")
        if ret == 2:
            cache = self.cmd.run("equery -q list '*'")[1]
        pattern = re.compile('(.*)-(\d.*)')
        self.installed = {}
        for pkg in cache:
            if pattern.match(pkg):
                name = pattern.match(pkg).group(1)
                version = pattern.match(pkg).group(2)
                self.installed[name] = version
            else:
                self.logger.info("Failed to parse pkg name %s" % pkg)

    def VerifyPackage(self, entry, modlist):
        """Verify package for entry."""
        if not 'version' in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
               (entry.attrib['name']))
            return False
        if entry.attrib['name'] in self.installed:
            if self.installed[entry.attrib['name']] == entry.attrib['version']:
                if not self.setup['quick'] and \
                                entry.get('verify', 'true') == 'true':
                    output = self.cmd.run("/usr/bin/equery -N check '=%s-%s' 2>&1 "
                                          "| grep '!!!' | awk '{print $2}'" \
                                          % (entry.get('name'), entry.get('version')))[1]
                    if [filename for filename in output \
                                    if filename not in modlist]:
                        return False
                return True
            else:
                entry.set('current_version', self.installed[entry.get('name')])
                return False
        entry.set('current_exists', 'false')
        return False

    def RemovePackages(self, packages):
        """Deal with extra configuration detected."""
        pkgnames = " ".join([pkg.get('name') for pkg in packages])
        if len(packages) > 0:
            self.logger.info('Removing packages:')
            self.logger.info(pkgnames)
            self.cmd.run("emerge --unmerge --quiet %s" % " ".join(pkgnames.split(' ')))
            self.RefreshPackages()
            self.extra = self.FindExtraPackages()
