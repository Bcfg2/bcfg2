'''This is the bcfg2 support for debian'''
__revision__ = '$Revision$'

import apt_pkg, glob, os, re, sys, Bcfg2.Client.Toolset

class ToolsetImpl(Bcfg2.Client.Toolset.Toolset):
    '''The Debian toolset implements package and service operations and inherits
    the rest from Toolset.Toolset'''
    __name__ = 'Debian'
    __important__ = ["/etc/apt/sources.list", "/var/cache/debconf/config.dat", \
                     "/var/cache/debconf/templates.dat", '/etc/passwd', '/etc/group', \
                     '/etc/apt/apt.conf', '/etc/dpkg/dpkg.cfg']
    pkgtool = {'deb':('DEBIAN_FRONTEND=noninteractive apt-get --reinstall -q=2 --force-yes -y install %s',
                      ('%s=%s', ['name', 'version']))}
    svcre = re.compile("/etc/.*/[SK]\d\d(?P<name>\S+)")

    def __init__(self, cfg, setup):
        Bcfg2.Client.Toolset.Toolset.__init__(self, cfg, setup)
        self.cfg = cfg
        self.logger.debug('Configuring Debian toolset')
        os.environ["DEBIAN_FRONTEND"] = 'noninteractive'
        # dup /dev/null on top of stdin
        null = open('/dev/null', 'w+')
        os.dup2(null.fileno(), sys.__stdin__.fileno())
        self.saferun("dpkg --force-confold --configure -a")
        if not self.setup['build']:
            self.saferun("/usr/sbin/dpkg-reconfigure -f noninteractive debconf < /dev/null")
        self.saferun("apt-get clean")
        self.saferun("apt-get -q=2 -y update")
        self.installed = {}
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}
        for pkg in [cpkg for cpkg in self.cfg.findall(".//Package") if not cpkg.attrib.has_key('type')]:
            pkg.set('type', 'deb')
        self.Refresh()
        self.logger.debug('Done configuring Debian toolset')

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
        rawfiles = glob.glob("/etc/rc*.d/*%s" % (entry.get('name')))
        files = [filename for filename in rawfiles if self.svcre.match(filename).group('name') == entry.get('name')]
        if entry.get('status') == 'off':
            if files:
                entry.set('current_status', 'on')
                return False
            else:
                return True
        else:
            if files:
                return True
            else:
                entry.set('current_status', 'off')
                return False

    def InstallService(self, entry):
        '''Install Service for entry'''
        cmdrc = 1
        self.logger.info("Installing Service %s" % (entry.get('name')))
        try:
            os.stat('/etc/init.d/%s' % entry.get('name'))
        except OSError:
            self.logger.debug("Init script for service %s does not exist" % entry.get('name'))
            return False
        
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                self.logger.info("Disabling service %s" % (entry.get('name')))
            else:
                self.saferun("/etc/init.d/%s stop" % (entry.get('name')))
                cmdrc = self.saferun("/usr/sbin/update-rc.d -f %s remove" % entry.get('name'))[0]
        else:
            if self.setup['dryrun']:
                self.logger.info("Enabling service %s" % (entry.attrib['name']))
            else:
                cmdrc = self.saferun("/usr/sbin/update-rc.d %s defaults" % (entry.attrib['name']))[0]
        if cmdrc:
            return False
        return True

    def VerifyPackage(self, entry, modlist):
        '''Verify package for entry'''
        if not entry.attrib.has_key('version'):
            self.logger.info("Cannot verify unversioned package %s" %
                             (entry.attrib['name']))
            return False
        if self.installed.has_key(entry.attrib['name']):
            if self.installed[entry.attrib['name']] == entry.attrib['version']:
                if not self.setup['quick']:
                    output = self.saferun("/usr/bin/debsums -s %s" % entry.get('name'))[1]
                    if [filename for filename in output if filename not in modlist]:
                        return False
                return True
            else:
                entry.set('current_version', self.installed[entry.get('name')])
                return False
        entry.set('current_exists', 'false')
        return False

    def Inventory(self):
        '''Do standard inventory plus debian extra service check'''
        Bcfg2.Client.Toolset.Toolset.Inventory(self)
        allsrv = []
        [allsrv.append(self.svcre.match(fname).group('name')) for fname in
         glob.glob("/etc/rc[12345].d/S*") if self.svcre.match(fname).group('name') not in allsrv]
        self.logger.debug("Found active services:")
        self.logger.debug(allsrv)
        csrv = self.cfg.findall(".//Service")
        [allsrv.remove(svc.get('name')) for svc in csrv if
         svc.get('status') == 'on' and svc.get('name') in allsrv]
        self.extra_services = allsrv

    def HandleExtra(self):
        '''Deal with extra configuration detected'''
        if self.setup['dryrun']:
            return
        
        if len(self.pkgwork['remove']) > 0:
            if self.setup['remove'] in ['all', 'packages']:
                self.logger.info('Removing packages:')
                self.logger.info(self.pkgwork['remove'])
                if not self.saferun("apt-get remove -y --force-yes %s" % " ".join(self.pkgwork['remove']))[0]:
                    self.pkgwork['remove'] = []
            else:
                if not self.setup['bundle']:
                    self.logger.info("Need to remove packages:")
                    self.logger.info(self.pkgwork['remove'])
                
        if len(self.extra_services) > 0:
            if self.setup['remove'] in ['all', 'services']:
                self.logger.info('Removing services:')
                self.logger.info(self.extra_services)
                [self.extra_services.remove(serv) for serv in self.extra_services if
                 not self.saferun("rm -f /etc/rc*.d/S??%s" % serv)[0]]
            else:
                if not self.setup['bundle']:
                    self.logger.info('Need to remove services:')
                    self.logger.info(self.extra_services)
        
