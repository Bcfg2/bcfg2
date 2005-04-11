'''This module implements a config file repository'''
__revision__ = '$Revision$'

from binascii import b2a_base64
from os import stat
from re import compile as regcompile
from stat import S_ISDIR, ST_MODE
from syslog import syslog, LOG_INFO, LOG_ERR

from Bcfg2.Server.Generator import Generator, GeneratorError, FileBacked

class FileEntry(FileBacked):
    '''The File Entry class pertains to the config files contained in a particular directory.
    This includes :info, all base files and deltas'''
    
    def __init__(self, name, all, image, classes, bundles, attribs, hostname):
        FileBacked.__init__(self, name)
        self.all = all
        self.image = image
        self.bundles = bundles
        self.classes = classes
        self.attributes = attribs
        self.hostname = hostname

    def __cmp__(self, other):
        fields = ['all', 'image', 'classes', 'bundles', 'attributes', 'hostname']
        try:
            most1 = [index for index in range(len(fields)) if getattr(self, fields[index])][0]
        except IndexError:
            most1 = 0
        try:
            most2 = [index for index in range(len(fields)) if getattr(other, fields[index])][0]
        except IndexError:
            most2 = 0
        if most1 == most2:
            if self.name.split('.')[-1][0] not in ['C', 'B']:
                return 0
            # need to tiebreak with numeric prio
            prio1 = int(self.name.split('.')[-1][1:3])
            prio2 = int(other.name.split('.')[-1][1:3])
            return prio1 - prio2
        else:
            return most1 - most2

class ConfigFileEntry(object):
    '''ConfigFileEntry is a repository entry for a single file, containing
    all data for all clients.'''
    specific = regcompile('(.*/)(?P<filename>[\S\-.]+)\.((H_(?P<hostname>\S+))|' +
                          '(B(?P<bprio>\d+)_(?P<bundle>\S+))|(A(?P<aprio>\d+)_(?P<attr>\S+))|' +
                          '(I_(?P<image>\S+))|(C(?P<cprio>\d+)_(?P<class>\S+)))' +
                          '(\.(?P<op>cat|udiff))?$')
    info = regcompile('^owner:(\s)*(?P<owner>\w+)|group:(\s)*(?P<group>\w+)|' +
                      'perms:(\s)*(?P<perms>\w+)|encoding:(\s)*(?P<encoding>\w+)|' +
                      '(?P<paranoid>paranoid(\s)*)$')
    
    def __init__(self, path, repopath):
        object.__init__(self)
        self.path = path
        self.repopath = repopath
        self.basefiles = []
        self.deltas = []
        self.metadata = {'encoding': 'ascii', 'owner':'root', 'group':'root', 'perms':'0644'}
        self.paranoid = False

    def read_info(self):
        '''read in :info metadata'''
        filename = "%s/:info" % self.repopath
        for line in open(filename).readlines():
            match = self.info.match(line)
            if not match:
                continue
            else:
                mgd = match.groupdict()
                if mgd['owner']:
                    self.metadata['owner'] = mgd['owner']
                elif mgd['group']:
                    self.metadata['group'] = mgd['group']
                elif mgd['encoding']:
                    self.metadata['encoding'] = mgd['encoding']
                elif mgd['perms']:
                    self.metadata['perms'] = mgd['perms']
                    if len(self.metadata['perms']) == 3:
                        self.metadata['perms'] = "0%s" % (self.metadata['perms'])
                elif mgd['paranoid']:
                    self.paranoid = True

    def AddEntry(self, name):
        '''add new file additions for a single cf file'''
        if name[-5:] == ':info':
            return self.read_info()

        if name.split('/')[-1] == self.path.split('/')[-1]:
            self.basefiles.append(FileEntry(name, True, None, [], [], [], None))
            return

        specmatch = self.specific.match(name)
        if specmatch == None:
            syslog(LOG_ERR, "Cfg: Failed to match file %s" % (name))
            return

        data = {}
        for item, value in specmatch.groupdict().iteritems():
            if value != None:
                data[item] = value

        cfile = FileEntry(name, False, data.get('image', None), data.get('class', []),
                          data.get('bundle', []), data.get('attr', []), data.get('hostname', None))

        if specmatch.group("op") != None:
            self.deltas.append(cfile)
            self.deltas.sort()
        else:
            self.basefiles.append(cfile)
            self.basefiles.sort()

    def HandleEvent(self, event):
        '''Handle FAM updates'''
        action = event.code2str()
        if event.filename == ':info':
            return self.read_info()
        if event.filename != self.path.split('/')[-1]:
            if not self.specific.match('/' + event.filename):
                syslog(LOG_INFO, 'Cfg: Suppressing event for bogus file %s' % event.filename)
                return

        entries = [entry for entry in self.basefiles + self.deltas if
                   entry.name.split('/')[-1] == event.filename]

        if len(entries) == 0:
            syslog(LOG_ERR, "Cfg: Failed to match entry for spec %s" % (event.filename))
        elif len(entries) > 1:
            syslog(LOG_ERR, "Cfg: Matched multiple entries for spec %s" % (event.filename))
            
        if action == 'deleted':
            syslog(LOG_INFO, "Cfg: Removing entry %s" % event.filename)
            for entry in entries:
                syslog(LOG_INFO, "Cfg: Removing entry %s" % (entry.name))
                if entry in self.basefiles:
                    self.basefiles.remove(entry)
                if entry in self.deltas:
                    self.deltas.remove(entry)
            syslog(LOG_INFO, "Cfg: Entry deletion completed")
        elif action in ['changed', 'exists', 'created']:
            if action == 'changed':
                syslog(LOG_INFO, "Cfg: File %s changed" % event.filename)
            [entry.HandleEvent(event) for entry in entries]
        else:
            syslog(LOG_ERR, "Cfg: Unhandled Action %s for file %s" % (action, event.filename))

    def GetConfigFile(self, entry, metadata):
        '''Fetch config file from repository'''
        name = entry.attrib['name']
        filedata = ""
        # first find basefile
        try:
            basefile = [bfile for bfile in self.basefiles if metadata.Applies(bfile)][-1]
        except IndexError:
            syslog(LOG_ERR, "Cfg: Failed to locate basefile for %s" % name)
            raise GeneratorError, ('basefile', name)
        filedata += basefile.data

        # find applicable deltas
        #deltas = [x for x in self.deltas if x.Applies(metadata)]
        # filter for more specific
        #for delta in deltas:
        #    pass
        # apply diffs, etc
        entry.attrib.update(self.metadata)
        if self.paranoid:
            entry.attrib['paranoid'] = 'true'
        if self.metadata['encoding'] == 'base64':
            entry.text = b2a_base64(filedata)
        else:
            entry.text = filedata

class Cfg(Generator):
    '''This generator in the configuration file repository for bcfg2'''
    __name__ = 'Cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    tempfile = regcompile("^.*~$|^.*\.swp")

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        self.entries = {}
        self.__provides__ = {'ConfigFile':{}}
        self.famID = {}
        self.directories = []
        self.AddDirectoryMonitor(self.data)
        # eventually flush fam events here so that all entries built here
        # ready to go

    def AddDirectoryMonitor(self, name):
        '''Add new directory to FAM structures'''
        if name not in self.directories:
            try:
                stat(name)
            except OSError:
                self.LogError("Failed to open directory %s" % (name))
                return
            reqid = self.core.fam.AddMonitor(name, self)
            self.famID[reqid] = name
            self.directories.append(name)

    def AddEntry(self, name, event):
        '''Add new entry to FAM structures'''
        try:
            sdata = stat(name)[ST_MODE]
        except OSError:
            return

        if S_ISDIR(sdata):
            self.AddDirectoryMonitor(name)
        else:
            # file entries shouldn't contain path-to-repo
            shortname = '/'+ '/'.join(name[len(self.data)+1:].split('/')[:-1])
            repodir = '/' + '/'.join(name.split('/')[:-1])
            if not self.entries.has_key(shortname):
                self.entries[shortname] = ConfigFileEntry(shortname, repodir)
                self.__provides__['ConfigFile'][shortname] = self.entries[shortname].GetConfigFile
            self.entries[shortname].AddEntry(name)
            self.entries[shortname].HandleEvent(event)

    def HandleEvent(self, event):
        '''Handle FAM updates'''
        action = event.code2str()
        if self.tempfile.match(event.filename):
            syslog(LOG_INFO, "Cfg: Suppressed event for file %s" % event.filename)
            return
        if event.filename[0] != '/':
            filename = "%s/%s" % (self.famID[event.requestID], event.filename)
        else:
            filename = event.filename
        configfile = filename[len(self.data):-(len(event.filename)+1)]

        if ((action in ['exists', 'created']) and (filename != self.data)):
            self.AddEntry(filename, event)
        elif action == 'changed':
            # pass the event down the chain to the ConfigFileEntry
            if self.entries.has_key(configfile):
                self.entries[configfile].HandleEvent(event)
            else:
                if filename != self.data:
                    self.AddEntry(filename, event)
                else:
                    self.LogError("Ignoring event for %s"%(configfile))
        elif action == 'deleted':
            self.entries[configfile].HandleEvent(event)
        elif action in ['exists', 'endExist']:
            pass
        else:
            self.LogError("Got unknown event %s %s:%s" % (action, event.requestID, event.filename))
