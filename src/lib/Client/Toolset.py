'''This is the basic toolset class for the Bcfg2 client'''
__revision__ = '$Revision$'

from binascii import a2b_base64
from copy import deepcopy
from grp import getgrgid, getgrnam
from os import chown, chmod, lstat, mkdir, stat, system, unlink, rename, readlink, symlink
from pwd import getpwuid, getpwnam
from stat import S_ISVTX, S_ISGID, S_ISUID, S_IXUSR, S_IWUSR, S_IRUSR, S_IXGRP
from stat import S_IWGRP, S_IRGRP, S_IXOTH, S_IWOTH, S_IROTH, ST_MODE, S_ISDIR
from stat import S_IFREG, ST_UID, ST_GID, S_ISREG, S_IFDIR, S_ISLNK
from sys import exc_info
import stat as statmod
from math import floor, ceil
#from time import asctime, localtime
from traceback import extract_tb
from popen2 import Popen4
from lxml.etree import Element, SubElement, tostring

def calc_perms(initial, perms):
    '''This compares ondisk permissions with specified ones'''
    pdisp = [{1:S_ISVTX, 2:S_ISGID, 4:S_ISUID}, {1:S_IXUSR, 2:S_IWUSR, 4:S_IRUSR},
             {1:S_IXGRP, 2:S_IWGRP, 4:S_IRGRP}, {1:S_IXOTH, 2:S_IWOTH, 4:S_IROTH}]
    tempperms = initial
    if len(perms) == 3:
        perms = '0%s' % (perms)
    pdigits = [int(perms[digit]) for digit in range(4)]
    for index in range(4):
        for (num, perm) in pdisp[index].iteritems():
            if pdigits[index] & num:
                tempperms |= perm
    return tempperms

class Toolset(object):
    '''The toolset class contains underlying command support and all states'''
    __important__ = []
    __name__ = 'Toolset'
    pkgtool = ('echo', ('%s', ['name']))
    
    def __init__(self, cfg, setup):
        '''Install initial configs, and setup state structures'''
        object.__init__(self)
        self.setup = setup
        self.cfg = cfg
        self.states = {}
        self.structures = {}
        self.modified = []
        self.installed = {}
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}
        self.extra_services = []
        (self.height, self.width) = self.get_height_width()
        if self.__important__:
            for cfile in [cfl for cfl in cfg.findall(".//ConfigFile") if cfl.get('name') in self.__important__]:
                self.VerifyEntry(cfile)
                if not self.states[cfile]:
                    self.InstallConfigFile(cfile)

    def saferun(self, command):
        '''Run a command in a pipe dealing with stdout buffer overloads'''
        self.CondPrint('debug', '> %s' % command)

        runpipe = Popen4(command, bufsize=16384)
        output = runpipe.fromchild.read()
        if len(output) > 0:
            self.CondPrint('debug', '< %s' % output)
        cmdstat = runpipe.poll()
        while cmdstat == -1:
            moreOutput = runpipe.fromchild.read()
            if len(moreOutput) > 0:                
                self.CondPrint('debug', '< %s' % moreOutput)
            output += moreOutput
            cmdstat = runpipe.poll()

        return (cmdstat, [line for line in output.split('\n') if line])

    def CondPrint(self, state, msg):
        '''Conditionally print message'''
        if self.setup[state]:
            try:
                prefix = "%s[%s]: " % (self.__name__, state)
                line_len = self.width-len(prefix)
                for line in msg.split('\n'):
                    inner_lines = int(floor(float(len(line)) / line_len))+1
                    for i in xrange(inner_lines):
                        print "%s%s" % (prefix, line[i*line_len:(i+1)*line_len])
            except IOError:
                pass

    def get_height_width(self):
        try:
            import termios, struct, fcntl
            height, width = struct.unpack('hhhh',
                                        fcntl.ioctl(0, termios.TIOCGWINSZ,
                                                    "\000"*8))[0:2]
            return height, width
        except:
            return 25, 80    

    def FormattedCondPrint(self, state, items):
        items.sort()
        screenWidth = self.width - len("%s[%s]:" % (self.__name__, state))
        columnWidth = 1
        for item in items:
            if len(item) > columnWidth:
                columnWidth = len(item)
        columnWidth += 1

        columns = int(floor(float(screenWidth) / columnWidth))
        lines = int(ceil(float(len(items)) / columns))

        for lineNumber in xrange(lines):
            lineItems = []
            for columnNumber in xrange(columns):
                itemNumber = int(columnNumber*lines + lineNumber)
                if itemNumber < len(items):
                    lineItems.append(items[itemNumber]) 
            format = "%%-%ss" % columnWidth
            lineText = "".join([format % item for item in lineItems])
            self.CondPrint(state, lineText.rstrip())

    def CondDisplayList(self, state, title, items):
        self.CondPrint(state, title)
        self.FormattedCondPrint(state, items)
        self.CondPrint(state, '')
            
    def CondDisplayState(self, state, phase):
        self.CondPrint(state, 'Phase: %s' % phase)
        self.CondPrint(state, 'Correct entries:\t%d'
                       % self.states.values().count(True))
        self.CondPrint(state, 'Incorrect entries:\t%d' %
                       self.states.values().count(False))
        self.CondPrint(state, 'Total managed entries:\t%d' %
                       len(self.states.values()))
        self.CondPrint(state, 'Unmanaged entries:\t%d' %
                       len(self.pkgwork['remove']))
        self.CondPrint(state, '')                 

        if ((self.states.values().count(False) > 0) and
            not self.pkgwork['remove']):
            self.CondPrint('All entries correct.')
            
    def LogFailure(self, area, entry):
        '''Print tracebacks in unexpected cases'''
        print "Failure in %s for entry: %s" % (area, tostring(entry))
        (ttype, value, trace) = exc_info()
        for line in extract_tb(trace):
            print "File %s, line %i, in %s\n   %s\n" % (line)
        print "%s: %s\n" % (ttype, value)
        del ttype, value, trace

    # These next functions form the external API

    def Refresh(self):
        '''Update based on current pkg system state'''
        return

    def Inventory(self):
        '''Inventory system status'''
        self.CondPrint('verbose', "Inventorying system...")
        self.Inventory_Entries()
        all = deepcopy(self.installed)
        desired = {}
        for entry in self.cfg.findall(".//Package"):
            desired[entry.attrib['name']] = entry
        self.pkgwork = {'update':[], 'add':[], 'remove':[]}
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

    def Inventory_Entries(self):
        '''Build up workqueue for installation'''
        # build initial set of states
        unexamined = [(child, []) for child in self.cfg.getchildren()]
        while unexamined:
            (entry, modlist) = unexamined.pop()
            if entry.tag not in ['Bundle', 'Independant']:
                self.VerifyEntry(entry, modlist)
            else:
                modlist = [cfile.get('name') for cfile in entry.getchildren() if cfile.tag == 'ConfigFile']
                unexamined += [(child, modlist) for child in entry.getchildren()]
                self.structures[entry] = False

        for structure in self.cfg.getchildren():
            self.CheckStructure(structure)

    def CheckStructure(self, structure):
        '''Check structures with bundle verification semantics'''
        if structure in self.modified:
            self.modified.remove(structure)
            if structure.tag == 'Bundle':
                # check for clobbered data
                modlist = [cfile.get('name') for cfile in structure.getchildren() if cfile.tag == 'ConfigFile']
                for entry in structure.getchildren():
                    self.VerifyEntry(entry, modlist)
        try:
            state = [self.states[entry] for entry in structure.getchildren()]
            if False not in state:
                self.structures[structure] = True
        except KeyError, msg:
            print "State verify evidently failed for %s" % (msg)
            self.structures[structure] = False

    def GenerateStats(self, client_version):
        '''Generate XML summary of execution statistics'''
        stats = Element("Statistics")

        # Calculate number of total bundles and structures
        total =  len(self.states)
        stats.set('total', str(total))
        # Calculate number of good bundles and structures
        good = len([key for key, val in self.states.iteritems() if val])
        stats.set('good', str(good))
        stats.set('version', '2.0')
        stats.set('client_version', client_version)


        if len([key for key, val in self.structures.iteritems() if not val]) == 0:
            stats.set('state', 'clean')
            dirty = 0
        else:
            stats.set('state', 'dirty')
            dirty = 1
        #stats.set('time', asctime(localtime()))

        # List bad elements of the configuration
        if dirty:
            bad_elms = SubElement(stats, "Bad")
            for elm in [key for key, val in self.states.iteritems() if not val]:
                if elm.get('name') == None:
                    SubElement(bad_elms, elm.tag)
                else:
                    SubElement(bad_elms, elm.tag, name=elm.get('name'))
        if self.modified:
            mod = SubElement(stats, "Modified")
            for elm in self.modified:
                SubElement(mod, elm.tag, name=elm.get('name'))
        if self.extra_services + self.pkgwork['remove']:
            extra = SubElement(stats, "Extra")
            [SubElement(extra, "Service", name=svc) for svc in self.extra_services]
            [SubElement(extra, "Package", name=pkg) for pkg in self.pkgwork['remove']]
        return stats

    # the next two are dispatch functions

    def VerifyEntry(self, entry, modlist = []):
        '''Dispatch call to Verify<tagname> and save state in self.states'''
        try:
            method = getattr(self, "Verify%s" % (entry.tag))
            # verify state and stash value in state
            if entry.tag == 'Package':
                self.states[entry] = method(entry, modlist)
            else:
                self.states[entry] = method(entry)
        except:
            self.LogFailure("Verify", entry)

    def InstallEntry(self, entry):
        '''Dispatch call to self.Install<tagname>'''
        try:
            method = getattr(self, "Install%s"%(entry.tag))
            self.states[entry] = method(entry)
        except:
            self.LogFailure("Install", entry)

    # All remaining operations implement the mechanics of POSIX cfg elements

    def VerifySymLink(self, entry):
        '''Verify SymLink Entry'''
        try:
            sloc = readlink(entry.get('name'))
            if sloc == entry.get('to'):
                return True
            return False
        except OSError:
            return False

    def InstallSymLink(self, entry):
        '''Install SymLink Entry'''
        self.CondPrint('verbose', "Installing Symlink %s" % (entry.get('name')))
        try:
            fmode = lstat(entry.get('name'))[ST_MODE]
            if S_ISREG(fmode) or S_ISLNK(fmode):
                self.CondPrint('debug', "Non-directory entry already exists at %s" % (entry.get('name')))
                unlink(entry.get('name'))
            elif S_ISDIR(fmode):
                self.CondPrint('debug', "Directory entry already exists at %s" % (entry.get('name')))
                self.saferun("mv %s/ %s.bak" % (entry.get('name'), entry.get('name')))
            else:
                unlink(entry.get('name'))
        except OSError:
            print "Symlink %s cleanup failed" % (entry.get('name'))
        try:
            symlink(entry.get('to'), entry.get('name'))
            return True
        except OSError:
            return False

    def VerifyDirectory(self, entry):
        '''Verify Directory Entry'''
        while len(entry.get('perms', '')) < 4:
            entry.set('perms', '0' + entry.get('perms', ''))
        try:
            ondisk = stat(entry.get('name'))
        except OSError:
            self.CondPrint("debug", "Directory %s does not exist" % (entry.get('name')))
            return False
        try:
            owner = getpwuid(ondisk[ST_UID])[0]
            group = getgrgid(ondisk[ST_GID])[0]
        except OSError:
            self.CondPrint('debug', 'User resolution failing')
            owner = 'root'
            group = 'root'
        perms = oct(stat(entry.get('name'))[ST_MODE])[-4:]
        if ((owner == entry.get('owner')) and
            (group == entry.get('group')) and
            (perms == entry.get('perms'))):
            return True
        else:
            if owner != entry.get('owner'):
                self.CondPrint("debug", "Directory %s ownership wrong" % (entry.get('name')))
            if group != entry.get('group'):
                self.CondPrint("debug", "Directory %s group wrong" % (entry.get('name')))
            if perms != entry.get('perms'):
                self.CondPrint("debug", "Directory %s permissions wrong: are %s should be %s" %
                               (entry.get('name'), perms, entry.get('perms')))
            return False

    def InstallDirectory(self, entry):
        '''Install Directory Entry'''
        exists = False
        self.CondPrint('verbose', "Installing Directory %s" % (entry.get('name')))
        try:
            fmode = lstat(entry.get('name'))
            if not S_ISDIR(fmode[ST_MODE]):
                self.CondPrint("debug", "Found a non-directory entry at %s" % (entry.get('name')))
                try:
                    unlink(entry.get('name'))
                except OSError:
                    self.CondPrint('verbose', "Failed to unlink %s" % (entry.get('name')))
                    return False
            else:
                exists = True
        except OSError:
            # stat failed
            pass

        if not exists:
            try:
                mkdir(entry.get('name'))
            except OSError:
                self.CondPrint('debug', 'Failed to create directory %s' % (entry.get('name')))
                return False
        try:
            chown(entry.get('name'),
                  getpwnam(entry.get('owner'))[2], getgrnam(entry.get('group'))[2])
            chmod(entry.get('name'), calc_perms(S_IFDIR, entry.get('perms')))
            return True
        except (OSError, KeyError):
            self.CondPrint('debug', 'Permission fixup failed for %s' % (entry.get('name')))
            return False

    def VerifyConfigFile(self, entry):
        '''Install ConfigFile Entry'''
        filename = entry.get('name')
        try:
            ondisk = stat(filename)
        except OSError:
            self.CondPrint('debug', "File %s doesn't exist" % (filename))
            return False
        try:
            data = open(filename).read()
        except IOError:
            self.CondPrint('debug', "Failed to read %s" % (filename))
            return False
        try:
            owner = getpwuid(ondisk[ST_UID])[0]
            group = getgrgid(ondisk[ST_GID])[0]
        except KeyError:
            self.CondPrint('debug', "Owner/Group failure for %s: %s, %s" %
                           (filename, ondisk[ST_UID], ondisk[ST_GID]))
            return False
        perms = stat(filename)[ST_MODE]
        if entry.get('encoding', 'ascii') == 'base64':
            tempdata = a2b_base64(entry.text)
        else:
            tempdata = entry.text

        if ((data == tempdata) and (owner == entry.get('owner')) and
            (group == entry.get('group')) and (perms == calc_perms(S_IFREG, entry.get('perms')))):
            return True
        else:
            if data != tempdata:
                self.CondPrint('debug', "File %s contents wrong" % (filename))
            elif ((owner != entry.get('owner')) or (group != entry.get('group'))):
                self.CondPrint('debug', 'File %s ownership wrong' % (filename))
            elif perms != calc_perms(S_IFREG, entry.get('perms')):
                self.CondPrint('debug', 'File %s permissions wrong' % (filename))
            return False

    def InstallConfigFile(self, entry):
        '''Install ConfigFile Entry'''
        if entry.text == None:
            self.CondPrint('verbose',
                           "Incomplete information for ConfigFile %s. Cannot install" % (entry.get('name')))
            return False
        self.CondPrint('verbose', "Installing ConfigFile %s" % (entry.get('name')))

        if self.setup['dryrun']:
            return False
        parent = "/".join(entry.get('name').split('/')[:-1])
        if parent:
            for idx in xrange(len(parent.split('/')[:-1])):
                current = '/'+'/'.join(parent.split('/')[1:2+idx])
                try:
                    sloc = lstat(current)
                    try:
                        if not S_ISDIR(sloc[ST_MODE]):
                            unlink(current)
                            mkdir(current)
                    except OSError:
                        return False
                except OSError:
                    try:
                        mkdir(current)
                    except OSError:
                        return False

        # If we get here, then the parent directory should exist
        try:
            newfile = open("%s.new"%(entry.get('name')), 'w')
            if entry.get('encoding', 'ascii') == 'base64':
                filedata = a2b_base64(entry.text)
            else:
                filedata = entry.text
            newfile.write(filedata)
            newfile.close()
            try:
                chown(newfile.name, getpwnam(entry.get('owner'))[2], getgrnam(entry.get('group'))[2])
            except KeyError:
                chown(newfile.name, 0, 0)
            chmod(newfile.name, calc_perms(S_IFREG, entry.get('perms')))
            if entry.get("paranoid", False) and self.setup.get("paranoid", False):
                self.saferun("cp %s /var/cache/bcfg2/%s" % (entry.get('name')))
            rename(newfile.name, entry.get('name'))
            return True
        except (OSError, IOError), err:
            if err.errno == 13:
                self.CondPrint('verbose', "Failed to open %s for writing" % (entry.get('name')))
            else:
                print err
            return False

    def VerifyPackage(self, entry, modlist):
        '''Dummy package verification method. Cannot succeed'''
        return False

    def VerifyPermissions(self, entry):
        '''Verify method for abstract permission'''
        try:
            sinfo = stat(entry.get('name'))
        except OSError:
            self.CondPrint('debug', "Entry %s doesn't exist" % entry.get('name'))
            return False
        # pad out perms if needed
        while len(entry.get('perms', '')) < 4:
            entry.set('perms', '0' + entry.get('perms', ''))
        perms = oct(sinfo[ST_MODE])[-4:]
        if perms == entry.get('perms'):
            return True

        self.CondPrint('debug', "Entry %s permissions incorrect" % entry.get('name'))
        return False
    
    def InstallPermissions(self, entry):
        '''Install method for abstract permission'''
        try:
            sinfo = stat(entry.get('name'))
        except OSError:
            self.CondPrint('debug', "Entry %s doesn't exist" % entry.get('name'))
            return False
        for ftype in ['DIR', 'REG', 'CHR', 'BLK']:
            if getattr(statmod, "S_IS%s" % ftype)(sinfo[ST_MODE]):
                chmod(entry.get('name'), calc_perms(getattr(statmod, "S_IF%s" % ftype), entry.get('perms')))
                return True
        self.CondPrint('verbose', "Entry %s has unknown file type" % entry.get('name'))
        return False

    def VerifyPostInstall(self, entry):
        '''Postinstall verification method'''
        return True

    def HandleBundleDeps(self):
        '''Handle bundles depending on what has been modified'''
        for entry in [child for child in self.structures if child.tag == 'Bundle']:
            bchildren = entry.getchildren()
            if [b_ent for b_ent in bchildren if b_ent in self.modified]:
                # This bundle has been modified
                self.CondPrint('verbose', "%s %s needs update" % (entry.tag, entry.get('name', '???')))
                modfiles = [cfile.get('name') for cfile in bchildren if cfile.tag == 'ConfigFile']
                for child in bchildren:
                    if child.tag == 'Package':
                        self.VerifyPackage(child, modfiles)
                    else:
                        self.VerifyEntry(child)
                        if not self.states[child]:
                            self.CondPrint('debug', "Reinstalling clobbered entry %s %s" % (child.tag,
                                                                                            child.get('name')))
                            self.InstallEntry(child)
                            self.VerifyEntry(child)
                    self.CondPrint('debug', "Re-checked entry %s %s: %s" %
                                   (child.tag, child.get('name'), self.states[child]))
                for postinst in [entry for entry in bchildren if entry.tag == 'PostInstall']:
                    self.saferun(postinst.get('name'))
                for svc in [svc for svc in bchildren if svc.tag == 'Service' and
                            svc.get('status', 'off') == 'on']:
                    if self.setup['build']:
                        # stop services in miniroot
                        self.saferun('/etc/init.d/%s stop' % svc.get('name'))
                    else:
                        self.CondPrint('debug', 'Restarting service %s' % svc.get('name'))
                        self.saferun('/etc/init.d/%s %s' % (svc.get('name'), svc.get('reload', 'reload')))
            
        for entry in self.structures:
            if [strent for strent in entry.getchildren() if not self.states.get(strent, False)]:
                self.CondPrint('verbose', "%s %s incomplete" % (entry.tag, entry.get('name', "")))
            else:
                self.structures[entry] = True

    def HandleExtra(self):
        '''deal with extra configuration during installation'''
        return False

    def Install(self):
        '''Correct detected misconfigurations'''
        if self.setup['dryrun']:
            self.CondPrint("verbose", "Dry-run mode: no changes will be made")
        else:
            self.CondPrint("verbose", "Updating the system")
        self.CondPrint("verbose", "")
        self.HandleExtra()
        # use quick package ops from here on
        self.setup['quick'] = True

        self.CondDisplayList('dryrun', "Packages to update:",
                             [pkg.get('name') for pkg in self.pkgwork['update']])
        self.CondDisplayList('dryrun', "Packages to add:",
                       [pkg.get('name') for pkg in self.pkgwork['add']])
        self.CondDisplayList('dryrun', "Packages to remove:",
                             self.pkgwork['remove'])
        self.CondDisplayList('dryrun', "Entries to update:",
                             ["%s: %s" % (entry.tag, entry.get('name'))
                              for entry in self.states if not (self.states[entry]
                                                               or entry.tag == 'Package')])
        self.CondDisplayList('dryrun', "Services to remove:", self.extra_services)
                             
        if self.setup['dryrun']:
            return

        # build up work queue
        work = self.pkgwork['add'] + self.pkgwork['update']
        # add non-package entries
        work += [ent for ent in self.states if ent.tag != 'Package' and not self.states[ent]]

        # Counters
        ## Packages left to install
        left = len(work) + len(self.pkgwork['remove'])
        ## Packages installed in previous iteration
        old = left + 1
        ## loop iterations performed
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

            self.CondPrint("verbose", "Installing non-package entries")
            [self.InstallEntry(ent) for ent in work if ent.tag != 'Package']

            packages = [pkg for pkg in work if pkg.tag == 'Package']
            ptypes = []
            for pkg in packages:
                if pkg.get('type') not in ptypes:
                    ptypes.append(pkg.get('type'))
            if packages:
                for pkgtype in ptypes:
                    # try single large install
                    self.CondPrint("verbose", "Trying single pass package install for pkgtype %s" % pkgtype)
                    if not self.pkgtool.has_key(pkgtype):
                        self.CondPrint("verbose", "No support for pkgtype %s" % (pkgtype))
                        continue
                    pkgtool = self.pkgtool[pkgtype]
                    pkglist = [pkg for pkg in packages if pkg.get('type') == pkgtype]
                    for field in pkgtool[1][1]:
                        pkglist = [pkg for pkg in pkglist if pkg.attrib.has_key(field)]
                    if not pkglist:
                        self.CondPrint("debug", "No complete/installable packages of type %s" % pkgtype)
                        continue
                    pkgargs = " ".join([pkgtool[1][0] % tuple([pkg.get(field) for field in pkgtool[1][1]])
                                        for pkg in pkglist])

                    self.CondPrint("debug", "Installing packages: :%s:" % pkgargs)
                    self.CondPrint("debug", "Running command ::%s::" % (pkgtool[0] % pkgargs))
                    (cmdrc, cmdoutput) = self.saferun(pkgtool[0] % pkgargs)

                    if cmdrc == 0:
                        self.CondPrint('verbose', "Single Pass Succeded")
                        # set all package states to true and flush workqueues
                        pkgnames = [pkg.get('name') for pkg in pkglist]
                        for entry in [entry for entry in self.states.keys()
                                      if entry.tag == 'Package' and entry.get('type') == pkgtype and entry.get('name') in pkgnames]:
                            self.CondPrint('debug', 'Setting state to true for pkg %s' % (entry.get('name')))
                            self.states[entry] = True
                            [self.pkgwork[listname].remove(entry) for listname in ['add', 'update'] if self.pkgwork[listname].count(entry)]
                        self.Refresh()
                    else:
                        self.CondPrint("verbose", "Single Pass Failed")
                        # do single pass installs
                        self.Refresh()
                        for pkg in pkglist:
                            # handle state tracking updates
                            if self.VerifyPackage(pkg, []):
                                self.CondPrint("verbose", "Forcing state to true for pkg %s" % (pkg.get('name')))
                                self.states[pkg] = True
                            else:
                                self.CondPrint("verbose", "Installing pkg %s version %s" %
                                               (pkg.get('name'), pkg.get('version')))
                                (cmdrc, cmdoutput) = self.saferun(pkgtool[0] %
                                               (pkgtool[1][0] %
                                                tuple([pkg.get(field) for field in pkgtool[1][1]])))
                                if cmdrc == 0:
                                    self.states[pkg] = True
                                else:
                                    self.CondPrint('verbose', "Failed to install package %s" % (pkg.get('name')))
            for entry in [ent for ent in work if self.states[ent]]:
                work.remove(entry)
                self.modified.append(entry)
            left = len(work) + len(self.pkgwork['remove'])
        self.HandleBundleDeps()
