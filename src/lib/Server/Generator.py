'''This is a baseclass not intended for instantiation'''
__revision__ = '$Revision: 1.34 $'

from elementtree.ElementTree import XML
from syslog import syslog, LOG_ERR, LOG_INFO
from xml.parsers.expat import ExpatError
from os import stat
from stat import ST_MTIME

class GeneratorError(Exception):
    '''Generator runtime error used to inform upper layers of internal generator failure'''
    pass

class GeneratorInitError(Exception):
    '''Constructor time error that allows the upper layer to proceed in the face of
    generator initialization failures'''
    pass

class Generator(object):
    '''This is a class that generators can be subclassed from.
    __name__, __version__, and __author__ must be set for the module
    __provides__ is a dictionary mapping listing the entity type and name to a function name
    __requires__ is a set of external published data needed for operation
    __croninterval__ is the frequency in second with which the Cron method should be executed'''
    
    __name__ = None
    __version__ = None
    __croninterval__ = False
    __provides__ = {}
    __requires__ = []
    
    def __init__(self, core, datastore):
        object.__init__(self)
        self.core = core
        self.data = "%s/%s" % (datastore, self.__name__)
        self.external = {}

    def LogError(self, msg):
        syslog(LOG_ERR, "%s: %s" % (self.__name__, msg))

    def CompleteSetup(self):
        '''Read any external required publication data'''
        self.ReadAll()

    def Cron(self):
        '''Cron defines periodic tasks to maintain data coherence'''
        pass

    def Publish(self, key, value):
        '''publish a value for external consumption'''
        self.core.Publish(self.__name__, key, value)

    def Read(self, key):
        '''Read a publication value'''
        self.core.ReadValue(key)

    def ReadAll(self):
        '''Read all required publication values'''
        for field in self.__requires__:
            self.external[field] = self.Read(field)

    def Notify(self, region):
        '''Generate change notification for region'''
        pass

    def get_probes(self, client):
        '''Get appropriate probes for client'''
        return []

    def accept_probe_data(self, client, probedata):
        '''Recieve probe response for client'''
        return

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
                self.Index()
            except IOError:
                syslog(LOG_ERR, "Failed to read file %s" % (self.name))

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
        if self.entries.has_key(name):
            syslog(LOG_INFO, "got multiple adds for %s" % name)
        else:
            if ((name[-1] == '~') or (name[:2] == '.#') or (name == 'SCCS') or (name[-4:] == '.swp')):
                return
            self.entries[name] = self.__child__('%s/%s' % (self.name, name))
            self.entries[name].HandleEvent()

    def HandleEvent(self, event):
        '''Propagate fam events to underlying objects'''
        action = event.code2str()
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
        except ExpatError:
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
        except ExpatError, msg:
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
        smap = {('Global','Host'):-1, ('Global','Image'):-1, ("Global",'Class'):-1,
                ('Image', 'Global'):1, ('Image', 'Image'):0, ('Image', 'Host'):1, ('Image', 'Class'):-1,
                ('Class','Global'):1, ('Class', 'Image'):1, ('Class','Class'):0, ('Class', 'Host'): -1,
                ('Host', 'Global'):1, ('Host', 'Image'):1, ('Host','Class'):1, ('Host','Host'):0}
        if smap.has_key((meta1[0][0],  meta2[0][0])):
            return smap[(meta1[0][0], meta2[0][0])]

    def MatchMetadata(self, mdata, metadata):
        '''Match internal metadata representation against metadata'''
        (mtype, mvalue) = mdata
        if mtype == 'Global':
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
            entry.attrib.update(data.attrib)
