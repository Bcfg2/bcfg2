# This is the bcfg2 support for debian
# $Id $

from copy import deepcopy
from glob import glob
from os import environ, stat, system
from popen2 import Popen4
from string import join, split
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
                     "/var/cache/debconf/templates.dat", '/etc/passwd', '/etc/group']

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        self.cfg = cfg
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

    # implement entry (Verify|Install) ops
    
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

    def InstallPackage(self, entry):
        if not entry.attrib.has_key('version'):
            print "Package entry for %s is malformed"%(entry.attrib['name'])
            return False
        
        if self.setup['dryrun'] or self.setup['verbose']:
            print "Installing package %s %s"%(entry.attrib['name'], entry.attrib['version'])

        if self.setup['dryrun']:
            return False
        else:
            # queue package for bulk installation
            self.pkgtodo.append(entry)
            return False

    def Inventory(self):
        print "In Inventory::"
        Toolset.Inventory(self)
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}
        all = deepcopy(self.installed)
        desired = {}
        for entry in self.cfg.findall(".//Package"):
            desired[entry.attrib['name']] = entry

        for pkg, entry in desired.iteritems():
            print pkg, 
            if self.states[entry]:
                # package entry verifies
                print "OK"
                del all[pkg]
            else:
                if all.has_key(pkg):
                    # wrong version
                    print "UPDATE"
                    self.pkgwork['update'].append(entry)
                else:
                    print "NEW"
                    # new pkg
                    self.pkgwork['add'].append(entry)
            
            if all.has_key(pkg):
                if all[pkg] != desired[pkg]:
                    # package version is wrong
                    self.pkgwork['update'].append(entry)
                del all[pkg]
                #del desired[pkg]
            else:
                # new package install
                self.pkgwork['add'].append(entry)
                #del desired[pkg]

        # pkgwork contains all one-way verification data now
        # all data remaining in all is extra packages
        
    def Install(self):
        print "Installing"
        cmd = "apt-get --reinstall -q=2 -y install %s"
        print "Need to remove:", self.pkgwork['remove']
        print "%s new, %s update, %s remove"%(len(self.pkgwork['add']),len(self.pkgwork['update']), len(self.pkgwork['remove']))
        # try single large install
        rc = system(cmd%join(map(lambda x:"%s=%s"%(x.attrib['name'], x.attrib['version']), self.pkgwork['add'] + self.pkgwork['update'])))
        if rc == 0:
            # set installed to true for pkgtodo
            for pkg in self.pkgwork['add'] + self.pkgwork['update']:
                self.states[x]=True
            self.pkgtodo = []
            self.Refresh()
        else:
            # do single pass installs
            system("dpkg --configure --pending")
            self.Refresh()
            work = self.pkgwork['add'] + self.pkgwork['update']
            for pkg in work:
                if self.VerifyPackage(pkg):
                    self.states[pkg] = True
                    #self.pkgtodo.remove(pkg)
            oldlen = len(work) + 1
            while (len(work) < oldlen):
                oldlen = len(work)
                for pkg in work:
                    print cmd%("%s=%s"%(pkg.attrib['name'], pkg.attrib['version']))
                    rc = system(cmd%("%s=%s"%(pkg.attrib['name'], pkg.attrib['version'])))
                    if rc == 0:
                        self.states[pkg] = True
                        work.remove(pkg)
                    else:
                        print "Failed to install package %s"%(pkg.attrib['name'])
        for entry in [x for x in self.states if not self.states[x] and x.tag != 'Package']:
            self.InstallEntry(entry)
