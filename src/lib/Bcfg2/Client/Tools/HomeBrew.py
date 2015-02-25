"""This provides Bcfg2 support for homebrew packages."""

import Bcfg2.Client.Tools


class HomeBrew(Bcfg2.Client.Tools.PkgTool):
    """Homebrew package support."""
    name = 'HomeBrew'
    __execs__ = ["/usr/local/bin/brew"]
    __handles__ = [('Package', 'homebrew')]
    __req__ = {'Package': ['name', 'version']}
    pkgtype = 'homebrew'
    pkgtool = ('/usr/local/bin/brew install %s', ('%s', ['name']))

    def RefreshPackages(self):
        """Refresh memory hashes of packages."""
        pkgcache = self.cmd.run(["/usr/local/bin/brew",
                                 "list", "--versions"]).stdout.splitlines()
        self.installed = {}
        for pkg in pkgcache:
            pkgname, version = pkg.strip().split()
            self.logger.debug(" pkgname: %s version: %s" % (pkgname, version))
            self.installed[pkgname] = version

    def VerifyPackage(self, entry, _):
        """Verify Package status for entry."""
        self.logger.debug("VerifyPackage: %s : %s" % (entry.get('name'),
                                                      entry.get('version')))

        if entry.attrib['name'] in self.installed:
            if (self.installed[entry.attrib['name']] ==
                    entry.attrib['version'] or
                    entry.attrib['version'] == 'any'):
                return True
            else:
                self.logger.info("  %s: Wrong version installed.  "
                                 "Want %s, but have %s" %
                                 (entry.get("name"),
                                  entry.get("version"),
                                  self.installed[entry.get("name")]))

                entry.set('current_version', self.installed[entry.get('name')])
                return False
        entry.set('current_exists', 'false')
        return False

    def Remove(self, packages):
        """Remove extra packages."""
        pkg_names = [p.get('name') for p in packages]
        self.logger.info("Removing packages: %s" % pkg_names)
        self.cmd.run(["/usr/local/bin/brew", "uninstall"] + pkg_names)
        self.RefreshPackages()
        self.extra = self.FindExtra()
