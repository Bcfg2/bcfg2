"""This is the Bcfg2 tool for the FreeBSD package system."""

# TODO
# - actual package installation
# - verification of package files

import re
import Bcfg2.Client.Tools


class FreeBSDPackage(Bcfg2.Client.Tools.PkgTool):
    """The FreeBSD toolset implements package operations and inherits
    the rest from Toolset.Toolset."""
    name = 'FreeBSDPackage'
    __execs__ = ['/usr/sbin/pkg_add', '/usr/sbin/pkg_info']
    __handles__ = [('Package', 'freebsdpkg')]
    __req__ = {'Package': ['name', 'version']}
    pkgtool = ('/usr/sbin/pkg_add -r %s', ('%s-%s', ['name', 'version']))
    pkgtype = 'freebsdpkg'

    def RefreshPackages(self):
        self.installed = {}
        packages = self.cmd.run("/usr/sbin/pkg_info -a -E").stdout.splitlines()
        pattern = re.compile(r'(.*)-(\d.*)')
        for pkg in packages:
            if pattern.match(pkg):
                name = pattern.match(pkg).group(1)
                version = pattern.match(pkg).group(2)
                self.installed[name] = version

    def VerifyPackage(self, entry, _):
        if not 'version' in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
                             entry.attrib['name'])
            return False
        if entry.attrib['name'] in self.installed:
            if self.installed[entry.attrib['name']] == entry.attrib['version']:
                # TODO: verfification
                return True
            else:
                entry.set('current_version', self.installed[entry.get('name')])
                return False

        self.logger.info("Package %s not installed" % (entry.get('name')))
        entry.set('current_exists', 'false')
        return False
