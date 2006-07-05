# This is the bcfg2 support for redhat
# $Id$

'''This is redhat client support'''
__revision__ = '$Revision$'

from Bcfg2.Client.Toolset import Toolset

class ToolsetImpl(Toolset):
    '''This class implelements support for rpm packages and standard chkconfig services'''
    __name__ = 'Redhat'
    pkgtool = {'rpm':("rpm --oldpackage --replacepkgs --quiet -U %s", ("%s", ["url"]))}

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}
        self.Refresh()
        for pkg in [cpkg for cpkg in self.cfg.findall(".//Package") if not cpkg.attrib.has_key('type')]:
            pkg.set('type', 'rpm')
        for srv in [csrv for csrv in self.cfg.findall(".//Service") if not csrv.attrib.has_key('type')]:
            srv.set('type', 'chkconfig')
        # relocation hack: we will define one pkgtool per relocation location
        for pkg in [cpkg for cpkg in self.cfg.findall('.//Package') if cpkg.attrib.has_key('reloc')]:
            ptoolname = "rpm-reloc-%s" % (pkg.get('reloc'))
            if not self.pkgtool.has_key(ptoolname):
                cmd = "rpm --relocate %s --oldpackage --replacepkgs --quiet -U %%s" % (pkg.get('reloc'))
                self.pkgtool[ptoolname] = (cmd, ("%s", ["url"]))
            pkg.set('type', ptoolname)


    def Refresh(self):
        '''Refresh memory hashes of packages'''
        self.installed = {}
        for line in self.saferun("rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE}\n'")[1]:
            (name, version) = line.split()
            self.installed[name] = version

    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        try:
            srvdata = self.saferun('/sbin/chkconfig --list %s | grep -v "unknown service"'
                                   % entry.attrib['name'])[1][0].split()
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            entry.set('current_status', 'off')
            return False
        if entry.attrib['type'] == 'xinetd':
            return entry.attrib['status'] == srvdata[1]

        try:
            onlevels = [level.split(':')[0] for level in srvdata[1:] if level.split(':')[1] == 'on']
        except IndexError:
            onlevels = []

        # chkconfig/init.d service
        if entry.get('status') == 'on':
            status = len(onlevels) > 0
        else:
            status = len(onlevels) == 0

        if not status:
            if entry.get('status') == 'on':
                entry.set('current_status', 'off')
            else:
                entry.set('current_status', 'on')
        return status

    def InstallService(self, entry):
        '''Install Service entry'''
        self.saferun("/sbin/chkconfig --add %s"%(entry.attrib['name']))
        self.logger.info("Installing Service %s" % (entry.get('name')))
        if not entry.get('status'):
            self.logger.error("Can't install service %s, not enough data" % (entry.get('name')))
            return False
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                self.logger.info("Disabling server %s" % (entry.get('name')))
            else:
                cmdrc = self.saferun("/sbin/chkconfig %s %s" % (entry.attrib['name'],
                                                                entry.attrib['status']))[0]
        else:
            if self.setup['dryrun']:
                self.logger.info("Enabling server %s" % (entry.get('name')))
            else:
                cmdrc = self.saferun("/sbin/chkconfig %s %s" %
                            (entry.attrib['name'], entry.attrib['status']))[0]
        return cmdrc == 0

    def VerifyPackage(self, entry, modlist):
        '''Verify Package status for entry'''
        if not entry.get('version'):
            self.logger.error("Can't install package %s, not enough data." % (entry.get('name')))
            return False
        rpm_options = []
        if entry.get('verify', 'false') == 'nomtime':
            self.logger.debug("Skipping mtime verification for package %s" % (entry.get('name')))
            rpm_options.append("--nomtime")
        if self.installed.has_key(entry.get('name')):
            if entry.get('version') == self.installed[entry.get('name')]:
                if entry.get('multiarch'):
                    archs = entry.get('multiarch').split()
                    info = self.saferun('rpm -q %s --qf "%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n"' % (entry.get('name')))[1]
                    while info:
                        (_, vers, arch) = info.pop()
                        if arch in archs:
                            archs.remove(arch)
                        else:
                            self.logger.error("Got pkg install for Package %s: arch %s" % (entry.get('name'), arch))
                            return False
                    if archs:
                        self.logger.error("Package %s not installed for arch: %s" % (entry.get('name'), archs))
                        return False
                if (self.setup['quick'] or (entry.get('verify', 'true') == 'false')):
                    if entry.get('verify', 'true') == 'false':
                        self.logger.debug("Skipping checksum verification for package %s" % (entry.get('name')))
                    return True
            else:
                self.logger.debug("Package %s: wrong version installed. want %s have %s" %
                                  (entry.get('name'), entry.get('version'), self.installed[entry.get('name')]))
                entry.set('current_version', self.installed[entry.get('name')])
                return False
        else:
            self.logger.debug("Package %s: not installed" % (entry.get('name')))
            entry.set('current_exists', 'false')
            return False

        (vstat, output) = self.saferun("rpm --verify -q %s %s-%s" % (" ".join(rpm_options), entry.get('name'), entry.get('version')))
        if vstat != 0:
            if [name for name in output if name.split()[-1] not in modlist]:
                self.logger.debug("Package %s content verification failed" % entry.get('name'))
                return False
        return True

    def HandleExtra(self):
        '''Deal with extra configuration detected'''
        if len(self.pkgwork['remove']) > 0:
            if self.setup['remove'] in ['all', 'packages']:
                self.logger.info("Removing packages: %s" % self.pkgwork['remove'])
                if not self.saferun("rpm --quiet -e %s" % " ".join(self.pkgwork['remove']))[0]:
                    self.pkgwork['remove'] = []
                    self.Refresh()
                    self.Inventory()
            else:
                self.logger.info("Need to remove packages:")
                self.logger.info(self.pkgwork['remove'])
        if len(self.extra_services) > 0:
            if self.setup['remove'] in ['all', 'services']:
                self.logger.info('Removing services:')
                self.logger.info(self.extra_services)
                for service in self.extra_services:
                    if not self.saferun("/sbin/chkconfig --level 123456 %s off" % service)[0]:
                        self.extra_services.remove(service)
                    self.logger.info("Failed to remove service %s" % (service))
            else:
                self.logger.info('Need to remove services:')
                self.logger.info(self.extra_services)
        
    def Inventory(self):
        '''Do standard inventory plus debian extra service check'''
        Toolset.Inventory(self)
        allsrv = [line.split()[0] for line in self.saferun("/sbin/chkconfig --list|grep :on")[1]]
        self.logger.debug('Found active services:')
        self.logger.debug(allsrv)
        csrv = self.cfg.findall(".//Service")
        [allsrv.remove(svc.get('name')) for svc in csrv if
         svc.get('status') == 'on' and svc.get('name') in allsrv]
        self.extra_services = allsrv
