#!/usr/bin/env python

from binascii import a2b_base64
from grp import getgrgid, getgrnam
from os import chown, chmod, lstat, mkdir, stat, system, unlink, rename, readlink, symlink
from pwd import getpwuid, getpwnam
from stat import *
from string import join, split
from sys import exc_info
from time import asctime, localtime
from traceback import extract_tb

from elementtree.ElementTree import Element, SubElement, tostring

def print_failure():
    if '-v' in argv: print "\033[60G[\033[1;31mFAILED\033[0;39m]\r"

def print_success():
    if '-v' in argv: print "\033[60G[  \033[1;32mOK\033[0;39m  ]\r"

def CalcPerms(initial,perms):
    tempperms = initial
    if len(perms) == 3: perms = '0%s'%(perms)
    (s,u,g,o) = map(int, map(lambda x:perms[x], range(4)))
    if s & 1:
        tempperms |= S_ISVTX
    if s & 2:
        tempperms |= S_ISGID
    if s & 4:
        tempperms |= S_ISUID
    if u & 1:
        tempperms |= S_IXUSR
    if u & 2:
        tempperms |= S_IWUSR
    if u & 4:
        tempperms |= S_IRUSR
    if g & 1:
        tempperms |= S_IXGRP
    if g & 2:
        tempperms |= S_IWGRP
    if g & 4:
        tempperms |= S_IRGRP
    if o & 1:
        tempperms |= S_IXOTH
    if o & 2:
        tempperms |= S_IWOTH
    if o & 4:
        tempperms |= S_IROTH
    return tempperms

class Toolset(object):
    __important__ = []

    def __init__(self, cfg, setup):
        self.setup = setup
        self.cfg = cfg
        self.states = {}
        self.structures = {}
        self.modified = []
        self.extra = []
        if self.__important__:
            for c in cfg.findall(".//ConfigFile"):
                for name in self.__important__:
                    if c.get("name") == name:
                        self.InstallConfigFile(c)

    def LogFailure(self, area, entry):
        '''Print tracebacks in unexpected cases'''
        print "Failure in %s for entry: %s"%(area, tostring(entry))
        (t,v,tb) = exc_info()
        for line in extract_tb(tb):
            print "File %s, line %i, in %s\n   %s\n"%(line)
        print "%s: %s\n"%(t,v)
        del t,v,tb

    # These next functions form the external API

    def Inventory(self):
        # build initial set of states
        unexamined = map(lambda x:(x,[]), self.cfg.getchildren())
        while unexamined:
            (r, modlist) = unexamined.pop()
            if r.tag not in ['Bundle', 'Independant']:
                self.VerifyEntry(r, modlist)
            else:
                modlist = [x.attrib['name'] for x in r.getchildren() if x.tag == 'ConfigFile']
                unexamined += map(lambda x:(x,modlist), r.getchildren())
                self.structures[r] = False

        for structure in self.cfg.getchildren():
            self.CheckStructure(structure)

    def CheckStructure(self, structure):
        '''Check structures with bundle verification semantics'''
        if structure in self.modified:
            self.modified.remove(structure)
            if structure.tag == 'Bundle':
                # check for clobbered data
                modlist = [x.attrib['name'] for x in structure.getchildren() if x.tag == 'ConfigFile']
                for entry in structure.getchildren():
                    self.VerifyEntry(entry, modlist)
        try:
            state = map(lambda x:self.states[x], structure.getchildren())
            if False not in state:
                self.structures[structure] = True
        except KeyError, k:
            print "State verify evidently failed for %s"%(k)
            self.structures[structure] = False

    def Install(self):
        self.modified  =  [k for (k,v) in self.structures.iteritems() if not v]
        for entry in [k for (k,v) in self.states.iteritems() if not v]:
            self.InstallEntry(entry)

    def Commit(self):
        '''Commit pending changes to the system. This method allows for interrelated
        operations to be executed concurrently'''
        return

    def GenerateStats(self):
        '''Generate XML summary of execution statistics'''
        stats = Element("Statistics")
        SubElement(stats, "Structures", good=str(len([k for k,v in self.structures.iteritems() if v])), \
                   bad=str(len([k for k,v in self.structures.iteritems() if not v])))
        SubElement(stats, "Entries", good=str(len([k for k,v in self.states.iteritems() if v])), \
                   bad=str(len([k for k,v in self.states.iteritems() if not v])))
        if len([k for k,v in self.structures.iteritems() if not v]) == 0:
            stats.attrib['state'] = 'clean'
        else:
            stats.attrib['state'] = 'dirty'
        stats.attrib['time'] = asctime(localtime())
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
                print entry.attrib['name'], self.states[entry]
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
            s = readlink(entry.attrib['name'])
            if s == entry.attrib['to']:
                return True
            return False
        except OSError:
            return False

    def InstallSymLink(self, entry):
        try:
            fmode = lstat(entry.attrib['name'])[ST_MODE]
            if S_ISREG(fmode) or S_ISLNK(fmode):
                unlink(entry.attrib['name'])
            elif S_ISDIR(fmode):
                system("mv %s/ %s.bak"%(entry.attrib['name'], entry.attrib['name']))
            else:
                unlink(entry.attrib['name'])
        except OSError, e:
            pass
        try:
            symlink(entry.attrib['to'], entry.attrib['name'])
        except OSError, e:
            return False

    def VerifyDirectory(self, entry):
        try:
            ondisk=stat(entry.attrib['name'])
        except OSError:
            return False
        try:
            owner=getpwuid(ondisk[ST_UID])[0]
            group=getgrgid(ondisk[ST_GID])[0]
        except OSError:
            owner='root'
            group='root'
        perms=stat(entry.attrib['name'])[ST_MODE]
        if ((owner == entry.attrib['owner']) and
            (group == entry.attrib['group']) and
            (perms == CalcPerms(S_IFDIR, entry.attrib['perms']))):
            return True
        else:
            return False

    def InstallDirectory(self, entry):
        try:
            fmode = lstat(entry.attrib['name'])
            if not S_ISDIR(fmode[0]):
                try:
                    unlink(entry.attrib['name'])
                except:
                    return False
        except OSError:
            pass
        try:
            mkdir(entry.attrib['name'])
        except OSError:
            return False
        try:
            chown(entry.attrib['name'],getpwnam(self.attrib['owner'])[2],getgrnam(entry.attrib['group'])[2])
            chmod(entry.attrib['name'],entry.attrib['perms'])
        except:
            return False

    def VerifyConfigFile(self, entry):
        try:
            ondisk=stat(entry.attrib['name'])
        except OSError:
            return False
        try:
            data=open(entry.attrib['name']).read()
        except IOError:
            return False
        try:
            owner=getpwuid(ondisk[ST_UID])[0]
            group=getgrgid(ondisk[ST_GID])[0]
        except KeyError:
            return False
        perms=stat(entry.attrib['name'])[ST_MODE]
        if entry.attrib.get('encoding', 'ascii') == 'base64':
            tempdata = a2b_base64(entry.text)
        else:
            tempdata = entry.text
        if ((data == tempdata) and (owner == entry.attrib['owner']) and
            (group == entry.attrib['group']) and (perms == CalcPerms(S_IFREG, entry.attrib['perms']))):
            return True
        return False

    def InstallConfigFile(self, entry):
        if self.setup['dryrun'] or self.setup['verbose']:
            print "Installing ConfigFile %s"%(entry.attrib['name'])
        if self.setup['dryrun']:
            return False
        parent = join(split(entry.attrib['name'],"/")[:-1],"/")
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
            newfile = open("%s.new"%(entry.attrib['name']), 'w')
            if entry.attrib.get('encoding', 'ascii') == 'base64':
                filedata = a2b_base64(entry.text)
            else:
                filedata = entry.text
            newfile.write(filedata)
            newfile.close()
            chown(newfile.name, getpwnam(entry.attrib['owner'])[2], getgrnam(entry.attrib['group'])[2])
            chmod(newfile.name, CalcPerms(S_IFREG, entry.attrib['perms']))
            if entry.attrib.get("paranoid", False) and setup.get("paranoid", False):
                system("diff -u %s %s.new"%(entry.attrib['name'], entry.attrib['name']))
            rename(newfile.name, entry.attrib['name'])
            return True
        except (OSError, IOError), e:
            print e
            return False

