# This is the bcfg2 support for yum
'''This provides bcfg2 support for yum'''
__revision__ = '$Revision$'

import Bcfg2.Client.Tools.RPM, ConfigParser, sys

YAD = True
CP = ConfigParser.ConfigParser()
try:
    if '-C' in sys.argv:
        CP.read([sys.argv[sys.argv.index('-C') + 1]])
    else:
        CP.read(['/etc/bcfg2.conf'])
    if CP.get('Yum', 'autodep') == 'false':
        YAD = False
except:
    pass

class Yum(Bcfg2.Client.Tools.RPM.RPM):
    '''Support for Yum packages'''
    pkgtype = 'yum'
    if YAD:
        pkgtool = ("/usr/bin/yum -d0 -y install %s", ("%s-%s", ["name", "version"]))
    else:
        pkgtool = ("/usr/bin/yum -d0 install %s", ("%s-%s", ["name", "version"]))
    __name__ = 'Yum'
    __execs__ = ['/usr/bin/yum', '/var/lib/rpm']
    __handles__ = [('Package', 'yum')]
    __req__ = {'Package': ['name', 'version']}
    conflicts = ['RPM']

    def RemovePackages(self, packages):
        '''Remove specified entries'''
        pkgnames = [pkg.get('name') for pkg in packages]
        if len(pkgnames) > 0:
            self.logger.info("Removing packages: %s" % pkgnames)
            if self.cmd.run("yum -d0 -y remove %s" % " ".join(pkgnames))[0] == 0:
                self.modified += packages
            self.RefreshPackages()
            self.extra = self.FindExtraPackages()
