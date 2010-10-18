# This is the bcfg2 support for solaris sysv packages
"""This provides bcfg2 support for Solaris SYSV packages."""
__revision__ = '$Revision$'

import tempfile

import Bcfg2.Client.Tools
import Bcfg2.Client.XML


noask = '''
mail=
instance=overwrite
partial=nocheck
runlevel=nocheck
idepend=nocheck
rdepend=nocheck
space=ask
setuid=nocheck
conflict=nocheck
action=nocheck
basedir=default
'''


class SYSV(Bcfg2.Client.Tools.PkgTool):
    """Solaris SYSV package support."""
    __execs__ = ["/usr/sbin/pkgadd", "/usr/bin/pkginfo"]
    __handles__ = [('Package', 'sysv')]
    __req__ = {'Package': ['name', 'version']}
    __ireq__ = {'Package': ['name', 'url', 'version']}
    name = 'SYSV'
    pkgtype = 'sysv'
    pkgtool = ("/usr/sbin/pkgadd %s -n -d %%s", (('%s %s', ['url', 'name'])))

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)
        # noaskfile needs to live beyond __init__ otherwise file is removed
        self.noaskfile = tempfile.NamedTemporaryFile()
        self.noaskname = self.noaskfile.name
        try:
            self.noaskfile.write(noask)
            # flush admin file contents to disk
            self.noaskfile.flush()
            self.pkgtool = (self.pkgtool[0] % ("-a %s" % (self.noaskname)), \
                            self.pkgtool[1])
        except:
            self.pkgtool = (self.pkgtool[0] % (""), self.pkgtool[1])

    def RefreshPackages(self):
        """Refresh memory hashes of packages."""
        self.installed = {}
        # Build list of packages
        lines = self.cmd.run("/usr/bin/pkginfo -x")[1]
        while lines:
            # Splitting on whitespace means that packages with spaces in
            # their version numbers don't work right.  Found this with
            # IBM TSM software with package versions like
            #           "Version 6 Release 1 Level 0.0"
            # Should probably be done with a regex but this works.
            version = lines.pop().split(') ')[1]
            pkg = lines.pop().split()[0]
            self.installed[pkg] = version

    def VerifyPackage(self, entry, modlist):
        """Verify Package status for entry."""
        if not entry.get('version'):
            self.logger.info("Insufficient information of Package %s; cannot Verify" % entry.get('name'))
            return False

        desiredVersion = entry.get('version')
        if desiredVersion == 'any':
            desiredVersion = self.installed.get(entry.get('name'), desiredVersion)

        cmdrc = self.cmd.run("/usr/bin/pkginfo -q -v \"%s\" %s" % \
                             (desiredVersion, entry.get('name')))[0]

        if cmdrc != 0:
            if entry.get('name') in self.installed:
                self.logger.debug("Package %s version incorrect: have %s want %s" \
                                  % (entry.get('name'), self.installed[entry.get('name')],
                                     desiredVersion))
            else:
                self.logger.debug("Package %s not installed" % (entry.get("name")))
        else:
            if self.setup['quick'] or entry.attrib.get('verify', 'true') == 'false':
                return True
            (vstat, odata) = self.cmd.run("/usr/sbin/pkgchk -n %s" % (entry.get('name')))
            if vstat == 0:
                return True
            else:
                output = [line for line in odata if line[:5] == 'ERROR']
                if len([name for name in output if name.split()[-1] not in modlist]):
                    self.logger.debug("Package %s content verification failed" % \
                                      (entry.get('name')))
                else:
                    return True
        return False

    def RemovePackages(self, packages):
        """Remove specified Sysv packages."""
        names = [pkg.get('name') for pkg in packages]
        self.logger.info("Removing packages: %s" % (names))
        self.cmd.run("/usr/sbin/pkgrm -a %s -n %s" % \
                     (self.noaskname, names))
        self.RefreshPackages()
        self.extra = self.FindExtraPackages()
