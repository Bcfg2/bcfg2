'''This provides bcfg2 support for Gentoo'''
__revision__ = '$Revision$'

from os import popen, system, stat
from popen2 import Popen4
from glob import glob
from re import match, compile as regcompile

from Bcfg2.Client.Toolset import Toolset

class Gentoo(Toolset):
    '''This class implelements support for Gentoo binary packages and standard /etc/init.d services'''
    pkgtool = {'emerge':("/usr/bin/emerge --quiet --nospinner --usepkg --getbinpkg %s", ("%s-%s", ['name', 'version']))}

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.cfg = cfg
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}
        self.installed = {}
        self.extra_services = []
        self.Refresh()
        system("emerge sync")

    def Refresh(self):
        '''Refresh memory hashes of packages'''
        self.installed = {}

        splitter = regcompile('([\w\-\+]+)-([\d].*)')

        # Build list of packages
        instp =  [splitter.match(fname.split('/')[-1].replace('.ebuild','')).groups()
                  for fname in glob('/var/db/pkg/*/*/*.ebuild')]
        for info in instp:
            self.installed["%s-%s" % info] = info[1]

    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        runlevels = popen("/bin/rc-status --list").readlines()
        try:
            crunlevels = popen("/sbin/rc-update show | grep %s" % entry.attrib['name']).readlines()[0].split()[2:]
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            return False

        if entry.get('status') == 'off':
            if len(crunlevels) == 0:
                return True
        elif entry.get('status') == 'on':
            if len(crunlevels) > 0:
                return True
        return False
                
    def InstallService(self, entry):
        '''Install Service entry'''
        
        self.CondPrint('verbose', "Installing Service %s" % (entry.get('name')))
        try:
            stat('/etc/init.d/%s' % entry.get('name'))
        except OSError:
            self.CondPrint('debug', "Init script for service %s does not exist" % entry.get('name'))
            return False
        
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling Service %s" % (entry.get('name'))
            else:
                cmdrc = system("/sbin/rc-update del %s %s" % (entry.attrib['name'], entry.attrib['runlevels']))
        else:
            if self.setup['dryrun']:
                print "Enabling Service %s" % (entry.attrib['name'])
            else:
                cmdrc = system("/sbin/rc-update add %s %s" % (entry.attrib['name'], entry.attrib['runlevels']))
        if cmdrc:
            return False
        return True

    def VerifyPackage(self, entry, modlist):
        '''Verify Package status for entry'''
        if not (entry.get('name') and entry.get('version')):
            print "Can't verify package, not enough data."
            return False

        installed_package = popen("/usr/bin/qpkg --no-color --installed --verbose %s-%s" %
                                  (entry.get('name'), entry.get('version'))).readlines()
        if installed_package:
            installed_package = installed_package[0].strip("\n").split('/')[-1]
            if installed_package != "%s-%s" % (entry.get('name'), entry.get('version')):
                self.CondPrint('debug', "Package %s-%s version incorrect" % (entry.get('name'), entry.get('version')))
            if entry.attrib.get('verify', 'true') == 'true':
                if self.setup['quick']:
                    return True
                verp = Popen4("/usr/bin/qpkg --no-color --check %s-%s" %
                              (entry.get('name'), entry.get('version')), bufsize=16384)
                odata = verp.fromchild.read()
                vstat = verp.poll()
                while vstat == -1:
                    odata += verp.fromchild.read()
                    vstat = verp.poll()
                output = [line for line in odata.split("\n") if line]
                differences = output[-1]
                
                if match("^0/", differences):
                    return True
                else:
                    for line in output[1:-1]:
                        if line.split()[0] not in modlist:
                            self.CondPrint('debug', "Package %s content verification failed" % (entry.get('name')))
                            return False
                    return True
        return False

    def Inventory(self):
        '''Do standard inventory plus debian extra service check'''
        Toolset.Inventory(self)
        allsrv = [ srv.split('/')[-1] for srv in glob('/etc/init.d/*')]
        csrv = self.cfg.findall(".//Service")
        [allsrv.remove(svc.get('name')) for svc in csrv if svc.get('status') == 'on' and svc.get('name') in allsrv]
        self.extra_services = allsrv

    def HandleExtra(self):
        '''Deal with extra configuration detected'''
        if len(self.pkgwork) > 0:
            if self.setup['remove'] in ['all', 'packages']:
                self.CondPrint('verbose', "Removing packages: %s" % (self.pkgwork['remove']))
                system("/usr/bin/emerge --quiet --nospinner unmerge %s" % " ".join(self.pkgwork['remove']))
            else:
                self.CondPrint('verbose', "Need to remove packages: %s" % (self.pkgwork['remove']))
                if len(self.extra_services) > 0:
                    if self.setup['remove'] in ['all', 'services']:
                        self.CondPrint('verbose', "Removing services: %s" % (self.extra_services))
                        for service in self.extra_services:
                            system("/sbin/rc-update del %s" % service)
                    else:
                        self.CondPrint('verbose', "Need to remove services: %s" % (self.extra_services))
