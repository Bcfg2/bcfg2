# This is the bcfg2 support for redhat
# $Id: $

'''This is redhat client support'''
__revision__ = '$Revision$'

from os import popen, system
from popen2 import Popen4

from Bcfg2.Client.Toolset import Toolset

class Redhat(Toolset):
    '''This class implelements support for rpm packages and standard chkconfig services'''
    rpmcmd = "rpm --oldpackage --replacepkgs --quiet -U %s"

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.pkgtodo = []

    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        srvdata = popen("/sbin/chkconfig --list %s"%entry.attrib['name']).readlines()[0].split()
        if entry.attrib['type'] == 'xinetd':
            if entry.attrib['status'] == srvdata[1]:
                return True
            else:
                return False

        # chkconfig/init.d service
        if entry.attrib['status'] == 'off':
            for level in srvdata[1:]:
                if level.split(':')[1] != 'off':
                    return False
            return True
        else:
            # services should be on for 2345
            for level in srvdata[1:]:
                [num, status] = level.split(':')
                if num in '2345':
                    if status == 'off':
                        return False
                else:
                    if status == 'on':
                        return False
            return True
    
    def InstallService(self, entry):
        '''Install Service entry'''
        system("/sbin/chkconfig --add %s"%(entry.attrib['name']))
        if entry.attrib['status'] == 'off':
            cmdrc = system("/sbin/chkconfig --level 0123456 %s %s" % (entry.attrib['name'], entry.attrib['status']))
        else:
            cmdrc = system("/sbin/chkconfig %s %s" %
                        (entry.attrib['name'], entry.attrib['status']))
        if cmdrc == 0:
            return True
        else:
            return False

    def VerifyPackage(self, entry, modlist = []):
        '''Verify Package status for entry'''
        instp = Popen4("rpm -qi %s-%s" % (entry.attrib['name'], entry.attrib['version']))
        istat = instp.wait()/256
        if istat == 0:
            if entry.attrib.get('verify', 'true') == 'true':
                if self.setup['quick']:
                    return True
                verp = Popen4("rpm --verify --nomd5 -q %s-%s" %
                              (entry.attrib['name'],entry.attrib['version']), bufsize=16384)
                odata = ''
                vstat = verp.poll()
                while vstat == -1:
                    odata += verp.fromchild.read()
                    vstat = verp.poll() >> 8
                output = [line for line in odata.split("\n") if line]
                if vstat == 0:
                    return True
                else:
                    if len([name for name in output if name.split()[-1] not in modlist]):
                        return True
        return False

    def InstallPackage(self, entry):
        '''Install Package entry'''
        self.pkgtodo.append(entry)
        return False

    def Install(self):
        '''Fix detected misconfigurations'''
        # try single install
        cmdrc = system(self.rpmcmd % (" ".join([pkg.get('url') for pkg in self.pkgtodo])))
        if cmdrc == 0:
            # set state == True for all just-installed packages
            for pkg in self.pkgtodo:
                self.states[pkg] = True
            self.pkgtodo = []
        else:
            # fall back to single package installs
            oldlen = len(self.pkgtodo) + 1
            while oldlen > len(self.pkgtodo):
                oldlen = len(self.pkgtodo)
                for entry in self.pkgtodo:
                    cmdrc = system(self.rpmcmd % (entry.get('url')))
                    if cmdrc == 0:
                        self.states[entry] = True
                        self.pkgtodo.remove(entry)
                    else:
                        if self.setup['verbose']:
                            print "package %s-%s failed to install" % (entry.get('name'), entry.get('version'))


