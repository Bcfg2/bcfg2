'''This is the basic toolset class for the Bcfg2 client'''
__revision__ = '$Revision: 1.39 $'

from binascii import a2b_base64
from grp import getgrgid, getgrnam
from os import chown, chmod, lstat, mkdir, stat, system, unlink, rename, readlink, symlink
from pwd import getpwuid, getpwnam
from stat import S_ISVTX, S_ISGID, S_ISUID, S_IXUSR, S_IWUSR, S_IRUSR, S_IXGRP
from stat import S_IWGRP, S_IRGRP, S_IXOTH, S_IWOTH, S_IROTH, ST_MODE, S_ISDIR
from stat import S_IFREG, ST_UID, ST_GID, S_ISREG, S_IFDIR, S_ISLNK
from sys import exc_info
#from time import asctime, localtime
from traceback import extract_tb

from elementtree.ElementTree import Element, SubElement, tostring

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

    def __init__(self, cfg, setup):
        '''Install initial configs, and setup state structures'''
        object.__init__(self)
        self.setup = setup
        self.cfg = cfg
        self.states = {}
        self.structures = {}
        self.modified = []
        self.extra = []
        if self.__important__:
            for cfile in [cfl for cfl in cfg.findall(".//ConfigFile") if cfl.get('name') in self.__important__]:
                self.VerifyEntry(cfile)
                if not self.states[cfile]:
                    self.InstallConfigFile(cfile)

    def CondPrint(self, state, msg):
        '''Conditionally print message'''
        if self.setup[state]:
            print msg

    def LogFailure(self, area, entry):
        '''Print tracebacks in unexpected cases'''
        print "Failure in %s for entry: %s" % (area, tostring(entry))
        (ttype, value, trace) = exc_info()
        for line in extract_tb(trace):
            print "File %s, line %i, in %s\n   %s\n" % (line)
        print "%s: %s\n" % (ttype, value)
        del ttype, value, trace

    # These next functions form the external API

    def Inventory(self):
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

    def Install(self):
        '''Baseline Installation method based on current entry states'''
        self.modified  =  [key for (key, val) in self.structures.iteritems() if not val]
        [self.InstallEntry(key) for (key, val) in self.states.iteritems() if not val]

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
        return stats

    # the next two are dispatch functions

    def VerifyEntry(self, entry, modlist = []):
        '''Dispatch call to Verify<tagname> and save state in self.states'''
        try:
            method = getattr(self, "Verify%s"%(entry.tag))
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
                unlink(entry.get('name'))
            elif S_ISDIR(fmode):
                system("mv %s/ %s.bak" % (entry.get('name'), entry.get('name')))
            else:
                unlink(entry.get('name'))
        except OSError:
            print "Symlink %s cleanup failed" % (entry.get('name'))
        try:
            symlink(entry.get('to'), entry.get('name'))
        except OSError:
            return False

    def VerifyDirectory(self, entry):
        '''Verify Directory Entry'''
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
        perms = stat(entry.get('name'))[ST_MODE]
        if ((owner == entry.get('owner')) and
            (group == entry.get('group')) and
            (perms == calc_perms(S_IFDIR, entry.get('perms')))):
            return True
        else:
            if owner != entry.get('owner'):
                self.CondPrint("debug", "Directory %s ownership wrong" % (entry.get('name')))
            if group != entry.get('group'):
                self.CondPrint("debug", "Directory %s group wrong" % (entry.get('name')))
            if perms != calc_perms(S_IFDIR, entry.get('perms')):
                self.CondPrint("debug", "Directory %s permissions wrong" % (entry.get('name')))
            return False

    def InstallDirectory(self, entry):
        '''Install Directory Entry'''
        self.CondPrint('verbose', "Installing Directory %s" % (entry.get('name')))
        try:
            fmode = lstat(entry.get('name'))
            if not S_ISDIR(fmode[0]):
                try:
                    unlink(entry.get('name'))
                except OSError:
                    self.CondPrint('debug', "Failed to unlink %s" % (entry.get('name')))
                    return False
        except OSError:
            # stat failed
            pass
        
        try:
            mkdir(entry.get('name'))
        except OSError:
            self.CondPrint('debug', 'Failed to create directory %s' % (entry.get('name')))
            return False
        try:
            chown(entry.get('name'),
                  getpwnam(entry.get('owner'))[2], getgrnam(entry.get('group'))[2])
            chmod(entry.get('name'), calc_perms(S_IFDIR, entry.get('perms')))
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
                    mkdir(current)

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
                system("cp %s /var/cache/bcfg2/%s" % (entry.get('name')))
            rename(newfile.name, entry.get('name'))
            return True
        except (OSError, IOError), errmsg:
            print errmsg
            return False

