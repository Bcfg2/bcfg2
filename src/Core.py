#!/usr/bin/python
# $Id$

from syslog import syslog, LOG_ERR

from Error import PublishError

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
    def __init__(self, generators):
        self.handles = {}
        self.pubspace = {}
        self.generators = []
        for generator in generators:
            self.generators.append(generator(self))
        # we need to inventory and setup generators
        # Process generator requirements
        for g in self.generators:
            for prq in g.__requires__:
                if not self.pubspace.has_key(prq):
                    raise GeneratorError, (g.name, prq)
            g.CompleteSetup()
            for f in g.__build__.keys():
                self.handles[f] = g

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

    def GetConfigFile(self,filename,client):
        if self.handles.has_key(filename):
            return self.handles[filename].Build(filename,client)
        raise KeyError, filename
