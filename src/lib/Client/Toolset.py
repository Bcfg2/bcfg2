#!/usr/bin/env python

from grp import getgrgid, getgrnam
from os import chown, chmod, lstat, mkdir, stat, system, unlink, rename
from pwd import getpwuid, getpwnam
from stat import *
from string import join, split

def print_failure():
    if '-v' in argv: print "\033[60G[\033[1;31mFAILED\033[0;39m]\r"

def print_success():
    if '-v' in argv: print "\033[60G[  \033[1;32mOK\033[0;39m  ]\r"

def CalcPerms(initial,perms):
    tempperms = initial
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
        if self.__important__:
            for c in cfg.findall(".//ConfigFile"):
                for name in self.__important__:
                    if c.get("name") == name:
                        self.InstallConfigFile(c)

    def VerifySymLink(self, src, dst):
        try:
            s = readlink(dst)
            if s == src:
                return True
            return False
        except OSError:
            return False

    def InstallSymLink(self, src, dst):
        try:
            fmode = lstat(dst)[ST_MODE]
            if S_ISREG(fmode) or S_ISLNK(fmode):
                unlink(dst)
            elif S_ISDIR(fmode):
                system("mv %s/ %s.bak"%(dst, dst))
            else:
                unlink(dst)
        except OSError, e:
            pass
        try:
            symlink(src, dst)
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
            (perms == entry.attrib['perms'])):
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
            newfile.write(entry.text)
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

    def FindConfig(self):
        pass
        
            
