"""This is the Bcfg2 support for OpenSolaris packages."""

import pkg.client.image as image
import pkg.client.progress as progress

import Bcfg2.Client.Tools


class IPS(Bcfg2.Client.Tools.PkgTool):
    """The IPS driver implements OpenSolaris package operations."""
    name = 'IPS'
    pkgtype = 'ips'
    conflicts = ['SYSV']
    __handles__ = [('Package', 'ips')]
    __req__ = {'Package': ['name', 'version']}
    pkgtool = ('pkg install --no-refresh %s', ('%s', ['name']))

    def __init__(self, logger, setup, cfg):
        self.installed = {}
        self.pending_upgrades = set()
        self.image = image.Image()
        self.image.find_root('/', False)
        self.image.load_config()
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, cfg)
        self.cfg = cfg

    def RefreshPackages(self):
        self.installed = dict()
        self.image.history.operation_name = "list"
        self.image.load_catalogs(progress.NullProgressTracker())
        for (pfmri, pinfo) in self.image.inventory([], False):
            pname = pfmri.pkg_name
            pversion = pfmri.version.get_short_version()
            self.installed[pname] = pversion
            if pinfo['upgradable']:
                self.pending_upgrades.add(pname)

    def VerifyPackage(self, entry, _):
        """Verify package for entry."""
        pname = entry.get('name')
        if not 'version' in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" % (pname))
            return False
        if pname not in self.installed:
            self.logger.debug("IPS: Package %s not installed" % pname)
            return False
        if entry.get('version') == 'auto':
            if pname in self.pending_upgrades:
                return False
        elif entry.get('version') == 'any':
            pass
        else:
            if entry.get('version') != self.installed[pname]:
                self.logger.debug("IPS: Package %s: have %s want %s" %
                                  (pname, self.installed[pname],
                                   entry.get('version')))
                return False

        # need to implement pkg chksum validation
        return True
