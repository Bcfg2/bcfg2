#!/usr/bin/env python
# $Id$

from syslog import syslog, LOG_ERR

class GeneratorError(Exception):
    pass

class Generator(object):
    '''This is a class that generators can be subclassed from.
    __name__, __version__, and __author__ must be set for the module
    __build__ is a dictionary mapping filename to generator function
    __requires__ is a set of external published data needed for operation'''
    
    __name__ = None
    __version__ = None
    __datastore__ = '/home/desai/data/b2'
    __build__ = {}
    __requires__ = []
    
    def __init__(self, container):
        self.container=container
        self.data="%s/%s"%(self.__datastore__,self.__name__)
        self.PublishAll()

    def CompleteSetup(self):
        self.ReadAll()
        print "%s loaded"%(self.__version__)

    def Cron(self):
        '''Cron defines periodic tasks to maintain data coherence'''
        pass

    def Build(self,filename,client):
        '''Build will construct a Config File object for client.'''
        if self.__build__.has_key(filename):
            return getattr(self,self.__build__[filename])(filename,client)
        else:
            raise GeneratorError, ("Key",filename)

    def Publish(self,key,value):
        self.container.Publish(self.__name__,key,value)

    def PublishAll(self):
        pass

    def Read(self,key):
        self.container.ReadValue(key)

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

class PublishError(Exception):
    pass

class PublishedValue(object):
    def __init__(self,owner,key,value):
        self.owner=owner
        self.key=key
        self.value=value

    def Update(self,owner,value):
        if owner != self.owner:
            raise PublishError, (self.key,owner)
        self.value=value

class GeneratorContainer(object):
    def __init__(self):
        self.pubspace={}
        self.generators=[]
        # we need to setup publish, read interface
        # we need to inventory and setup generators
        pass

    def PublishValue(self,owner,key,value):
        if not self.pubspace.has_key(key):
            # This is a new entry
            self.pubspace[key]=PublishedValue(owner,key,value)
        else:
            # This is an old entry. Update can fai
            try:
                self.pubspace[key].Update(owner,value)
            except PublishError,e:
                syslog(LOG_ERR, "Publish conflict for %s. Owner %s, Modifier %s"%(key,self.pubspace[key].owner,owner))

    def ReadValue(self,key):
        if self.pubspace.has_key(key):
            return self.pubspace[key].value
        raise KeyError,key

    def LoadGenerators(self,genlist):
        for generator in genlist:
            self.generators.append(generator(self))
        for generator in self.generators:
            generator.CompleteSetup()
        self.handles={}
        for g in self.generators:
            for f in g.__build__.keys():
                self.handles[f]=g

    def GetConfigFile(self,filename,client):
        if self.handles.has_key(filename):
            return self.handles[filename].Build(filename,client)
        raise KeyError, filename
