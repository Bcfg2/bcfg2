# This is the bcfg2 support for solaris
'''This provides bcfg2 support for Solaris'''
__revision__ = '$Revision$'

from glob import glob
from os import stat, unlink
from re import compile as regcompile
from tempfile import mktemp

from Bcfg2.Client.Toolset import Toolset

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

class ToolsetImpl(Toolset):
    '''This class implelements support for SYSV/blastware/encap packages
    and standard SMF services'''
    pkgtool = {'sysv':("/usr/sbin/pkgadd %s -d %%s -n %%%%s", (("%s", ["name"]))),
               'blast':("/opt/csw/bin/pkg-get install %s", ("%s", ["name"])),
               'encap':("/local/sbin/epkg -l -q %s", ("%s", ["url"]))}
    splitter = regcompile('.*/(?P<name>[\w-]+)\-(?P<version>[\w\.-]+)')
    ptypes = {}
    __name__ = 'Solaris'
    
    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.extra_services = []
        self.snames = {}
        self.noaskname = mktemp()
        try:
            open(self.noaskname, 'w+').write(noask)
            self.pkgtool['sysv'] = (self.pkgtool['sysv'][0] % ("-a %s" % (self.noaskname)), self.pkgtool['sysv'][1])
        except:
            self.pkgtool['sysv'] = (self.pkgtool['sysv'][0] % (""), self.pkgtool['sysv'][1])
        try:
            stat("/opt/csw/bin/pkg-get")
            self.saferun("/opt/csw/bin/pkg-get -U > /dev/null")
        except OSError:
            pass
        self.Refresh()
        for pkg in [cpkg for cpkg in self.cfg.findall(".//Package") if not cpkg.attrib.has_key('type')]:
            pkg.set('type', 'sysv')
        for pkg in [cpkg for cpkg in self.cfg.findall(".//Package") if cpkg.get('type') == 'sysv']:
            if pkg.attrib.has_key('url'):
                pkg.set('url', '/'.join(pkg.get('url').split('/')[:-1]))
            pkg.set('type', "sysv-%s" % (pkg.get('url')))
            if not self.pkgtool.has_key(pkg.get('type')):
                self.pkgtool[pkg.get('type')] = (self.pkgtool['sysv'][0] % (pkg.get('url')),
                                                        self.pkgtool['sysv'][1])
            
    def Refresh(self):
        '''Refresh memory hashes of packages'''
        self.installed = {}
        self.ptypes = {}
        # Build list of packages
        lines = self.saferun("/usr/bin/pkginfo -x")[1]
        while lines:
            version = lines.pop().split()[1]
            pkg = lines.pop().split()[0]
            self.installed[pkg] = version
            self.ptypes[pkg] = 'sysv'
        # try to find encap packages
        for pkg in glob("/local/encap/*"):
            match = self.splitter.match(pkg)
            if match:
                self.installed[match.group('name')] = match.group('version')
                self.ptypes[match.group('name')] = 'encap'
            else:
                print "Failed to split name %s" % pkg
        print self.installed.keys()

    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        if not entry.attrib.has_key('FMRI'):
            (rc, name) = self.saferun("/usr/bin/svcs -H -o FMRI %s 2>/dev/null" % entry.get('name'))
            if name:
                entry.set('FMRI', name[0])
            else:
                self.CondPrint('verbose', 'Failed to locate FMRI for service %s' % entry.get('name'))
                return False
        if entry.get('FMRI')[:3] == 'lrc':
            filename = entry.get('FMRI').split('/')[-1]
            # this is a legacy service
            gname = "/etc/rc*.d/%s" % filename
            if glob(gname.replace('_', '.')):
                return entry.get('status') == 'on'
            else:
                return entry.get('status') == 'off'
        try:
            srvdata = self.saferun("/usr/bin/svcs -H -o STA %s" % entry.attrib['name'])[1][0].split()
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            return False

        if entry.get('status') == 'on':
            return srvdata[0] == 'ON'
        else:
            return srvdata[0] in ['OFF', 'UN', 'MNT', 'DIS', 'DGD']

    def InstallService(self, entry):
        '''Install Service entry'''
        if not entry.attrib.has_key('status'):
            self.CondPrint('verbose', 'Insufficient information for Service %s; cannot Install' % entry.get('name'))
            return False
        if not entry.attrib.has_key('FMRI'):
            name = self.saferun("/usr/bin/svcs -H -o FMRI %s 2>/dev/null" % entry.get('name'))[1]
            if name:
                entry.set('FMRI', name[0])
            else:
                self.CondPrint('verbose', 'Failed to locate FMRI for service %s' % entry.get('name'))
                return False
        self.CondPrint('verbose', "Installing Service %s" % (entry.get('name')))
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling Service %s" % (entry.get('name'))
            else:
                cmdrc = self.saferun("/usr/sbin/svcadm disable -r %s" % (entry.attrib['FMRI']))[0]
        else:
            if self.setup['dryrun']:
                print "Enabling Service %s" % (entry.attrib['name'])
            else:
                cmdrc = self.saferun("/usr/sbin/svcadm enable -r %s" % (entry.attrib['FMRI']))[0]
        return cmdrc == 0

    def VerifyPackage(self, entry, modlist):
        '''Verify Package status for entry'''
        if not entry.get('version'):
            self.CondPrint('verbose',
                           "Insufficient information of Package %s; cannot Verify" % entry.get('name'))
            return False
        if entry.get('type') in ['sysv', 'blast'] or entry.get('type')[:4] == 'sysv':
            cmdrc = self.saferun("/usr/bin/pkginfo -q -v \"%s\" %s" % (entry.get('version'), entry.get('name')))[0]
        elif entry.get('type') in ['encap']:
            cmdrc = self.saferun("/local/sbin/epkg -q -k %s-%s >/dev/null" %
                                 (entry.get('name'), entry.get('version')))[0]
        if cmdrc != 0:
            self.CondPrint('debug', "Package %s version incorrect" % entry.get('name'))
        else:
            if entry.attrib.get('verify', 'true') == 'true':
                if self.setup['quick'] or entry.get('type') == 'encap':
                    return True
                (vstat, odata) = self.saferun("/usr/sbin/pkgchk -n %s" % (entry.get('name')))
                if vstat == 0:
                    return True
                else:
                    output = [line for line in odata if line[:5] == 'ERROR']
                    if len([name for name in output if name.split()[-1] not in modlist]):
                        self.CondPrint('debug', "Package %s content verification failed" % (entry.get('name')))
                    else:
                        return True
        return False

    def Inventory(self):
        '''Do standard inventory plus debian extra service check'''
        Toolset.Inventory(self)
        allsrv = [name for name, version in [ srvc.strip().split() for srvc in
                                              self.saferun("/usr/bin/svcs -a -H -o FMRI,STATE")[1] ]
                  if version != 'disabled']
        csrv = self.cfg.findall(".//Service")
        # need to build a service name map. services map to a fullname if they are already installed
        for srv in csrv:
            name = self.saferun("/usr/bin/svcs -H -o FMRI %s 2>/dev/null" % srv.get('name'))[1]
            if name:
                srv.set('FMRI', name[0])
            else:
                self.CondPrint("verbose", "failed to locate FMRI for service %s" % srv.get('name'))
        #nsrv = [ r for r in [ popen("/usr/bin/svcs -H -o FMRI %s " % s).read().strip() for s in csrv ] if r ]
        [allsrv.remove(svc.get('FMRI')) for svc in csrv if
         svc.get('status') == 'on' and svc.get("FMRI") in allsrv]
        self.extra_services = allsrv

    def HandleExtra(self):
        '''Deal with extra configuration detected'''
        if len(self.pkgwork) > 0:
            if self.setup['remove'] in ['all', 'packages']:
                self.CondPrint('verbose', "Removing packages: %s" % (self.pkgwork['remove']))
                sysvrmpkgs = [pkg for pkg in self.pkgwork['remove'] if self.ptypes[pkg] == 'sysv']
                enrmpkgs = [pkg for pkg in self.pkgwork['remove'] if self.ptypes[pkg] == 'encap']
                if sysvrmpkgs:
                    if not self.saferun("/usr/sbin/pkgrm -n %s" % " ".join(sysvrmpkgs))[0]:
                        [self.pkgwork['remove'].remove(pkg) for pkg in sysvrmpkgs]
                if enrmpkgs:
                    if not self.saferun("/local/sbin/epkg -l -q -r %s" % " ".join(enrmpkgs))[0]:
                        [self.pkgwork['remove'].remove(pkg) for pkg in enrmpkgs]
            else:
                self.CondPrint('verbose', "Need to remove packages: %s" % (self.pkgwork['remove']))
                if len(self.extra_services) > 0:
                    if self.setup['remove'] in ['all', 'services']:
                        self.CondPrint('verbose', "Removing services: %s" % (self.extra_services))
                        for service in self.extra_services:
                            if not self.saferun("/usr/sbin/svcadm disable %s" % service)[0]:
                                self.extra_services.remove(service)
                    else:
                        self.CondPrint('verbose', "Need to remove services: %s" % (self.extra_services))

    def Install(self):
        '''Local install method handling noaskfiles'''
        Toolset.Install(self)
        try:
            unlink(self.noaskname)
        except:
            pass
