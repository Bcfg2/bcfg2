'''This is a baseclass not intended for instantiation'''
__revision__ = '$Revision$'

from elementtree.ElementTree import XML
from syslog import syslog, LOG_ERR

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
        self.__setup__()

    def __setup__(self):
        '''This method must be overloaded during subclassing.
        All module specific setup, including all publication, occurs here.'''

    def CompleteSetup(self):
        self.ReadAll()
        print "%s loaded" % (self.__version__)

    def Cron(self):
        '''Cron defines periodic tasks to maintain data coherence'''
        pass

    def Publish(self, key, value):
        self.core.Publish(self.__name__, key, value)

    def Read(self, key):
        self.core.ReadValue(key)

    def ReadAll(self):
        self.external = {}
        for field in self.__requires__:
            self.external[field] = self.Read(field)

    def GetMetadata(self, client, field):
        '''GetMetadata returns current metadata file client. Field can be one of:
        image, tags, bundles'''
        pass

    def Notify(self, region):
        '''Generate change notification for region'''
        pass

    def get_probes(self, metadata):
        return []

    def accept_probe_data(self, client, probedata):
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
        self.HandleEvent()

    def HandleEvent(self, event=None):
        try:
            self.data = file(self.name).read()
        except IOError:
            syslog(LOG_ERR, "Failed to read file %s" % (self.name))
        self.Index()

    def Index(self):
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
        if self.entries.has_key(name):
            print "got multiple adds"
        else:
            if ((name[-1] == '~') or (name[:2] == '.#') or (name == 'SCCS') or (name[-4:] == '.swp')):
                return
            self.entries[name] = self.__child__('%s/%s' % (self.name, name))
            self.entries[name].HandleEvent()

    def HandleEvent(self, event):
        action = event.code2str()
        if action == 'exists':
            if event.filename != self.name:
                self.AddEntry(event.filename)
        elif action == 'created':
            self.AddEntry(event.filename)
        elif action == 'changed':
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

    def Index(self):
        try:
            xdata = XML(self.data)
        except:
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
    __containers__ = ['Class', 'Host', 'Image']

    def StoreRecord(self, metadata, entry):
        if not self.store.has_key(entry.tag):
            self.store[entry.tag] = {}
        if not self.store[entry.tag].has_key(entry.attrib['name']):
            self.store[entry.tag][entry.attrib['name']] = []
        self.store[entry.tag][entry.attrib['name']].append((metadata, entry))
    
    def Index(self):
        try:
            xdata = XML(self.data)
        except:
            syslog(LOG_ERR, "Failed to parse %s"%(self.name))
            return
        self.store = {}
        for e in xdata.getchildren():
            if e.tag not in self.__containers__:
                self.StoreRecord(('Global','all'), e)
            else:
                m = (e.tag, e.attrib['name'])
                for entry in e.getchildren():
                    self.StoreRecord(m, entry)
        # now to build the __provides__ table
        self.__provides__ = {}
        for key in self.store.keys():
            self.__provides__[key] = {}
            for j in self.store[key].keys():
                self.__provides__[key][j] = self.FetchRecord
                # also need to sort all leaf node lists
                self.store[key][j].sort(self.Sort)

    def Sort(self, m1, m2):
        d = {('Global','Host'):-1, ('Global','Image'):-1, ("Global",'Class'):-1,
             ('Image', 'Global'):1, ('Image', 'Image'):0, ('Image', 'Host'):1, ('Image', 'Class'):-1,
             ('Class','Global'):1, ('Class', 'Image'):1, ('Class','Class'):0, ('Class', 'Host'): -1,
             ('Host', 'Global'):1, ('Host', 'Image'):1, ('Host','Class'):1, ('Host','Host'):0}
        if d.has_key((m1[0][0],  m2[0][0])):
            return d[(m1[0][0], m2[0][0])]

    def MatchMetadata(self, m, metadata):
        if m[0] == 'Global':
            return True
        elif m[0] == 'Image':
            if m[1] == metadata.image:
                return True
        elif m[0] == 'Class':
            if m[1] in metadata.classes:
                return True
        elif m[0] == 'Host':
            if m[1] == metadata.hostname:
                return True
        return False

    def FetchRecord(self, entry, metadata):
        l = self.store[entry.tag][entry.attrib['name']]
        useful = [x for x in l if self.MatchMetadata(x[0], metadata)]
        if not useful:
            syslog(LOG_ERR, "Failed to FetchRecord %s:%s"%(entry.tag, entry.get('name')))
        else:
            data = useful[-1][-1]
            entry.attrib.update(data.attrib)
