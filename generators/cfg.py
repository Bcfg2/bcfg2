#!/usr/bin/env python

from os import stat, listdir
from re import compile
from stat import S_ISDIR, ST_MODE, ST_MTIME

from Types import ConfigFile
from Generator import Generator
from GeneratorUtils import DirectoryBacked, FileBacked

class ConfigFragment(object):
    def __init__(self,filename,datafile):
        self.re = compile("\S+%s(.(?P<type>[BTH])(?P<prio>\d)+_(?P<data>\S+)(.(?P<op>cat|udiff))?)?"%(filename))
        m = self.re.match(datafile)
        self.type = m.group('type')
        if self.type:
            self.prio = m.group('prio')
            self.data = m.group('data')
            self.op = m.group('op')
        else:
            self.type='G'
        self.data = file(datafile).read()
        self.mtime = stat(datafile)[ST_MTIME]
        
class ConfigFileRepository(DirectoryBacked):
    fragment = compile("(^:info$|^(?P<filename>.*)(\.((B(?P<bprio>\d+)_(?P<bundle>\S+))|(T(?P<tprio>\d+)_(?P<tag>\S+))(I(?P<iprio>\d+)_(?P<image>\S+))|(H_(?P<hostname>\S+)))(\.(?P<op>cat|udiff))?)?$)")

    def __index__(self):
        pass

class Repository(object):
    def __init__(self,path):
        # we need to figure out when to rerun this code
        self.path = path
        dirs = [path]
        self.entries = {}
        # we can locate file locations by searching for :info files
        while dirs:
            el = listdir(dirs[0])
            for entry in el:
                s = stat("%s/%s"%(dirs[0],entry))
                if S_ISDIR(s[ST_MODE]):
                    dirs.append("%s/%s"%(dirs[0],entry))
            if ':info' in el:
                print dirs[0]
                self.entries[dirs[0][len(path):]] = DirectoryBacked(dirs[0])                
            dirs = dirs[1:]

class cfg(Generator):
    __name__ = 'cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __build__ = {}

    def __setup__(self):
        self.repo = Repository(self.data)

    
