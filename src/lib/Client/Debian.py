'''This is the bcfg2 support for debian'''
__revision__ = '$Revision$'

from copy import deepcopy
from glob import glob
from os import environ, system
from popen2 import Popen4

import apt_pkg

from Bcfg2.Client.Toolset import Toolset

from elementtree.ElementTree import tostring

class Debian(Toolset):
    '''The Debian toolset implements package and service operations and inherits
    the rest from Toolset.Toolset'''
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
        self.installed = {}
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}        
        self.Refresh()

    def Refresh(self):
        '''Refresh memory hashes of packages'''
        apt_pkg.init()
        cache = apt_pkg.GetCache()
        self.installed = {}
        for pkg in cache.Packages:
            if pkg.CurrentVer:
                self.installed[pkg.Name] = pkg.CurrentVer.VerStr

    # implement entry (Verify|Install) ops
    
    def VerifyService(self, entry):
        '''Verify Service status for entry'''
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
        '''Install Service for entry'''
        self.CondPrint('verbose', "Installing Service %s" % (entry.get('name')))
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling service %s" % (entry.get('name'))
                return False
            else:
                cmdrc = system("update-rc.d -f %s remove" % entry.get('name'))
        else:
            if self.setup['dryrun']:
                print "Enabling service %s" % (entry.attrib['name'])
                return False
            else:
                cmdrc = system("update-rc.d %s defaults" % (entry.attrib['name']))
        if cmdrc:
            return False
        return True

    def VerifyPackage(self, entry, modlist=[]):
        '''Verify Package for entry'''
        if self.installed.has_key(entry.attrib['name']):
            if self.installed[entry.attrib['name']] == entry.attrib['version']:
                if not self.setup['quick']:
                    cmd = Popen4("debsums -s %s"%(entry.attrib['name']))
                    cstat = cmd.poll()
                    output = cmd.fromchild.read()
                    while cstat == -1:
                        output += cmd.fromchild.read()
                        cstat = cmd.poll()
                    output = [line for line in output.split('\n') if line]
                    if [filename for filename in output if filename not in modlist]:
                        return False
                return True
        return False

    def InstallPackage(self, entry):
        '''Install Package for entry - DEPRICATED'''
        if not entry.attrib.has_key('version'):
            print "Package entry for %s is malformed" % (entry.attrib['name'])
        if self.setup['dryrun'] or self.setup['verbose']:
            print "Installing package %s %s" % (entry.attrib['name'], entry.attrib['version'])
        return False

    def Inventory(self):
        '''Inventory system status'''
        self.CondPrint('verbose', "Inventorying system...")
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
                    del all[pkg]
                    self.pkgwork['update'].append(entry)
                else:
                    # new pkg
                    self.pkgwork['add'].append(entry)


        # pkgwork contains all one-way verification data now
        # all data remaining in all is extra packages
        self.pkgwork['remove'] = all.keys()
        
    def Install(self):
        '''Correct detected misconfigurations'''
        self.CondPrint("verbose", "Installing needed configuration changes")
        cmd = "apt-get --reinstall -q=2 -y install %s"
        print "Need to remove:", self.pkgwork['remove']
        self.setup['quick'] = True
        # need installed for bundle verification
        installed = []

        # build up work queue
        work = self.pkgwork['add'] + self.pkgwork['update']
        # add non-package entries
        work += [ent for ent in self.states if ent.tag != 'Package' and not self.states[ent]]

        left = len(work) + len(self.pkgwork['remove'])
        old = left + 1
        count = 1
        
        while ((0 < left < old) and (count < 20)):
            self.CondPrint('verbose', "Starting pass %s" % (count))
            self.CondPrint("verbose", "%s Entries left" % (len(work)))
            self.CondPrint('verbose', "%s new, %s update, %s remove" %
                           (len(self.pkgwork['add']), len(self.pkgwork['update']),
                            len(self.pkgwork['remove'])))
                           
            count = count + 1
            old = left

            self.CondPrint("verbose", "Installing Non Package entries")
            for nonpkg in [ent for ent in work if ent.tag != 'Package']:
                if nonpkg not in installed:
                    installed.append(nonpkg)
                self.InstallEntry(nonpkg)
                if self.states[nonpkg]:
                    work.remove(nonpkg)

            packages = [pkg for pkg in work if pkg.tag == 'Package']
            if packages:
                # try single large install
                self.CondPrint("verbose", "Trying single pass package install")
                cmdrc = system(cmd % " ".join(["%s=%s" % (pkg.get('name'), pkg.get('version', 'dummy'))
                                               for pkg in packages]))

                if cmdrc == 0:
                    self.CondPrint('verbose', "Single Pass Succeded")
                    # set all states to true and flush workqueues
                    for pkg in packages:
                        self.states[pkg] = True
                        work.remove(pkg)
                        if pkg not in installed:
                            installed.append(pkg)
                    self.Refresh()
                else:
                    self.CondPrint("verbose", "Single Pass Failed")
                    # do single pass installs
                    system("dpkg --configure --pending")
                    self.Refresh()
                    for pkg in packages:
                        # handle state tracking updates
                        if self.VerifyPackage(pkg):
                            self.CondPrint("verbose", "Forcing state to true for pkg %s" % (pkg.get('name')))
                            self.states[pkg] = True
                            work.remove(pkg)
                            installed.append(pkg)
                        else:
                            self.CondPrint("verbose", "Installing pkg %s version %s" %
                                           (pkg.get('name'), pkg.get('version')))
                            cmdrc = system(cmd % ("%s=%s" % (pkg.get('name'), pkg.get('version'))))
                            if cmdrc == 0:
                                self.states[pkg] = True
                                work.remove(pkg)
                                installed.append(pkg)
                            else:
                                self.CondPrint('verbose', "Failed to install package %s" % (pkg.get('name')))

            left = len(work) + len(self.pkgwork['remove'])

        # now we need to check bundle deps
        for entry in self.structures.keys():
            if entry.tag == 'Bundle':
                for new in installed:
                    if new in entry.getchildren():
                        self.CondPrint('verbose', "%s %s needs update" % (entry.tag, entry.get('name', '???')))
                        modfiles = [x.get('name') for x in entry.getchildren() if x.tag == 'ConfigFile']
                        for child in entry.getchildren():
                            if child.tag == 'Package':
                                self.VerifyPackage(child, modfiles)
                            else:
                                self.VerifyEntry(child)
                            self.CondPrint('debug', "Re-checking entry %s %s: %s" % (child.tag, child.get('name'), self.states[child]))
                        for svc in [x for x in entry.getchildren() if x.tag == 'Service']:
                            self.CondPrint('debug', "Restarting service %s" % (svc.get('name')))
                            system('/etc/init.d/%s restart > /dev/null' % (svc.get('name')))
            
            if [x for x in entry.getchildren() if not self.states[x]]:
                self.CondPrint('verbose', "%s %s incomplete" % (entry.tag, entry.name))
            else:
                self.structures[entry] = True
