# This is the bcfg2 support for redhat
# $Id: $

from os import popen, system
from re import compile

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

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.pkgtodo = []

    def VerifyPackage(self, entry):
        return False

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

    def InstallPackage(self, entry):
        return False

    def Commit(self):
        # install packages from pkgtodo
        
        self.pkgtodo = []

