#!/usr/bin/env python

class GeneratorError(Exception):
    pass

class Generator(object):
    '''This is a class that generators can be subclassed off of.'''
    __name__ = None
    __version__ = '$Id: $'
    __datastore__ = '/tmp/data'
    __build__ = {}
    
    def __init__(self):
        self.data="%s/%s"%(self.__datastore__,self.__name__)
        print "%s loaded"%(self.__name__)

    def Cron(self):
        '''Cron defines periodic tasks to maintain data coherence'''
        pass

    def Build(self,filename,client):
        '''Build will construct a Config File object for client.'''
        if self.__build__.has_key(filename):
            self.__build__[filename](filename,client)
        else:
            raise GeneratorError, ("Key",filename)

    def Publish(self,key,value):
        pass

    def Fetch(self,key):
        pass

    def GetMetadata(self,client,field):
        '''GetMetadata returns current metadata file client. Field can be one of:
        image, tags, bundles'''
        pass

    def Notify(self,region):
        '''Generate change notification for region'''
        pass
