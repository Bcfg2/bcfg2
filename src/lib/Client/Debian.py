'''This is the bcfg2 support for debian'''
__revision__ = '$Revision$'

from glob import glob
from os import environ, stat, system
from re import compile as regcompile

import apt_pkg

from Bcfg2.Client.Toolset import Toolset, saferun

class Debian(Toolset):
    '''The Debian toolset implements package and service operations and inherits
    the rest from Toolset.Toolset'''
    __important__ = ["/etc/apt/sources.list", "/var/cache/debconf/config.dat", \
                     "/var/cache/debconf/templates.dat", '/etc/passwd', '/etc/group', \
                     '/etc/apt/apt.conf']
    pkgtool = {'deb':('DEBIAN_FRONTEND=noninteractive apt-get --reinstall -q=2 --force-yes -y install %s',
                      ('%s=%s', ['name', 'version']))}
    svcre = regcompile("/etc/.*/[SK]\d\d(?P<name>\S+)")

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.cfg = cfg
        environ["DEBIAN_FRONTEND"] = 'noninteractive'
        system("dpkg --force-confold --configure -a")
        if not self.setup['build']:
            system("dpkg-reconfigure -f noninteractive debconf < /dev/null")
        system("apt-get clean")
        system("apt-get -q=2 -y update")
        self.installed = {}
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}
        for pkg in [cpkg for cpkg in self.cfg.findall(".//Package") if not cpkg.attrib.has_key('type')]:
            pkg.set('type', 'deb')
        self.Refresh()

    def Refresh(self):
        '''Refresh memory hashes of packages'''
        apt_pkg.init()
        cache = apt_pkg.GetCache()
        self.installed = {}
        for pkg in cache.Packages:
            if pkg.CurrentVer:
                self.installed[pkg.Name] = pkg.CurrentVer.VerStr

    # implement entry (Verify|Install) ops
    
    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        rawfiles = glob("/etc/rc*.d/*%s" % (entry.get('name')))
        files = [filename for filename in rawfiles if self.svcre.match(filename).group('name') == entry.get('name')]
        if entry.get('status') == 'off':
            if files:
                return False
            else:
                return True
        else:
            if files:
                return True
            else:
                return False

    def InstallService(self, entry):
        '''Install Service for entry'''
        cmdrc = 1
        self.CondPrint('verbose', "Installing Service %s" % (entry.get('name')))
        try:
            stat('/etc/init.d/%s' % entry.get('name'))
        except OSError:
            self.CondPrint('debug', "Init script for service %s does not exist" % entry.get('name'))
            return False
        
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling service %s" % (entry.get('name'))
            else:
                cmdrc = system("update-rc.d -f %s remove" % entry.get('name'))
        else:
            if self.setup['dryrun']:
                print "Enabling service %s" % (entry.attrib['name'])
            else:
                cmdrc = system("update-rc.d %s defaults" % (entry.attrib['name']))
        if cmdrc:
            return False
        return True

    def VerifyPackage(self, entry, modlist):
        '''Verify Package for entry'''
        if self.installed.has_key(entry.attrib['name']):
            if self.installed[entry.attrib['name']] == entry.attrib['version']:
                if not self.setup['quick']:
                    output = saferun("debsums -s %s" % entry.get('name'))[1]
                    if [filename for filename in output if filename not in modlist]:
                        return False
                return True
        return False

    def Inventory(self):
        '''Do standard inventory plus debian extra service check'''
        Toolset.Inventory(self)
        allsrv = []
        [allsrv.append(self.svcre.match(fname).group('name')) for fname in
         glob("/etc/rc[12345].d/S*") if self.svcre.match(fname).group('name') not in allsrv]
        self.CondPrint('debug', "Found active services: %s" % allsrv)
        csrv = self.cfg.findall(".//Service")
        [allsrv.remove(svc.get('name')) for svc in csrv if
         svc.get('status') == 'on' and svc.get('name') in allsrv]
        self.extra_services = allsrv

    def HandleExtra(self):
        '''Deal with extra configuration detected'''
        if len(self.pkgwork) > 0:
            if self.setup['remove'] in ['all', 'packages']:
                self.CondPrint('verbose', "Removing packages: %s" % self.pkgwork['remove'])
                if not system("apt-get remove %s" % " ".join(self.pkgwork['remove'])):
                    self.pkgwork['remove'] = []
            else:
                self.CondPrint('verbose', "Need to remove packages: %s" % self.pkgwork['remove'])
        if len(self.extra_services) > 0:
            if self.setup['remove'] in ['all', 'services']:
                self.CondPrint('verbose', "Removing services: %s" % self.extra_services)
                [self.extra_services.remove(serv) for serv in self.extra_services if
                 not system("rm -f /etc/rc*.d/S??%s" % serv)]
            else:
                self.CondPrint('verbose', "Need to remove services: %s" % self.extra_services)
        
