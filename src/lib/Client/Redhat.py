# This is the bcfg2 support for redhat
# $Id: $

'''This is redhat client support'''
__revision__ = '$Revision$'

from copy import deepcopy
from os import popen, system
from popen2 import Popen4

from Bcfg2.Client.Toolset import Toolset

class Redhat(Toolset):
    '''This class implelements support for rpm packages and standard chkconfig services'''
    rpmcmd = "rpm --oldpackage --replacepkgs --quiet -U %s"

    def __init__(self, cfg, setup):
        Toolset.__init__(self, cfg, setup)
        #self.pkgtodo = []
        self.installed = {}
        self.installed_this_run = []
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}
        self.Refresh()

    def Refresh(self):
        '''Refresh memory hashes of packages'''
        self.installed = {}

        # Build list of packages
        instp = popen("rpm -qa --qf '%{NAME} %{VERSION}\n'")
        for line in instp:
            [name,version] = line.split(' ')
            self.installed[name] = version
        

    def VerifyService(self, entry):
        '''Verify Service status for entry'''
        try:
            srvdata = popen("/sbin/chkconfig --list %s"%entry.attrib['name']).readlines()[0].split()
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            return False
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
        self.CondPrint('verbose', "Installing Service %s" % (entry.get('name')))
        if entry.attrib['status'] == 'off':
            if self.setup['dryrun']:
                print "Disabling server %s" % (entry.get('name'))
            else:
                cmdrc = system("/sbin/chkconfig --level 0123456 %s %s" % (entry.attrib['name'], entry.attrib['status']))
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

    def VerifyPackage(self, entry, modlist = []):
        '''Verify Package status for entry'''
        if not (entry.get('name') and entry.get('version')):
            print "Can't install package, not enough data."
            return False
        instp = Popen4("rpm -qi %s-%s" % (entry.attrib['name'], entry.attrib['version']))
        istat = instp.wait()/256
        if istat == 0:
            if entry.attrib.get('verify', 'true') == 'true':
                if self.setup['quick']:
                    return True
                verp = Popen4("rpm --verify -q %s-%s" %
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

    def Inventory(self):
        '''Build up workqueue for installation'''
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
            


#    def InstallPackage(self, entry):
#        '''Install Package entry'''
#        self.pkgtodo.append(entry)
#        return False

    def Install(self):
        '''Fix detected misconfigurations'''
        self.CondPrint("verbose", "Installing needed configuration changes")
    
        # Dry run info
        self.CondPrint('dryrun', "Packages to update: %s" % (" ".join([pkg.get('name') for pkg in self.pkgwork['update']])))
        self.CondPrint('dryrun', "Packages to add: %s" % (" ".join([pkg.get('name') for pkg in self.pkgwork['add']])))
        self.CondPrint('dryrun', "Packages to remove %s" % (" ".join(self.pkgwork['remove'])))
        for entry in [entry for entry in self.states if (not self.states[entry]
                                                         and (entry.tag != 'Package'))]:
            self.CondPrint('dryrun', "Entry %s %s updated" % (entry.tag, entry.get('name')))
        if self.setup['dryrun']:
            return
        
        # build up work queue
        work = self.pkgwork['add'] + self.pkgwork['update']
        # add non-package entries
        work += [ent for ent in self.states if ent.tag != 'Package' and not self.states[ent]]

        # Counters
        ## Packages left to install
        left = len(work) + len(self.pkgwork['remove'])
        ## Packages installed in last review
        old = left + 1
        ## Loops gone through
        count = 1
        
        # Installation loop
        while ((0 < left < old) and (count < 20)):
            # Print pass info
            self.CondPrint('verbose', "Starting pass %s" % (count))
            self.CondPrint("verbose", "%s Entries left" % (len(work)))
            self.CondPrint('verbose', "%s new, %s update, %s remove" %
                           (len(self.pkgwork['add']), len(self.pkgwork['update']),
                            len(self.pkgwork['remove'])))
                           
            # Update counters
            count = count + 1
            old = left

            self.CondPrint("verbose", "Installing Non Package entries")
            [self.InstallEntry(ent) for ent in work if ent.tag != 'Package']

            packages = [pkg for pkg in work if pkg.tag == 'Package']
            if packages:
                # try single large install
                self.CondPrint("verbose", "Trying single pass package install")
                cmdrc = system(self.rpmcmd % " ".join([pkg.get('url') for pkg in packages]))

                if cmdrc == 0:
                    self.CondPrint('verbose', "Single Pass Succeded")
                    # set all states to true and flush workqueues
                    for pkg in packages:
                        self.states[pkg] = True
                    self.Refresh()
                else:
                    self.CondPrint("verbose", "Single Pass Failed")
                    # do single pass installs
                    self.Refresh()
                    for pkg in packages:
                        # handle state tracking updates
                        if self.VerifyPackage(pkg, []):
                            self.CondPrint("verbose", "Forcing state to true for pkg %s" % (pkg.get('name')))
                            self.states[pkg] = True
                        else:
                            self.CondPrint("verbose", "Installing pkg %s version %s" %
                                           (pkg.get('name'), pkg.get('version')))
                            cmdrc = system(self.rpmcmd % (pkg.get('url')))
                            if cmdrc == 0:
                                self.states[pkg] = True
                            else:
                                self.CondPrint('verbose', "Failed to install package %s" % (pkg.get('name')))
            for entry in [ent for ent in work if self.states[ent]]:
                work.remove(entry)
                self.installed_this_run.append(entry)
            left = len(work) + len(self.pkgwork['remove'])
        self.HandleBundleDeps()

    def HandleBundleDeps(self):
        '''Handle bundles depending on what has been modified'''
        for entry in [child for child in self.structures if child.tag == 'Bundle']:
            bchildren = entry.getchildren()
            if [b_ent for b_ent in bchildren if b_ent in self.installed_this_run]:
                # This bundle has been modified
                self.CondPrint('verbose', "%s %s needs update" % (entry.tag, entry.get('name', '???')))
                modfiles = [cfile.get('name') for cfile in bchildren if cfile.tag == 'ConfigFile']
                for child in bchildren:
                    if child.tag == 'Package':
                        self.VerifyPackage(child, modfiles)
                    else:
                        self.VerifyEntry(child)
                    self.CondPrint('debug', "Re-checked entry %s %s: %s" %
                                   (child.tag, child.get('name'), self.states[child]))
                for svc in [svc for svc in bchildren if svc.tag == 'Service']:
                    if self.setup['build']:
                        # stop services in miniroot
                        system('/etc/init.d/%s stop' % svc.get('name'))
                    else:
                        self.CondPrint('debug', 'Restarting service %s' % svc.get('name'))
                        system('/etc/init.d/%s %s' % (svc.get('name'), svc.get('reload', 'reload')))
            
        for entry in self.structures:
            if [strent for strent in entry.getchildren() if not self.states[strent]]:
                self.CondPrint('verbose', "%s %s incomplete" % (entry.tag, entry.get('name', "")))
            else:
                self.structures[entry] = True
