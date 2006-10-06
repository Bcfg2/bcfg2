# This is the bcfg2 support for solaris sysv packages
'''This provides bcfg2 support for Solaris SYSV packages'''
__revision__ = '$Revision$'

import tempfile, Bcfg2.Client.Tools, Bcfg2.Client.XML


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
    '''Solaris SYSV package support'''
    __execs__ = ["/usr/sbin/pkgadd"]
    __handles__ = [('Package', 'sysv')]
    __req__ = {'Package': ['name', 'version']}
    __name__ = 'SYSV'
    pkgtype = 'sysv'
    pkgtool = ("/usr/sbin/pkgadd %s -d %%s -n %%%%s", (("%s", ["name"])))

    def __init__(self, logger, setup, config, states):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config, states)
        self.noaskname = tempfile.mktemp()
        try:
            open(self.noaskname, 'w+').write(noask)
            self.pkgtool = (self.pkgtool[0] % ("-a %s" % (self.noaskname)), \
                            self.pkgtool[1])
        except:
            self.pkgtool = (self.pkgtool[0] % (""), self.pkgtool[1])

    def RefreshPackages(self):
        '''Refresh memory hashes of packages'''
        self.installed = {}
        # Build list of packages
        lines = self.cmd.run("/usr/bin/pkginfo -x")[1]
        while lines:
            version = lines.pop().split()[1]
            pkg = lines.pop().split()[0]
            self.installed[pkg] = version

    def VerifyPackage(self, entry, modlist):
        '''Verify Package status for entry'''
        if not entry.get('version'):
            self.logger.info("Insufficient information of Package %s; cannot Verify" % entry.get('name'))
            return False
        cmdrc = self.cmd.run("/usr/bin/pkginfo -q -v \"%s\" %s" % \
                             (entry.get('version'), entry.get('name')))[0]

        if cmdrc != 0:
            self.logger.debug("Package %s version incorrect" % entry.get('name'))
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
        '''Remove specified Sysv packages'''
        names = [pkg.get('name') for pkg in packages]
        self.logger.info("Removing packages: %s" % (names))
        self.cmd.run("/usr/sbin/pkgrm -a %s -n %s" % \
                     (self.noaskname, names))
        self.RefreshPackages()
        self.extra = self.FindExtraPackages()
