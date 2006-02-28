'''This provides bcfg2 support for Gentoo'''
__revision__ = '$Revision$'

import glob, os, re
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
        self.saferun("emerge sync")

    def Refresh(self):
        '''Refresh memory hashes of packages'''
        self.installed = {}

        splitter = re.compile('([\w\-\+]+)-([\d].*)')

        # Build list of packages
        instp =  [splitter.match(fname.split('/')[-1].replace('.ebuild','')).groups()
                  for fname in glob.glob('/var/db/pkg/*/*/*.ebuild')]
        for info in instp:
            self.installed["%s-%s" % info] = info[1]

    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        runlevels = self.saferun("/bin/rc-status --list")[1]
        try:
            crl = self.saferun("/sbin/rc-update show | grep %s" % entry.attrib['name'])[1][0].split()[2:]
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            return False

        if entry.get('status') == 'off':
            return len(crl) == 0
        elif entry.get('status') == 'on':
            return len(crl) > 0
        return False
                
    def InstallService(self, entry):
        '''Install Service entry'''
        
        self.logger.info("Installing Service %s" % (entry.get('name')))
        try:
            os.stat('/etc/init.d/%s' % entry.get('name'))
        except OSError:
            self.logger.debug("Init script for service %s does not exist" % entry.get('name'))
            return False
        
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                self.logger.info("Disabling Service %s" % (entry.get('name')))
            else:
                cmdrc = self.saferun("/sbin/rc-update del %s %s" % (entry.attrib['name'], entry.attrib['runlevels']))[0]
        else:
            if self.setup['dryrun']:
                self.logger.info("Enabling Service %s" % (entry.attrib['name']))
            else:
                cmdrc = self.saferun("/sbin/rc-update add %s %s" % (entry.attrib['name'], entry.attrib['runlevels']))[0]
        if cmdrc:
            return False
        return True

    def VerifyPackage(self, entry, modlist):
        '''Verify Package status for entry'''
        if not (entry.get('name') and entry.get('version')):
            self.logger.error("Can't verify package, not enough data.")
            return False

        installed_package = self.saferun("/usr/bin/qpkg --no-color --installed --verbose %s-%s" %
                                         (entry.get('name'), entry.get('version')))[1]
        if installed_package:
            installed_package = installed_package[0].strip("\n").split('/')[-1]
            if installed_package != "%s-%s" % (entry.get('name'), entry.get('version')):
                self.logger.debug("Package %s-%s version incorrect" % (entry.get('name'), entry.get('version')))
            if entry.attrib.get('verify', 'true') == 'true':
                if self.setup['quick']:
                    return True
                output = self.saferun("/usr/bin/qpkg --no-color --check %s-%s" %
                                      (entry.get('name'), entry.get('version')))[1]
                differences = output[-1]
                
                if re.match("^0/", differences):
                    return True
                else:
                    for line in output[1:-1]:
                        if line.split()[0] not in modlist:
                            self.logger.debug("Package %s content verification failed" % (entry.get('name')))
                            return False
                    return True
        return False

    def Inventory(self):
        '''Do standard inventory plus debian extra service check'''
        Toolset.Inventory(self)
        allsrv = [ srv.split('/')[-1] for srv in glob.glob('/etc/init.d/*')]
        csrv = self.cfg.findall(".//Service")
        [allsrv.remove(svc.get('name')) for svc in csrv if svc.get('status') == 'on' and svc.get('name') in allsrv]
        self.extra_services = allsrv

    def HandleExtra(self):
        '''Deal with extra configuration detected'''
        if len(self.pkgwork) > 0:
            if self.setup['remove'] in ['all', 'packages']:
                self.logger.info("Removing packages: %s" % (self.pkgwork['remove']))
                cmd = "/usr/bin/emerge --quiet --nospinner unmerge %s" % " ".join(self.pkgwork['remove'])
                self.saferun(cmd)
            else:
                self.logger.info("Need to remove packages: %s" % (self.pkgwork['remove']))
                if len(self.extra_services) > 0:
                    if self.setup['remove'] in ['all', 'services']:
                        self.logger.info("Removing services: %s" % (self.extra_services))
                        for service in self.extra_services:
                            self.saferun("/sbin/rc-update del %s" % service)
                    else:
                        self.logger.info("Need to remove services: %s" % (self.extra_services))
