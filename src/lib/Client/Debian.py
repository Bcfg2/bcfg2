# This is the bcfg2 support for debian
# $Id $
from glob import glob
from os import environ, stat, system
from popen2 import Popen4
from string import split
from sys import argv

import apt_pkg

from Toolset import Toolset

def Detect():
    try:
        stat('/etc/debian_version')
        return True
    except OSError:
        return False

class Debian(Toolset):
    __important__ = ["/etc/apt/sources.list", "/var/cache/debconf/config.dat", \
                     "/var/cache/debconf/templates.dat"]

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        #system("dpkg --configure -a")
        if not self.setup['build']:
            system("dpkg-reconfigure -f noninteractive debconf")
        system("apt-get -q=2 -y update")
        environ["DEBIAN_FRONTEND"]='noninteractive'
        self.Refresh()

    def Refresh(self):
        apt_pkg.init()
        self.cache = apt_pkg.GetCache()
        self.installed = {}
        for pkg in self.cache.Packages:
            if pkg.CurrentVer:
                self.installed[pkg.Name] = pkg.CurrentVer.VerStr

    def VerifyService(self, entry):
        if entry.attrib['status'] == 'off':
            cmd = Popen4("/usr/sbin/update-rc.d -n -f %s remove"%(entry.attrib['name']))
            num = 1
        else:
            cmd = Popen4("/usr/sbin/update-rc.d -n -f %s remove"%(entry.attrib['name']))
            num = 2
        cstat = cmd.poll()
        output = ''
        while cstat == -1:
            output += cmd.fromchild.read()
            cstat = cmd.poll() >> 8
        if len(filter(lambda x:x, split(output, '\n'))) > num:
            return False
        return True

    def InstallService(self, entry):
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling service %s"%(entry.attrib['name'])
                rc = 1
            else:
                rc = system("update-rc.d -f %s remove"%entry.attrib['name'])
        else:
            if self.setup['dryrun']:
                print "Enabling service %s"%(entry.attrib['name'])
                rc = 1
            else:
                rc = system("update-rc.d %s defaults"%(entry.attrib['name']))
        if rc:
            return False
        return True

    def VerifyPackage(self, entry, modlist=[]):
        if self.installed.has_key(entry.attrib['name']):
            if self.installed[entry.attrib['name']] == entry.attrib['version']:
                if not self.setup['quick']:
                    cmd = Popen4("debsums -s %s"%(entry.attrib['name']))
                    cstat = cmd.poll()
                    output = cmd.fromchild.read()
                    while cstat == -1:
                        output += cmd.fromchild.read()
                        cstat = cmd.poll()
                    output = filter(lambda x:x, split(output, '\n'))
                    if [x for x in output if x not in modlist]:
                        return False
                return True
        return False

    def InstallPackages(self, entries):
        for e in entries:
            system("apt-get --reinstall -q=2 -y install %s=%s"%(e.attrib['name'],e.attrib['version']))

    def InstallPackage(self, entry):
        if self.setup['dryrun'] or self.setup['verbose']:
            print "Installing package %s %s"%(entry.attrib['name'], entry.attrib['version'])
            if self.setup['dryrun']:
                return False
        else:
            # implement package installation here
            return False

    def GetInstalledConfigs(self):
        # returns a list of installed config files
        ret = []
        for a in map(lambda x:split(open(x).read(),"\n"),glob("/var/lib/dpkg/info/*.conffiles")):
            ret += a
        return ret
