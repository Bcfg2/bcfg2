#!/usr/bin/env python

from os import stat
from re import compile
from stat import S_ISDIR, ST_MODE
from string import join

from Types import ConfigFile
from Generator import Generator
from GeneratorUtils import DirectoryBacked, FileBacked
from Metadata import Metadata

class FileEntry(FileBacked):
    '''The File Entry class pertains to the config files contained in a particular directory.
    This includes :info, all base files and deltas'''
    
    def __init__(self, name, metadata):
        FileBacked.__init__(self, name)
        self.metadata = metadata

    def Applies(self, other):
        return self.metadata.Applies(other)

    def __cmp__(self, other):
        '''figure out if self is more or less specific than other'''
        return self.metadata.__cmp__(other.metadata)

class ConfigFileEntry(object):
    mx = compile("(^(?P<filename>.*)(\.((B(?P<bprio>\d+)_(?P<bundle>\S+))|(T(?P<tprio>\d+)_(?P<tag>\S+))(I(?P<iprio>\d+)_(?P<image>\S+))|(H_(?P<hostname>\S+)))(\.(?P<op>cat|udiff))?)?$)")
    info = compile('^owner:(\s)*(?P<owner>\w+)|group:(\s)*(?P<group>\w+)|perms:(\s)*(?P<perms>\w+)|encoding:(\s)*(?P<encoding>\w+)$')
    
    def __init__(self, path):
        self.path = path
        self.basefiles = []
        self.deltas = []
        self.encoding = 'ascii'
        self.owner = 'root'
        self.group = 'root'
        self.perms = '644'

    def GetInfo(self, filename):
        for line in open(filename).readlines():
            m = self.info.match(line)
            if not m:
                continue
            else:
                d = m.groupdict()
                if d['owner']:
                    self.owner=d['owner']
                elif d['group']:
                    self.group=d['group']
                elif d['encoding']:
                    self.encoding=d['encoding']
                elif d['perms']:
                    self.perms=d['perms']
                    if len(self.perms) == 3:
                        self.perms="0%s"%(self.perms)

    def AddEntry(self, name):
        if name[-5:] == ':info':
            return self.GetInfo(name)

        g = self.mx.match(name)
        if g == None:
            print "match failed for file name %s"%(name)
            return

        data = {}
        for attr in ['bundle', 'tag', 'hostname']:
            if g.group(attr) != None: data[attr] = g.group(attr)
        if data == {}:
            all = True
        else:
            all = False
        arg = (all, 'linux') + tuple(map(lambda z:filter(lambda x:x, [data.get(z, None)]), ['bundle','tag'])) + \
        (data.get("hostname",None), )
        m = apply(Metadata, arg)
        if g.group("op") != None:
            self.deltas.append(FileEntry(name, m))
            # need to sort here
        else:
            self.basefiles.append(FileEntry(name, m))
            # need to sort here

    def HandleEvent(self, event):
        action = event.code2str()
        if event.filename == ':info':
            return self.GetInfo(event.filename)
        for l in [self.basefiles, self.deltas]:
            for entry in l:
                if entry.name.split('/')[-1] == event.filename:
                    if action == 'changed':
                        entry.HandleEvent(event)
                    elif action == 'deleted':
                        l.remove(entry)
                    else:
                        print "unhandled action %s"%(action)

    def GetConfigFile(self, name, metadata):
        filedata = ""
        # first find basefile
        try:
            basefile = filter(lambda x:x.Applies(metadata), self.basefiles)[0]
        except IndexError:
            raise CfgFileException, ('basefile', self.name)
        filedata += basefile.data

        # find applicable deltas
        deltas = filter(lambda x:x.Applies(metadata), self.deltas)
        # filter for more specific
        for delta in deltas:
            pass
        # apply diffs, etc
        return ConfigFile(self.path, self.owner, self.group, self.perms, filedata, self.encoding)

class ConfigFileRepository(DirectoryBacked):
    '''This class implements repos and all change handling'''

    def __init__(self, name, fam):
        self.name = name
        self.fam = fam
        self.entries = {}
        self.provides = {}
        self.famID = {}
        self.directories = []
        self.AddDirectoryMonitor(self.name)
        # eventually flush fam events here so that all generators come out of constructors
        # ready to go

    def AddDirectoryMonitor(self, name):
        if name not in self.directories:
            try:
                stat(name)
            except:
                print "Failed to open %s"%(name)
                return
            id = self.fam.AddMonitor(name, self)
            self.famID[id] = name
            self.directories.append(name)

    def AddEntry(self, name):
        if S_ISDIR(stat(name)[ST_MODE]):
            self.AddDirectoryMonitor(name)
        else:
            # file entries shouldn't contain path-to-repo
            shortname = '/'+ join(name[len(self.name)+1:].split('/')[:-1], '/')
            if not self.entries.has_key(shortname):
                self.entries[shortname] = ConfigFileEntry(shortname)
                self.provides[shortname] = self.entries[shortname].GetConfigFile
            self.entries[shortname].AddEntry(name)
            #self.entries[shortname].HandleEvent()

    def HandleEvent(self, event):
        action = event.code2str()
        if event.filename[0] != '/':
            filename = "%s/%s"%(self.famID[event.requestID], event.filename)
        else:
            filename = event.filename
        if action == 'exists':
            if filename != self.name:
                self.AddEntry(filename)
        elif action == 'created':
            self.AddEntry(filename)
        elif action == 'changed':
            # pass the event down the chain to the ConfigFileEntry
            configfile = filename[len(self.name):-(len(event.filename)+1)]
            self.entries[configfile].HandleEvent(event)
        elif action == 'deleted':
            configfile = filename[len(self.name):-(len(event.filename)+1)]
            self.entries[configfile].HandleEvent(event)
        elif action in ['endExist']:
            pass
        else:
            print "Got unknown event %s %s %s"%(event.requestID, event.code2str(), event.filename)

class cfg(Generator):
    __name__ = 'cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {}

    def __setup__(self):
        self.repo = ConfigFileRepository(self.data, self.core.fam)
        self.__provides__['ConfigFile'] = self.repo.provides

    
