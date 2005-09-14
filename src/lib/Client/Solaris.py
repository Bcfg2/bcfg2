# This is the bcfg2 support for solaris
'''This provides bcfg2 support for Solaris'''
__revision__ = '$Revision$'

from glob import glob
from os import popen, stat, system
from popen2 import Popen4
from re import compile as regcompile

from Bcfg2.Client.Toolset import Toolset

class Solaris(Toolset):
    '''This class implelements support for SYSV/blastware/encap packages
    and standard SMF services'''
    pkgtool = {'sysv':("/usr/sbin/pkgadd -d %s -n all", ("%s", ["url"])),
               'blast':("/opt/csw/bin/pkg-get install %s", ("%s", ["name"])),
               'encap':("/local/sbin/epkg -l -q %s", ("%s", ["url"]))}
    splitter = regcompile('.*/(?P<name>[\w-]+)\-(?P<version>[\w\.-]+)')
    ptypes = {}
    
    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.extra_services = []
        try:
            stat("/opt/csw/bin/pkg-get")
            system("/opt/csw/bin/pkg-get -U > /dev/null")
        except OSError:
            pass
        self.Refresh()
        for pkg in [cpkg for cpkg in self.cfg.findall(".//Package") if not cpkg.attrib.has_key('type')]:
            pkg.set('type', 'sysv')
            
    def Refresh(self):
        '''Refresh memory hashes of packages'''
        self.installed = {}
        self.ptypes = {}
        # Build list of packages
        instp = popen("/usr/bin/pkginfo -x")
        lines = instp.readlines()
        while (lines):
            l1 = lines.pop()
            l2 = lines.pop()
            name = l2.split()[0]
            version = l1.split()[1]
            self.installed[name] = version
            self.ptypes[name] = 'sysv'
        # try to find encap packages
        for pkg in glob("/local/encap/*"):
            match = self.splitter.match(pkg)
            if match:
                self.installed[match.group('name')] = match.group('version')
                self.ptypes[match.group('name')] = 'encap'
            else:
                print "Failed to split name %s" % pkg

    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        try:
            srvdata = popen("/usr/bin/svcs -H -o STA %s" % entry.attrib['name']).readlines()[0].split()
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            return False

        if entry.get('status') == 'on':
            return srvdata[0] == 'ON'
        else:
            return srvdata[0] in ['OFF', 'UN', 'MNT', 'DIS', 'DGD']

    def InstallService(self, entry):
        '''Install Service entry'''
        system("/usr/sbin/svcadm enable -r %s" % (entry.attrib['name']))
        self.CondPrint('verbose', "Installing Service %s" % (entry.get('name')))
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling Service %s" % (entry.get('name'))
            else:
                cmdrc = system("/usr/sbin/svcadm disable %s" % (entry.attrib['name']))
        else:
            if self.setup['dryrun']:
                print "Enabling Service %s" % (entry.attrib['name'])
            else:
                cmdrc = system("/usr/sbin/svcadm enable %s" % (entry.attrib['name']))
        if cmdrc == 0:
            return True
        else:
            return False

    def VerifyPackage(self, entry, modlist):
        '''Verify Package status for entry'''
        if not (entry.get('name') and entry.get('version')):
            print "Can't verify package, not enough data."
            return False
        if entry.get('type') in ['sysv', 'blast']:
            cmdrc = system("/usr/bin/pkginfo -q -v \"%s\" %s" % (entry.get('version'), entry.get('name')))
        elif entry.get('type') in ['encap']:
            cmdrc = system("/local/sbin/epkg -q -k %s-%s >/dev/null" %
                           (entry.get('name'), entry.get('version')))
        if cmdrc != 0:
            self.CondPrint('debug', "Package %s version incorrect" % entry.get('name'))
        else:
            if entry.attrib.get('verify', 'true') == 'true':
                if self.setup['quick'] or entry.get('type') == 'encap':
                    return True
                verp = Popen4("/usr/sbin/pkgchk -n %s" % (entry.get('name')), bufsize=16384)
                odata = verp.fromchild.read()
                vstat = verp.poll()
                while vstat == -1:
                    odata += verp.fromchild.read()
                    vstat = verp.poll()
                output = [line for line in odata.split("\n") if line[:5] == 'ERROR']
                if vstat == 0:
                    return True
                else:
                    if len([name for name in output if name.split()[-1] not in modlist]):
                        return True
                    else:
                        self.CondPrint('debug', "Package %s content verification failed" % (entry.get('name')))
        return False

    def Inventory(self):
        '''Do standard inventory plus debian extra service check'''
        Toolset.Inventory(self)
        allsrv = [name for name, version in [ x.strip().split() for x in
                                              popen("/usr/bin/svcs -a -H -o SVC,STATE").readlines() ]
                  if version != 'disabled']
        csrv = self.cfg.findall(".//Service")
        #nsrv = [ r for r in [ popen("/usr/bin/svcs -H -o FMRI %s " % s).read().strip() for s in csrv ] if r ]
        [allsrv.remove(svc.get('name')) for svc in csrv if svc.get('status') == 'on' and svc.get('name') in allsrv]
        self.extra_services = allsrv

    def HandleExtra(self):
        '''Deal with extra configuration detected'''
        if len(self.pkgwork) > 0:
            if self.setup['remove'] in ['all', 'packages']:
                self.CondPrint('verbose', "Removing packages: %s" % (self.pkgwork['remove']))
                sysvrmpkgs = [pkg for pkg in self.pkgwork['remove'] if self.ptypes[pkg] == 'sysv']
                enrmpkgs = [pkg for pkg in self.pkgwork['remove'] if self.ptypes[pkg] == 'encap']
                if sysvrmpkgs:
                    system("/usr/sbin/pkgrm -n %s" % " ".join(sysvrmpkgs))
                if enrmpkgs:
                    system("/local/sbin/epkg -l -q -r %s" % " ".join(enrmpkgs))
            else:
                self.CondPrint('verbose', "Need to remove packages: %s" % (self.pkgwork['remove']))
                if len(self.extra_services) > 0:
                    if self.setup['remove'] in ['all', 'services']:
                        self.CondPrint('verbose', "Removing services: %s" % (self.extra_services))
                        for service in self.extra_services:
                            system("/usr/sbin/svcadm disable %s" % service)
                    else:
                        self.CondPrint('verbose', "Need to remove services: %s" % (self.extra_services))
