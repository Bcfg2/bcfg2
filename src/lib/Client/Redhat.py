# This is the bcfg2 support for redhat
# $Id: $

from os import popen, system
from popen2 import Popen4
from re import compile
from string import join

from Toolset import Toolset

def Detect():
    # until the code works
    return False

class Redhat(Toolset):
    '''This class implelements support for rpm packages and standard chkconfig services'''
    chkre=compile("(?P<name>\S+)\s+(?P<status>0:(?P<level0>\S+)\s+1:(?P<level1>\S+)\s+2:(?P<level2>\S+)\s+3:(?P<level3>\S+)\s+4:(?P<level4>\S+)\s+5:(?P<level5>\S+)\s+6:(?P<level6>\S+))")
    onre=compile(".*on.*")
    offre=compile(".*off.*")
    xre=compile("(?P<name>\S+)\s+(?P<status>\S+)")
    rpmcmd = "rpm --oldpackage --replacepkgs --quiet -U %s"

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.pkgtodo = []

    def VerifyService(self, entry):
        ckline = popen("/sbin/chkconfig --list %s"%entry.attrib['name']).readlines()
        if len(ckline) > 1:
            print "got too many lines from for service %s"%(entry.attrib['name'])
            return False
        else:
            if entry.attrib['type'] == 'chkconfig':
                cstatus = chkre.match(ckline[0]).group('status')
                if entry.attrib['status'] == 'off':
                    if onre.match(cstatus) == None:
                        return True
                    else:
                        return False
                else: # status == on
                    if not onre.match(cstatus):
                        return False
                    else:
                        levels = popen("grep chkconfig /etc/init.d/%s | awk '{print $3}' "%(name)).readlines()[0]
                        if levels[0] == '-' : levels = '345'
                        for i in range(7):
                            if str(i) in levels:
                                if cdata[i] == 'off':
                                    return False
                            else:
                                if cdata[i] == 'on':
                                    return False
                        if i == 6:
                            return True
            elif entry.attrib['type'] == 'xinetd':
                if xre.match(ckline[0]).group("status") == entry.attrib['status']:
                    return True
        return False
    
    def InstallService(self, entry):
        system("/sbin/chkconfig --add %s"%(entry.attrib['name']))
        if status == 'off':
            rc = system("/sbin/chkconfig --level 0123456 %s %s"%(entry.attrib['name'],entry.attrib['status']))
        else:
            rc = system("/sbin/chkconfig %s %s"%(entry.attrib['name'],entry.attrib['status']))
        if rc == 0:
            return True
        else:
            return False

    def VerifyPackage(self, entry, modlist = []):
        instp=Popen4("rpm -qi %s-%s"%(entry.attrib['name'],entry.attrib['version']))
        istat=instp.wait()/256
        if istat == 0:
            if entry.attrib.get('verify', 'true') == 'true':
                if self.setup['quick']:
                    return True
                verp=Popen4("rpm --verify --nomd5 -q %s-%s"%(entry.attrib['name'],entry.attrib['version']), bufsize=16384)
                odata=''
                vstat=verp.poll()
                while vstat == -1:
                    odata+=verp.fromchild.read()
                    vstat=verp.poll() >> 8
                output=filter(lambda x:x,odata.split('\n'))
                if vstat == 0:
                    return True
                else:
                    if len([x for x in output if x.split()[-1] not in modlist]) == 0:
                        return True
        return False

    def InstallPackage(self, entry):
        self.pkgtodo.append(entry)
        return False

    def Commit(self, entrystate):
        # try single install
        rc = system(self.rpmcmd%(join(map(lambda x:x.attrib['url'], self.pkgtodo))))
        if rc == 0:
            # set state == True for all just-installed packages
            for pkg in self.pkgtodo:
                entrystate[x] = True
            self.pkgtodo = []
        else:
            # fall back to single package installs
            oldlen = len(self.pkgtodo) + 1
            while oldlen > len(self.pkgtodo):
                oldlen = len(self.pkgtodo)
                for entry in self.pkgtodo:
                    rc = system(self.rpmcmd%(entry.attrib['url']))
                    if rc == 0:
                        entrystate[entry] = True
                        self.pkgtodo.remove(entry)
                    else:
                        if self.setup['verbose']:
                            print "package %s-%s failed to install"%(entry.attrib['name'], entry.attrib['version'])


