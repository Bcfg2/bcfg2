#!/usr/bin/env python

'''This is the basic toolset class for the Bcfg2 client'''
__revision__ = '$Revision$'

from binascii import a2b_base64
from grp import getgrgid, getgrnam
from os import chown, chmod, lstat, mkdir, stat, system, unlink, rename, readlink, symlink
from pwd import getpwuid, getpwnam
from stat import S_ISVTX, S_ISGID, S_ISUID, S_IXUSR, S_IWUSR, S_IRUSR, S_IXGRP
from stat import S_IWGRP, S_IRGRP, S_IXOTH, S_IWOTH, S_IROTH, ST_MODE, S_ISDIR
from stat import S_IFREG, ST_UID, ST_GID, S_ISREG, S_IFDIR, S_ISLNK
from sys import exc_info
from time import asctime, localtime
from traceback import extract_tb

from elementtree.ElementTree import Element, SubElement, tostring

def calc_perms(initial, perms):
    '''This compares ondisk permissions with specified ones'''
    tempperms = initial
    if len(perms) == 3:
        perms = '0%s' % (perms)
    [suid, user, group, other] = [perms[int(x)] for x in range(4)]
    for (num, perm) in {1:S_ISVTX, 2:S_ISGID, 4:S_ISUID}.iteritems():
        if suid & num:
            tempperms |= perm
    for (num, perm) in {1:S_IXUSR, 2:S_IWUSR, 4:S_IRUSR}.iteritems():
        if user & num:
            tempperms |= perm
    for (num, perm) in {1:S_IXGRP, 2:S_IWGRP, 4:S_IRGRP}.iteritems():
        if group & num:
            tempperms |= perm
    for (num, perm) in {1:S_IXOTH, 2:S_IWOTH, 4:S_IROTH}.iteritems():
        if other & num:
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
            for cfile in cfg.findall(".//ConfigFile"):
                for name in self.__important__:
                    if cfile.get("name") == name:
                        self.InstallConfigFile(cfile)

    def LogFailure(self, area, entry):
        '''Print tracebacks in unexpected cases'''
        print "Failure in %s for entry: %s" % (area, tostring(entry))
        (t, v, tb) = exc_info()
        for line in extract_tb(tb):
            print "File %s, line %i, in %s\n   %s\n" % (line)
        print "%s: %s\n" % (t, v)
        del t, v, tb

    def print_failure(self):
        '''Display curses style failure message'''
        if self.setup['verbose']:
            print "\033[60G[\033[1;31mFAILED\033[0;39m]\r"

    def print_success(self):
        '''Display curses style success message'''
        if self.setup['verbose']:
            print "\033[60G[  \033[1;32mOK\033[0;39m  ]\r"

    # These next functions form the external API

    def Inventory(self):
        # build initial set of states
        unexamined = [(x, []) for x in self.cfg.getchildren()]
        while unexamined:
            (r, modlist) = unexamined.pop()
            if r.tag not in ['Bundle', 'Independant']:
                self.VerifyEntry(r, modlist)
            else:
                modlist = [x.get('name') for x in r.getchildren() if x.tag == 'ConfigFile']
                unexamined += [(x, modlist) for x in r.getchildren()]
                self.structures[r] = False

        for structure in self.cfg.getchildren():
            self.CheckStructure(structure)

    def CheckStructure(self, structure):
        '''Check structures with bundle verification semantics'''
        if structure in self.modified:
            self.modified.remove(structure)
            if structure.tag == 'Bundle':
                # check for clobbered data
                modlist = [x.get('name') for x in structure.getchildren() if x.tag == 'ConfigFile']
                for entry in structure.getchildren():
                    self.VerifyEntry(entry, modlist)
        try:
            state = [self.states[x] for x in structure.getchildren()]
            if False not in state:
                self.structures[structure] = True
        except KeyError, k:
            print "State verify evidently failed for %s" % (k)
            self.structures[structure] = False

    def Install(self):
        '''Baseline Installation method based on current entry states'''
        self.modified  =  [k for (k, v) in self.structures.iteritems() if not v]
        for entry in [k for (k, v) in self.states.iteritems() if not v]:
            self.InstallEntry(entry)

    def GenerateStats(self):
        '''Generate XML summary of execution statistics'''
        stats = Element("Statistics")
        SubElement(stats, "Structures", good=str(len([k for k, v in self.structures.iteritems() if v])), \
                   bad=str(len([k for k, v in self.structures.iteritems() if not v])))
        SubElement(stats, "Entries", good=str(len([k for k, v in self.states.iteritems() if v])), \
                   bad=str(len([k for k, v in self.states.iteritems() if not v])))
        if len([k for k, v in self.structures.iteritems() if not v]) == 0:
            stats.set('state', 'clean')
        else:
            stats.set('state', 'dirty')
        stats.set('time', asctime(localtime()))
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

            if self.setup['debug']:
                print entry.get('name'), self.states[entry]
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
        try:
            s = readlink(entry.get('name'))
            if s == entry.get('to'):
                return True
            return False
        except OSError:
            return False

    def InstallSymLink(self, entry):
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
        except OSError, e:
            return False

    def VerifyDirectory(self, entry):
        try:
            ondisk = stat(entry.get('name'))
        except OSError:
            return False
        try:
            owner = getpwuid(ondisk[ST_UID])[0]
            group = getgrgid(ondisk[ST_GID])[0]
        except OSError:
            owner = 'root'
            group = 'root'
        perms = stat(entry.get('name'))[ST_MODE]
        if ((owner == entry.get('owner')) and
            (group == entry.get('group')) and
            (perms == calc_perms(S_IFDIR, entry.get('perms')))):
            return True
        else:
            return False

    def InstallDirectory(self, entry):
        try:
            fmode = lstat(entry.get('name'))
            if not S_ISDIR(fmode[0]):
                try:
                    unlink(entry.get('name'))
                except:
                    return False
        except OSError:
            print "Failed to cleanup for directory %s" % (entry.get('name'))
        try:
            mkdir(entry.get('name'))
        except OSError:
            return False
        try:
            chown(entry.get('name'),
                  getpwnam(entry.get('owner'))[2], getgrnam(entry.get('group'))[2])
            chmod(entry.get('name'), entry.get('perms'))
        except:
            return False

    def VerifyConfigFile(self, entry):
        try:
            ondisk = stat(entry.get('name'))
        except OSError:
            return False
        try:
            data = open(entry.get('name')).read()
        except IOError:
            return False
        try:
            owner = getpwuid(ondisk[ST_UID])[0]
            group = getgrgid(ondisk[ST_GID])[0]
        except KeyError:
            return False
        perms = stat(entry.get('name'))[ST_MODE]
        if entry.get('encoding', 'ascii') == 'base64':
            tempdata = a2b_base64(entry.text)
        else:
            tempdata = entry.text
        if ((data == tempdata) and (owner == entry.get('owner')) and
            (group == entry.get('group')) and (perms == calc_perms(S_IFREG, entry.get('perms')))):
            return True
        return False

    def InstallConfigFile(self, entry):
        if self.setup['dryrun'] or self.setup['verbose']:
            print "Installing ConfigFile %s" % (entry.get('name'))
        if self.setup['dryrun']:
            return False
        parent = "/".join(entry.get('name').split('/')[:-1])
        if parent:
            try:
                s = lstat(parent)
                try:
                    if not S_ISDIR(s[ST_MODE]):
                        unlink(parent)
                        mkdir(parent)
                except OSError:
                    return False
            except OSError:
                # need to handle mkdir -p case
                mkdir(parent)

        # If we get here, then the parent directory should exist
        try:
            newfile = open("%s.new"%(entry.get('name')), 'w')
            if entry.attrib.get('encoding', 'ascii') == 'base64':
                filedata = a2b_base64(entry.text)
            else:
                filedata = entry.text
            newfile.write(filedata)
            newfile.close()
            chown(newfile.name, getpwnam(entry.get('owner'))[2], getgrnam(entry.get('group'))[2])
            chmod(newfile.name, calc_perms(S_IFREG, entry.get('perms')))
            if entry.get("paranoid", False) and self.setup.get("paranoid", False):
                system("diff -u %s %s.new"%(entry.get('name'), entry.get('name')))
            rename(newfile.name, entry.get('name'))
            return True
        except (OSError, IOError), e:
            print e
            return False

