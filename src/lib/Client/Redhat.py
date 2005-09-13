# This is the bcfg2 support for redhat
# $Id: $

'''This is redhat client support'''
__revision__ = '$Revision$'

from os import popen, system
from popen2 import Popen4

from Bcfg2.Client.Toolset import Toolset

class Redhat(Toolset):
    '''This class implelements support for rpm packages and standard chkconfig services'''
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

        # Build list of packages
        instp = popen("rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE}\n'")
        for line in instp:
            [name, version] = line.split(' ')
            self.installed[name] = version[:-1]

    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        try:
            srvdata = popen("/sbin/chkconfig --list %s"%entry.attrib['name']).readlines()[0].split()
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            return False
        if entry.attrib['type'] == 'xinetd':
            return entry.attrib['status'] == srvdata[1]

        onlevels = [level.split(':')[0] for level in srvdata[1:] if level.split(':')[1] == 'on']

        # chkconfig/init.d service
        if entry.get('status') == 'on':
            return len(onlevels) > 0
        else:
            return len(onlevels) == 0
    
    def InstallService(self, entry):
        '''Install Service entry'''
        system("/sbin/chkconfig --add %s"%(entry.attrib['name']))
        self.CondPrint('verbose', "Installing Service %s" % (entry.get('name')))
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling server %s" % (entry.get('name'))
            else:
                cmdrc = system("/sbin/chkconfig %s %s" % (entry.attrib['name'], entry.attrib['status']))
        else:
            if self.setup['dryrun']:
                print "Enabling server %s" % (entry.get('name'))
            else:
                cmdrc = system("/sbin/chkconfig %s %s" %
                            (entry.attrib['name'], entry.attrib['status']))
        if cmdrc == 0:
            return True
        else:
            return False

    def VerifyPackage(self, entry, modlist):
        '''Verify Package status for entry'''
        if not entry.get('version'):
            print "Can't install package %s, not enough data." % (entry.get('name'))
            return False
        if self.installed.has_key(entry.get('name')):
            if entry.get('version') == self.installed[entry.get('name')]:
                if (self.setup['quick'] or (entry.get('verify', 'true') == 'false')):
                    return True
            else:
                self.CondPrint('debug', "Package %s: wrong version installed. want %s have %s" %
                               (entry.get('name'), entry.get('version'), self.installed[entry.get('name')]))
                return False
        else:
            self.CondPrint('debug', "Package %s: not installed" % (entry.get('name')))
            return False

        verp = Popen4("rpm --verify -q %s-%s" %
                      (entry.get('name'),entry.get('version')), bufsize=16384)
        odata = verp.fromchild.read()
        vstat = verp.poll()
        while vstat == -1:
            odata += verp.fromchild.read()
            vstat = verp.poll()
            output = [line for line in odata.split("\n") if line]
        if vstat == 0:
            return True
        else:
            if len([name for name in output if name.split()[-1] not in modlist]):
                return True
            else:
                self.CondPrint('debug',
                               "Package %s content verification failed" % entry.get('name'))
        return False
