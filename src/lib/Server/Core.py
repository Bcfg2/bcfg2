#!/usr/bin/python
# $Id$

'''Bcfg2.Server.Core provides the runtime support for bcfg2 modules'''
__revision__ = '$Revision$'

from os import stat
from stat import ST_MODE, S_ISDIR
from syslog import syslog, LOG_ERR
from time import time

import _fam

class GeneratorError(Exception):
    pass

class PublishError(Exception):
    pass

class fam(object):
    '''The fam object is a set of callbacks for file alteration events'''
    
    def __init__(self):
        self.fm = _fam.open()
        self.users = {}
        self.handles = {}

    def fileno(self):
        return self.fm.fileno()

    def AddMonitor(self, path, obj=None):
        mode = stat(path)[ST_MODE]
        if S_ISDIR(mode):
            handle = self.fm.monitorDirectory(path, None)
        else:
            handle = self.fm.monitorFile(path, None)
        self.handles[handle.requestID()] = handle
        if obj != None:
            self.users[handle.requestID()] = obj
        return handle.requestID()

    def HandleEvent(self):
        event = self.fm.nextEvent()
        reqid = event.requestID
        if self.users.has_key(reqid):
            self.users[reqid].HandleEvent(event)

class PublishedValue(object):
    def __init__(self, owner, key, value):
        self.owner = owner
        self.key = key
        self.value = value

    def Update(self, owner, value):
        if owner != self.owner:
            raise PublishError, (self.key, owner)
        self.value = value

class Core(object):
    def __init__(self, repository, structures, generators):
        object.__init__(self)
        self.datastore = repository
        self.fam = fam()
        self.pubspace = {}
        self.structures = []
        self.cron = {}
        for structure in structures:
            try:
                mod = getattr(__import__("Bcfg2.Server.Structures.%s" %
                                         (structure)).Server.Structures, structure)
            except ImportError:
                syslog(LOG_ERR, "Failed to load structure %s" % (structure))
                continue
            struct = getattr(mod, structure)
            self.structures.append(struct(self, self.datastore))
        self.generators = []
        for generator in generators:
            try:
                mod = getattr(__import__("Bcfg2.Server.Generators.%s" %
                                         (generator)).Server.Generators, generator)
            except ImportError:
                syslog(LOG_ERR, 'Failed to load generator %s' % (generator))
                continue
            gen = getattr(mod, generator)
            self.generators.append(gen(self, self.datastore))
        # we need to inventory and setup generators
        # Process generator requirements
        for gen in self.generators:
            for prq in gen.__requires__:
                if not self.pubspace.has_key(prq):
                    raise GeneratorError, (gen.name, prq)
            gen.CompleteSetup()

    def PublishValue(self, owner, key, value):
        if not self.pubspace.has_key(key):
            # This is a new entry
            self.pubspace[key] = PublishedValue(owner, key, value)
        else:
            # This is an old entry. Update can fai
            try:
                self.pubspace[key].Update(owner, value)
            except PublishError:
                syslog(LOG_ERR, "Publish conflict for %s. Owner %s, Modifier %s"%
                       (key, self.pubspace[key].owner, owner))

    def ReadValue(self, key):
        if self.pubspace.has_key(key):
            return self.pubspace[key].value
        raise KeyError, key

    def GetStructures(self, metadata):
        return reduce(lambda x, y:x+y,
                      [z.Construct(metadata) for z in self.structures])

    def BindStructure(self, structure, metadata):
        for entry in [x in structure.getchildren() if x.tag not in ['SymLink','Directory']]:
            try:
                self.Bind(entry, metadata)
            except KeyError, k:
                syslog(LOG_ERR, "Unable to locate %s"%k)

    def Bind(self, entry, metadata):
        g = [x for x in self.generators if
             x.__provides__.get(entry.tag, {}).has_key(entry.attrib['name'])]
        if len(g) == 1:
            return g[0].__provides__[entry.tag][entry.attrib['name']](entry, metadata)
        elif len(g) > 1:
            print "Data Integrity error for %s %s" % (entry.tag, entry.attrib['name'])
        else:
            for g in self.generators:
                if hasattr(g, "FindHandler"):
                    try:
                        return g.FindHandler(entry)(entry, metadata)
                    except:
                        print g, "failed"
            raise KeyError, (entry.tag, entry.attrib['name'])
                
    def RunCronTasks(self):
        g = [x for x in self.generators if x.__croninterval__]
        for generator in g:
            t = time()
            if ((t - self.cron.get(generator, 0)) > generator.__croninterval__):
                generator.Cron()
                self.cron[generator] = t

