"""This provides Bcfg2 support for Alpine Linux APK packages."""

import Bcfg2.Client.Tools


class APK(Bcfg2.Client.Tools.PkgTool):
    """Support for Apk packages."""
    name = 'APK'
    __execs__ = ["/sbin/apk"]
    __handles__ = [('Package', 'apk')]
    __req__ = {'Package': ['name', 'version']}
    pkgtype = 'apk'
    pkgtool = ("/sbin/apk add %s", ("%s", ["name"]))

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)
        self.installed = {}
        self.RefreshPackages()

    def RefreshPackages(self):
        """Refresh memory hashes of packages."""
        names = self.cmd.run("/sbin/apk info").stdout.splitlines()
        nameversions = self.cmd.run("/sbin/apk info -v").stdout.splitlines()
        for pkg in zip(names, nameversions):
            pkgname = pkg[0]
            version = pkg[1][len(pkgname) + 1:]
            self.logger.debug(" pkgname: %s" % pkgname)
            self.logger.debug(" version: %s" % version)
            self.installed[pkgname] = version

    def VerifyPackage(self, entry, _):
        """Verify Package status for entry."""
        if not 'version' in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
                             entry.attrib['name'])
            return False

        if entry.attrib['name'] in self.installed:
            if entry.attrib['version'] in \
                    ['auto', self.installed[entry.attrib['name']]]:
                #if not self.setup['quick'] and \
                #                entry.get('verify', 'true') == 'true':
                #FIXME: Does APK have any sort of verification mechanism?
                return True
            else:
                self.logger.info(" pkg %s at version %s, not %s" %
                                 (entry.attrib['name'],
                                  self.installed[entry.attrib['name']],
                                  entry.attrib['version']))
                entry.set('current_version', self.installed[entry.get('name')])
                return False
        entry.set('current_exists', 'false')
        return False

    def Remove(self, packages):
        """Remove extra packages."""
        names = [pkg.get('name') for pkg in packages]
        self.logger.info("Removing packages: %s" % " ".join(names))
        self.cmd.run("/sbin/apk del %s" % " ".join(names))
        self.RefreshPackages()
        self.extra = self.FindExtra()
