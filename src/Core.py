#!/usr/bin/python
# $Id$

from os import stat
from stat import ST_MODE, S_ISDIR
from syslog import syslog, LOG_ERR

from Error import PublishError

import _fam

class fam(object):
    '''The fam object contains alteration monitors'''
    
    def __init__(self):
        self.fm = _fam.open()
        self.users = {}
        self.handles = {}

    def fileno(self):
        return self.fm.fileno()

    def AddMonitor(self, path, obj=None):
        m = stat(path)[ST_MODE]
        if S_ISDIR(m):
            h = self.fm.monitorDirectory(path, None)
            self.handles[h.requestID()] = h
        else:
            h = self.fm.monitorFile(path, None)
            self.handles[h.requestID()] = h
        if obj != None:
            self.users[h.requestID()] = obj
        return h.requestID()

    def HandleEvent(self):
        event = self.fm.nextEvent()
        id = event.requestID
        if self.users.has_key(id):
            self.users[id].HandleEvent(event)

class PublishedValue(object):
    def __init__(self,owner,key,value):
        self.owner=owner
        self.key=key
        self.value=value

    def Update(self,owner,value):
        if owner != self.owner:
            raise PublishError, (self.key,owner)
        self.value=value

class Core(object):
    def __init__(self, repository, generators):
        self.datastore = repository
        self.fam = fam()
        self.pubspace = {}
        self.generators = []
        for generator in generators:
            g = getattr(__import__(generator),generator)
            self.generators.append(g(self, self.datastore))
        # we need to inventory and setup generators
        # Process generator requirements
        for g in self.generators:
            for prq in g.__requires__:
                if not self.pubspace.has_key(prq):
                    raise GeneratorError, (g.name, prq)
            g.CompleteSetup()

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

    def GetEntry(self, key1, key2):
        for d in map(lambda x:x.__provides__, self.generators):
            if d.has_key(key1):
                if d[key1].has_key(key2):
                    return d[key1][key2]
        raise KeyError, (key1, key2)

    def GetConfigFile(self,filename,metadata):
        try:
            self.Get("ConfigFile", filename, metadata)
        except:
            raise KeyError, filename

    def Get(self,type,name,metadata):
        return self.GetEntry(type, name)(name, metadata)

