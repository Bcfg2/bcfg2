#!/usr/bin/env python
'''This is the bcfg2 support for debian'''
__revision__ = '$Revision$'

from copy import deepcopy
from glob import glob
from os import environ, stat, system
from popen2 import Popen4

import apt_pkg

from Bcfg2.Client.Toolset import Toolset

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
        environ["DEBIAN_FRONTEND"] = 'noninteractive'
        system("dpkg --configure -a")
        if not self.setup['build']:
            system("dpkg-reconfigure -f noninteractive debconf < /dev/null")
        system("apt-get -q=2 -y update")
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
        files = glob("/etc/rc*.d/*%s" % (entry.get('name')))
        if entry.get('status') == 'off':
            if files:
                return False
            else:
                return True
        else:
            if files:
                return True
            else:
                return False

    def InstallService(self, entry):
        if self.setup['verbose']:
            print "Installing Service %s" % (entry.get('name'))
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling service %s" % (entry.get('name'))
                return False
            else:
                rc = system("update-rc.d -f %s remove" % entry.get('name'))
        else:
            if self.setup['dryrun']:
                print "Enabling service %s" % (entry.attrib['name'])
                return False
            else:
                rc = system("update-rc.d %s defaults" % (entry.attrib['name']))
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
                    output = [x for x in output.split('\n') if x]
                    if [x for x in output if x not in modlist]:
                        return False
                return True
        return False

    def InstallPackage(self, entry):
        if not entry.attrib.has_key('version'):
            print "Package entry for %s is malformed" % (entry.attrib['name'])
        if self.setup['dryrun'] or self.setup['verbose']:
            print "Installing package %s %s" % (entry.attrib['name'], entry.attrib['version'])
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
            if self.states.get(entry, True):
                # package entry verifies
                del all[pkg]
            else:
                if all.has_key(pkg):
                    # wrong version
                    self.pkgwork['update'].append(entry)
                else:
                    # new pkg
                    self.pkgwork['add'].append(entry)

        # pkgwork contains all one-way verification data now
        # all data remaining in all is extra packages
        
    def Install(self):
        print "Installing"
        cmd = "apt-get --reinstall -q=2 -y install %s"
        print "Need to remove:", self.pkgwork['remove']
        self.setup['quick'] = True

        # build up work queue
        work = self.pkgwork['add'] + self.pkgwork['update']
        # add non-package entries
        work += [x for x in self.states if x.tag != 'Package' and not self.states[x]]

        left = len(work)
        old = left + 1
        count = 1
        
        while ((0 < left < old) and (count < 20)):
            if self.setup['verbose']:
                print "Starting Pass: %s" % (count)
                print "%s new, %s update, %s remove" % (len(self.pkgwork['add']),
                                                        len(self.pkgwork['update']), len(self.pkgwork['remove']))
            count = count + 1
            old = left
            packages = [x for x in work if x.tag == 'Package']
            
            # try single large install
            rc = system(cmd % " ".join(["%s=%s" % (x.get('name'), x.get('version', 'dummy')) for x in packages]))

            if rc == 0:
                # set all states to true and flush workqueues
                for pkg in packages:
                    self.states[pkg] = True
                    work.remove(pkg)
                self.Refresh()
            else:
                # do single pass installs
                system("dpkg --configure --pending")
                self.Refresh()
                for pkg in packages:
                    # handle state tracking updates
                    if self.VerifyPackage(pkg):
                        self.states[pkg] = True
                        work.remove(pkg)
                    else:
                        rc = system(cmd % ("%s=%s" % (pkg.get('name'), pkg.get('version'))))
                        if rc == 0:
                            self.states[pkg] = True
                            work.remove(pkg)
                        else:
                            print "Failed to install package %s" % (pkg.get('name'))

            for nonpkg in [x for x in work if x.tag != 'Package']:
                self.InstallEntry(nonpkg)
                if self.states[nonpkg]:
                    work.remove(nonpkg)

            left = len(work)
