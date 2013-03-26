"""This provides Bcfg2 support for macports packages."""

import Bcfg2.Client.Tools


class MacPorts(Bcfg2.Client.Tools.PkgTool):
    """macports package support."""
    name = 'MacPorts'
    __execs__ = ["/opt/local/bin/port"]
    __handles__ = [('Package', 'macport')]
    __req__ = {'Package': ['name', 'version']}
    pkgtype = 'macport'
    pkgtool = ('/opt/local/bin/port install %s', ('%s', ['name']))

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)
        self.installed = {}
        self.RefreshPackages()

    def RefreshPackages(self):
        """Refresh memory hashes of packages."""
        pkgcache = self.cmd.run(["/opt/local/bin/port",
                                 "installed"]).stdout.splitlines()
        self.installed = {}
        for pkg in pkgcache:
            if pkg.startswith("Warning:"):
                continue
            if pkg.startswith("The following ports are currently installed"):
                continue
            if pkg.startswith("No ports are installed"):
                return
            pkgname = pkg.split('@')[0].strip()
            version = pkg.split('@')[1].split(' ')[0]
            self.logger.info(" pkgname: %s version: %s" % (pkgname, version))
            self.installed[pkgname] = version

    def VerifyPackage(self, entry, _):
        """Verify Package status for entry."""
        if not 'version' in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
                             entry.attrib['name'])
            return False

        if entry.attrib['name'] in self.installed:
            if (self.installed[entry.attrib['name']] == entry.attrib['version']
                or entry.attrib['version'] == 'any'):
                #if not self.setup['quick'] and \
                #                entry.get('verify', 'true') == 'true':
                #FIXME: We should be able to check this once
                #       http://trac.macports.org/ticket/15709 is implemented
                return True
            else:
                self.logger.info("  %s: Wrong version installed.  "
                                 "Want %s, but have %s" %
                                 (entry.get("name"),
                                  entry.get("version"),
                                  self.installed[entry.get("name")],
                                  ))

                entry.set('current_version', self.installed[entry.get('name')])
                return False
        entry.set('current_exists', 'false')
        return False

    def Remove(self, packages):
        """Remove extra packages."""
        names = [pkg.get('name') for pkg in packages]
        self.logger.info("Removing packages: %s" % " ".join(names))
        self.cmd.run("/opt/local/bin/port uninstall %s" %
                     " ".join(names))
        self.RefreshPackages()
        self.extra = self.FindExtra()
