#!/usr/bin/env python
# $Id$

from elementtree.ElementTree import XML
from syslog import syslog, LOG_ERR

class Generator(object):
    '''This is a class that generators can be subclassed from.
    __name__, __version__, and __author__ must be set for the module
    __provides__ is a dictionary mapping listing the entity type and name to a function name
    __requires__ is a set of external published data needed for operation'''
    
    __name__ = None
    __version__ = None
    __provides__ = {}
    __requires__ = []
    
    def __init__(self, core, datastore):
        self.core = core
        self.data = "%s/%s"%(datastore,self.__name__)
        self.__setup__()

    def __setup__(self):
        '''This method must be overloaded during subclassing.
        All module specific setup, including all publication, occurs here.'''

    def CompleteSetup(self):
        self.ReadAll()
        print "%s loaded"%(self.__version__)

    def Cron(self):
        '''Cron defines periodic tasks to maintain data coherence'''
        pass

    def Publish(self,key,value):
        self.core.Publish(self.__name__,key,value)

    def Read(self,key):
        self.core.ReadValue(key)

    def ReadAll(self):
        self.external = {}
        for field in self.__requires__:
            self.external[field] = self.Read(field)

    def GetMetadata(self,client,field):
        '''GetMetadata returns current metadata file client. Field can be one of:
        image, tags, bundles'''
        pass

    def Notify(self,region):
        '''Generate change notification for region'''
        pass

    def GetProbes(self, metadata):
        return []

    def AcceptProbeData(self, client, probedata):
        return

class FileBacked(object):
    '''This object caches file data in memory.
    HandleEvent is called whenever fam registers an event.
    Index can parse the data into member data as required.
    This object is meant to be used as a part of DirectoryBacked.'''
    
    def __init__(self, name):
        self.name = name
        self.HandleEvent()

    def HandleEvent(self, event=None):
        self.data = file(self.name).read()
        self.Index()

    def Index(self):
        pass

class DirectoryBacked(object):
    '''This object is a coherent cache for a filesystem hierarchy of files.'''
    __child__ = FileBacked

    def __init__(self, name, fam):
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
            self.entries[name] = self.__child__('%s/%s'%(self.name, name))
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
            print "Got unknown event %s %s %s"%(event.requestID, event.code2str(), event.filename)

class XMLFileBacked(FileBacked):
    '''This object is a coherent cache for an XML file to be used as a part of DirectoryBacked.'''
    __identifier__ = 'name'

    def Index(self):
        a = XML(self.data)
        self.label = a.attrib[self.__identifier__]
        self.entries = a.getchildren()

    def __iter__(self):
        return iter(self.entries)

class SingleXMLFileBacked(XMLFileBacked):
    '''This object is a coherent cache for an independent XML File.'''
    def __init__(self,filename,fam):
        XMLFileBacked.__init__(self, filename)
        fam.AddMonitor(filename, self)


