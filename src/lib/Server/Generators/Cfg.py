'''This module implements a config file repository'''
__revision__ = '$Revision$'

from binascii import b2a_base64
from os import stat
from re import compile as regcompile
from stat import S_ISDIR, ST_MODE
from syslog import syslog, LOG_INFO, LOG_ERR

from Bcfg2.Server.Generator import Generator, FileBacked

class CfgFileException(Exception):
    '''Raised for repository errors'''
    pass

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
        return most1 - most2

class ConfigFileEntry(object):
    '''ConfigFileEntry is a repository entry for a single file, containing
    all data for all clients.'''
    specific = regcompile('(.*/)(?P<filename>[\w.]+)\.((H_(?P<hostname>\w+))|(B(?P<bprio>\d+)_(?P<bundle>\w+))|(A(?P<aprio>\d+)_(?P<attr>\w+))|(I(?P<iprio>\d+)_(?P<image>\w+))|(C(?P<cprio>\d+)_(?P<class>\w+)))(\.(?P<op>cat|udiff))?')
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

        if name.split('/')[-1] == self.path.split('/')[-1]:
            self.basefiles.append(FileEntry(name, True, None, [], [], [], None))
            return

        specmatch = self.specific.match(name)
        if specmatch == None:
            syslog(LOG_ERR, "Failed to match file %s" % (name))
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
        if event.filename[-5:] == ':info':
            return self.read_info(event.filename)
        for entry in self.basefiles + self.deltas:
            if entry.name.split('/')[-1] == event.filename:
                if action == 'changed':
                    syslog(LOG_INFO, "File %s changed" % event.filename)
                    entry.HandleEvent(event)
                elif action == 'deleted':
                    [flist.remove(entry) for flist in [self.basefiles, self.deltas] if entry in flist]
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
            raise CfgFileException, ('basefile', name)
        filedata += basefile.data

        # find applicable deltas
        #deltas = [x for x in self.deltas if x.Applies(metadata)]
        # filter for more specific
        #for delta in deltas:
        #    pass
        # apply diffs, etc
        entry.attrib.update({'owner':self.owner, 'group':self.group,
                             'perms':self.perms, 'encoding':self.encoding})
        if self.paranoid:
            entry.attrib['paranoid'] = 'true'
        if self.encoding == 'base64':
            entry.text = b2a_base64(filedata)
        else:
            entry.text = filedata

class ConfigFileRepository(object):
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
                syslog(LOG_ERR, "Failed to open directory %s" % (name))
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

        if ((action == 'exists') and (filename != self.name)):
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
                if filename != self.name:
                    self.AddEntry(filename)
                else:
                    syslog(LOG_INFO, "Ignoring event for %s"%(configfile))
        elif action == 'deleted':
            configfile = filename[len(self.name):-(len(event.filename)+1)]
            self.entries[configfile].HandleEvent(event)
        elif action in ['exists', 'endExist']:
            pass
        else:
            syslog(LOG_ERR, "Got unknown event %s %s:%s" % (action, event.requestID, event.filename))

class Cfg(Generator):
    '''This generator manages the configuration file repository for bcfg2'''
    __name__ = 'Cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {}

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        self.repo = ConfigFileRepository(self.data, self.core.fam)
        self.__provides__ = {'ConfigFile':self.repo.provides}

    
