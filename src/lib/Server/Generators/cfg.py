#!/usr/bin/env python

'''This module implements a config file repository'''
__revision__ = '$Revision$'

from binascii import b2a_base64
from os import stat
from re import compile as regcompile
from stat import S_ISDIR, ST_MODE

from Bcfg2.Server.Generator import Generator, DirectoryBacked, FileBacked
from Bcfg2.Server.Metadata import Metadata

class CfgFileException(Exception):
    pass

class FileEntry(FileBacked):
    '''The File Entry class pertains to the config files contained in a particular directory.
    This includes :info, all base files and deltas'''
    
    def __init__(self, name, metadata):
        FileBacked.__init__(self, name)
        self.metadata = metadata

    def Applies(self, other):
        '''redirect to metadata.Applies'''
        return self.metadata.Applies(other)

    def __cmp__(self, other):
        '''figure out if self is more or less specific than other'''
        return self.metadata.__cmp__(other.metadata)

class ConfigFileEntry(object):
    '''ConfigFileEntry is a repository entry for a single file, containing
    all data for all clients.'''
    mx = regcompile("(^(?P<filename>.*)(\.((B(?P<bprio>\d+)_(?P<bundle>\S+))|(A(?P<aprio>\d+)_(?P<attr>\S+))|(I(?P<iprio>\d+)_(?P<image>\S+))|(I(?P<cprio>\d+)_(?P<class>\S+))|(H_(?P<hostname>\S+)))(\.(?P<op>cat|udiff))?)?$)")
    info = regcompile('^owner:(\s)*(?P<owner>\w+)|group:(\s)*(?P<group>\w+)|perms:(\s)*(?P<perms>\w+)|encoding:(\s)*(?P<encoding>\w+)|(?P<paranoid>paranoid(\s)*)$')
    
    def __init__(self, path):
        object.__init__(self)
        self.path = path
        self.basefiles = []
        self.deltas = []
        self.encoding = 'ascii'
        self.owner = 'root'
        self.group = 'root'
        self.perms = '0644'
        self.paranoid = False

    def read_info(self, filename):
        '''read in :info metadata'''
        for line in open(filename).readlines():
            match = self.info.match(line)
            if not match:
                continue
            else:
                mgd = match.groupdict()
                if mgd['owner']:
                    self.owner = mgd['owner']
                elif mgd['group']:
                    self.group = mgd['group']
                elif mgd['encoding']:
                    self.encoding = mgd['encoding']
                elif mgd['perms']:
                    self.perms = mgd['perms']
                    if len(self.perms) == 3:
                        self.perms = "0%s" % (self.perms)
                elif mgd['paranoid']:
                    self.paranoid = True

    def AddEntry(self, name):
        '''add new file additions for a single cf file'''
        if name[-5:] == ':info':
            return self.read_info(name)

        g = self.mx.match(name)
        if g == None:
            print "match failed for file name %s" % (name)
            return

        data = {}
        for attr in ['bundle', 'attr', 'hostname', 'class']:
            if g.group(attr) != None:
                data[attr] = g.group(attr)
        if data == {}:
            all = True
        else:
            all = False
        # metadata args (global, image, classes, bundles, attributes, hostname)
        arg = (all, data.get('image', None))
        for mtype in ['class', 'bundle', 'attr']:
            arg = arg + (data.get(mtype, []),)
        arg = arg + (data.get('hostname', None),)
        m = apply(Metadata, arg)
        if g.group("op") != None:
            self.deltas.append(FileEntry(name, m))
            # need to sort here
        else:
            self.basefiles.append(FileEntry(name, m))
            # need to sort here

    def HandleEvent(self, event):
        '''Handle FAM updates'''
        action = event.code2str()
        if event.filename[-5:] == ':info':
            return self.read_info(event.filename)
        for l in [self.basefiles, self.deltas]:
            for entry in l:
                if entry.name.split('/')[-1] == event.filename:
                    if action == 'changed':
                        entry.HandleEvent(event)
                    elif action == 'deleted':
                        l.remove(entry)
                    else:
                        print "unhandled action %s" % (action)

    def GetConfigFile(self, entry, metadata):
        '''Fetch config file from repository'''
        name = entry.attrib['name']
        filedata = ""
        # first find basefile
        try:
            basefile = [x for x in self.basefiles if x.Applies(metadata)][0]
        except IndexError:
            raise CfgFileException, ('basefile', name)
        filedata += basefile.data

        # find applicable deltas
        deltas = [x for x in self.deltas if x.Applies(metadata)]
        # filter for more specific
        for delta in deltas:
            pass
        # apply diffs, etc
        entry.attrib.update({'owner':self.owner, 'group':self.group,
                             'perms':self.perms, 'encoding':self.encoding})
        if self.paranoid:
            entry.attrib['paranoid'] = 'true'
        if self.encoding == 'base64':
            entry.text = b2a_base64(filedata)
        else:
            entry.text = filedata

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
        # eventually flush fam events here so that all entries built here
        # ready to go

    def AddDirectoryMonitor(self, name):
        '''Add new directory to FAM structures'''
        if name not in self.directories:
            try:
                stat(name)
            except OSError:
                print "Failed to open %s" % (name)
                return
            reqid = self.fam.AddMonitor(name, self)
            self.famID[reqid] = name
            self.directories.append(name)

    def AddEntry(self, name):
        '''Add new entry to FAM structures'''
        try:
            sdata = stat(name)[ST_MODE]
        except OSError:
            return

        if S_ISDIR(sdata):
            self.AddDirectoryMonitor(name)
        else:
            # file entries shouldn't contain path-to-repo
            shortname = '/'+ '/'.join(name[len(self.name)+1:].split('/')[:-1])
            if not self.entries.has_key(shortname):
                self.entries[shortname] = ConfigFileEntry(shortname)
                self.provides[shortname] = self.entries[shortname].GetConfigFile
            self.entries[shortname].AddEntry(name)
            #self.entries[shortname].HandleEvent()

    def HandleEvent(self, event):
        '''Handle FAM updates'''
        action = event.code2str()
        if event.filename[0] != '/':
            filename = "%s/%s" % (self.famID[event.requestID], event.filename)
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
            if event.filename == ':info':
                event.filename = filename
            if self.entries.has_key(configfile):
                self.entries[configfile].HandleEvent(event)
            else:
                syslog(LOG_INFO, "Ignoring event for %s"%(configfile))
        elif action == 'deleted':
            configfile = filename[len(self.name):-(len(event.filename)+1)]
            self.entries[configfile].HandleEvent(event)
        elif action in ['endExist']:
            pass
        else:
            print "Got unknown event %s %s %s" % (event.requestID, event.code2str(), event.filename)

class cfg(Generator):
    '''This generator manages the configuration file repository for bcfg2'''
    __name__ = 'cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {}

    def __setup__(self):
        self.repo = ConfigFileRepository(self.data, self.core.fam)
        self.__provides__['ConfigFile'] = self.repo.provides

    
