# This is the bcfg2 support for yum
'''This provides bcfg2 support for yum'''
__revision__ = '$Revision:$'

import Bcfg2.Client.Tools.RPM

class Yum(Bcfg2.Client.Tools.RPM.RPM):
    '''Support for Yum packages'''
    pkgtype = 'yum'
    pkgtool = ("/usr/bin/yum install %s", ("%s-%s", ["name", "version"]))
    __name__ = 'Yum'
    __execs__ = ['/usr/bin/yum']
    __handles__ = [('Package', 'yum')]

    def RemovePackages(self, packages):
        '''Remove specified entries'''
        pkgnames = [pkg.get('name') for pkg in packages]
        if len(pkgnames) > 0:
            self.logger.info("Removing packages: %s" % pkgnames)
            if self.cmd.run("yum remove %s" % " ".join(pkgnames))[0] == 0:
                self.modified += packages
            self.RefreshPackages()
            self.extra = self.FindExtraPackages()
