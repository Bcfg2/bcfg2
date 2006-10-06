# This is the bcfg2 support for blastwave packages (pkg-get)
'''This provides bcfg2 support for blastwave'''
__revision__ = '$Revision$'

import Bcfg2.Client.Tools.SYSV

class Blast(Bcfg2.Client.Tools.SYSV.SYSV):
    '''Support for Blastwave packages'''
    pkgtype = 'blast'
    pkgtool = ("/opt/csw/bin/pkg-get install %s", ("%s", ["name"]))
    __name__ = 'Blast'
    __execs__ = ['/opt/csw/bin/pkg-get']
    __handles__ = [('Package', 'blast')]

    # VerifyPackage comes from Bcfg2.Client.Tools.SYSV
    # Install comes from Bcfg2.Client.Tools.PkgTool
    # Extra comes from Bcfg2.Client.Tools.Tool
    # Remove comes from Bcfg2.Client.Tools.SYSV

    def FindExtraPackages(self):
        '''Pass through to null FindExtra call'''
        return []
