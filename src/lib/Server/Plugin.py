'''This module provides the baseclass for Bcfg2 Server Plugins'''
__revision__ = '$Revision:$'

from lxml.etree import XML, XMLSyntaxError
from os import stat
from stat import ST_MTIME
from syslog import syslog, LOG_ERR, LOG_INFO

class PluginInitError(Exception):
    '''Error raised in cases of Plugin initialization errors'''
    pass

class PluginExecutionError(Exception):
    '''Error raised in case of Plugin execution errors'''
    pass

class Plugin(object):
    '''This is the base class for all Bcfg2 Server plugins. Several attributes must be defined
    in the subclass:
    __name__ : the name of the plugin
    __version__ : a version string
    __author__ : the author/contact for the plugin

    Plugins can provide three basic types of functionality:
      - Structure creation (overloading BuildStructures)
      - Configuration entry binding (overloading HandlesEntry, or loads the Entries table)
      - Data collection (overloading GetProbes/ReceiveData)
    '''
    __name__ = 'Plugin'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __rmi__ = []

    def __init__(self, core, datastore):
        object.__init__(self)
        self.Entries = {}
        self.core = core
        self.data = "%s/%s" % (datastore, self.__name__)

    def LogError(self, msg):
        '''Log error message tagged with Plugin name'''
        syslog(LOG_ERR, "%s: %s" % (self.__name__, msg))

    def BuildStructures(self, metadata):
        '''Build a set of structures tailored to the client metadata'''
        return []

    def GetProbes(self, metadata):
        '''Return a set of probes for execution on client'''
        return []

    def ReceiveData(self, metadata, data):
        '''Receive probe results pertaining to client'''
        pass

# the rest of the file contains classes for coherent file caching

class FileBacked(object):
    '''This object caches file data in memory.
    HandleEvent is called whenever fam registers an event.
    Index can parse the data into member data as required.
    This object is meant to be used as a part of DirectoryBacked.'''
    
    def __init__(self, name):
        object.__init__(self)
        self.data = ''
        self.name = name
        self.mtime = 0
        #self.readonce = 0
        #self.HandleEvent()

    def HandleEvent(self, event=None):
        '''Read file upon update'''
        oldmtime = self.mtime
        try:
            self.mtime = stat(self.name)[ST_MTIME]
        except OSError:
            syslog(LOG_ERR, "Failed to stat file %s" % (self.name))
            
        if self.mtime > oldmtime:
            try:
            #    if self.readonce == 0:
            #        self.readonce = 1
            #    else:
            #        syslog(LOG_INFO, "Updated file %s" % (self.name))
                self.data = file(self.name).read()
            except IOError:
                syslog(LOG_ERR, "Failed to read file %s" % (self.name))
            self.Index()

    def Index(self):
        '''Update local data structures based on current file state'''
        pass

class DirectoryBacked(object):
    '''This object is a coherent cache for a filesystem hierarchy of files.'''
    __child__ = FileBacked

    def __init__(self, name, fam):
        object.__init__(self)
        self.name = name
        self.fam = fam
        self.entries = {}
        self.inventory = False
        fam.AddMonitor(name, self)

    def __getitem__(self, key):
        return self.entries[key]

    def __iter__(self):
        return self.entries.iteritems()

    def AddEntry(self, name):
        '''Add new entry to data structures upon file creation'''
        if name == '':
            syslog(LOG_INFO, "got add for empty name")
        elif self.entries.has_key(name):
            syslog(LOG_INFO, "got multiple adds for %s" % name)
        else:
            if ((name[-1] == '~') or (name[:2] == '.#') or (name == 'SCCS') or (name[-4:] == '.swp')):
                return
            self.entries[name] = self.__child__('%s/%s' % (self.name, name))
            self.entries[name].HandleEvent()

    def HandleEvent(self, event):
        '''Propagate fam events to underlying objects'''
        action = event.code2str()
        if event.filename == '':
            syslog(LOG_INFO, "Got event for blank filename")
            return
        if action == 'exists':
            if event.filename != self.name:
                self.AddEntry(event.filename)
        elif action == 'created':
            self.AddEntry(event.filename)
        elif action == 'changed':
            if self.entries.has_key(event.filename):
                self.entries[event.filename].HandleEvent(event)
        elif action == 'deleted':
            if self.entries.has_key(event.filename):
                del self.entries[event.filename]
        elif action in ['endExist']:
            pass
        else:
            print "Got unknown event %s %s %s" % (event.requestID, event.code2str(), event.filename)

class XMLFileBacked(FileBacked):
    '''This object is a coherent cache for an XML file to be used as a part of DirectoryBacked.'''
    __identifier__ = 'name'

    def __init__(self, filename):
        self.label = "dummy"
        self.entries = []
        FileBacked.__init__(self, filename)

    def Index(self):
        '''Build local data structures'''
        try:
            xdata = XML(self.data)
        except XMLSyntaxError:
            syslog(LOG_ERR, "Failed to parse %s"%(self.name))
            return
        self.label = xdata.attrib[self.__identifier__]
        self.entries = xdata.getchildren()

    def __iter__(self):
        return iter(self.entries)

class SingleXMLFileBacked(XMLFileBacked):
    '''This object is a coherent cache for an independent XML File.'''
    def __init__(self, filename, fam):
        XMLFileBacked.__init__(self, filename)
        fam.AddMonitor(filename, self)

class ScopedXMLFile(SingleXMLFileBacked):
    '''Scoped XML files are coherent files with Metadata structured data'''
    __containers__ = ['Class', 'Host', 'Image']

    def __init__(self, filename, fam):
        self.store = {}
        self.__provides__ = {}
        SingleXMLFileBacked.__init__(self, filename, fam)

    def StoreRecord(self, metadata, entry):
        '''Store scoped record based on metadata'''
        if not self.store.has_key(entry.tag):
            self.store[entry.tag] = {}
        if not self.store[entry.tag].has_key(entry.attrib['name']):
            self.store[entry.tag][entry.attrib['name']] = []
        self.store[entry.tag][entry.attrib['name']].append((metadata, entry))
    
    def Index(self):
        '''Build internal data structures'''
        try:
            xdata = XML(self.data)
        except XMLSyntaxError, msg:
            syslog(LOG_ERR, "Failed to parse %s"%(self.name))
            syslog(LOG_ERR, msg)
            return
        self.store = {}
        for entry in xdata.getchildren():
            if entry.tag not in self.__containers__:
                self.StoreRecord(('Global','all'), entry)
            else:
                name = (entry.tag, entry.get('name'))
                [self.StoreRecord(name, child) for child in entry.getchildren()]
        # now to build the __provides__ table
        for key in self.__provides__.keys():
            del self.__provides__[key]
        for key in self.store.keys():
            self.__provides__[key] = {}
            for name in self.store[key].keys():
                self.__provides__[key][name] = self.FetchRecord
                # also need to sort all leaf node lists
                self.store[key][name].sort(self.Sort)

    def Sort(self, meta1, meta2):
        '''Sort based on specificity'''
        order = ['Global', 'Image', 'Profile', 'Class', 'Host']
        return order.index(meta1[0][0]) - order.index(meta2[0][0])

    def MatchMetadata(self, mdata, metadata):
        '''Match internal metadata representation against metadata'''
        (mtype, mvalue) = mdata
        if mtype == 'Global':
            return True
        elif mtype == 'Profile':
            if mvalue == metadata.profile:
                return True
        elif mtype == 'Image':
            if mvalue == metadata.image:
                return True
        elif mtype == 'Class':
            if mvalue in metadata.classes:
                return True
        elif mtype == 'Host':
            if mvalue == metadata.hostname:
                return True
        return False

    def FetchRecord(self, entry, metadata):
        '''Build a data for specified metadata'''
        dlist = self.store[entry.tag][entry.get('name')]
        useful = [ent for ent in dlist if self.MatchMetadata(ent[0], metadata)]
        if not useful:
            syslog(LOG_ERR, "Failed to FetchRecord %s:%s"%(entry.tag, entry.get('name')))
        else:
            data = useful[-1][-1]
            [entry.attrib.__setitem__(x, data.attrib[x]) for x in data.attrib]
