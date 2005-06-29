'''Bcfg2.Server.Core provides the runtime support for bcfg2 modules'''
__revision__ = '$Revision$'

from os import stat
from stat import ST_MODE, S_ISDIR
from sys import exc_info
from syslog import syslog, LOG_ERR, LOG_INFO
from traceback import extract_tb
from time import time
from ConfigParser import ConfigParser
from elementtree.ElementTree import Element
import _fam

from Bcfg2.Server.Generator import GeneratorError, GeneratorInitError
from Bcfg2.Server.Metadata import MetadataStore, MetadataConsistencyError
from Bcfg2.Server.Statistics import Statistics

class PublishError(Exception):
    '''This error is raised upon publication failures'''
    pass

class CoreInitError(Exception):
    '''This error is raised when the core cannot be initialized'''
    pass

class Fam(object):
    '''The fam object is a set of callbacks for file alteration events'''
    
    def __init__(self):
        object.__init__(self)
        self.fm = _fam.open()
        self.users = {}
        self.handles = {}

    def fileno(self):
        '''return fam file handle number'''
        return self.fm.fileno()

    def AddMonitor(self, path, obj=None):
        '''add a monitor to path, installing a callback to obj.HandleEvent'''
        mode = stat(path)[ST_MODE]
        if S_ISDIR(mode):
            handle = self.fm.monitorDirectory(path, None)
            #print "adding callback for directory %s to %s, handle :%s:" % ( path, obj, handle.requestID())
        else:
            handle = self.fm.monitorFile(path, None)
        self.handles[handle.requestID()] = handle
        if obj != None:
            self.users[handle.requestID()] = obj
        return handle.requestID()

    def HandleEvent(self):
        '''Route a fam event to the proper callback'''
        event = self.fm.nextEvent()
        reqid = event.requestID
        if self.users.has_key(reqid):
            #print "dispatching event %s %s to obj %s handle :%s:" % (event.code2str(), event.filename, self.users[reqid], event.requestID)
            self.users[reqid].HandleEvent(event)

class PublishedValue(object):
    '''This is for data shared between generators'''
    def __init__(self, owner, key, value):
        object.__init__(self)
        self.owner = owner
        self.key = key
        self.value = value

    def Update(self, owner, value):
        '''Update the value after an ownership check succeeds'''
        if owner != self.owner:
            raise PublishError, (self.key, owner)
        self.value = value

class Core(object):
    '''The Core object is the container for all Bcfg2 Server logic, and modules'''
    def __init__(self, setup, configfile):
        object.__init__(self)
        cfile = ConfigParser()
        cfile.read([configfile])
        self.datastore = cfile.get('server','repository')
        try:
            self.fam = Fam()
        except IOError:
            raise CoreInitError, "failed to connect to fam"
        self.pubspace = {}
        self.structures = []
        self.generators = []
        self.cron = {}
        self.setup = setup
        
        mpath = cfile.get('server','metadata')
        try:
            self.metadata = MetadataStore("%s/metadata.xml" % mpath, self.fam)
        except OSError:
            raise CoreInitError, "metadata path incorrect"
        
        self.stats = Statistics("%s/statistics.xml" % (mpath))
        
        for structure in cfile.get('server', 'structures').split(','):
            try:
                mod = getattr(__import__("Bcfg2.Server.Structures.%s" %
                                         (structure)).Server.Structures, structure)
            except ImportError:
                syslog(LOG_ERR, "Failed to load structure %s" % (structure))
                continue
            struct = getattr(mod, structure)
            self.structures.append(struct(self, self.datastore))

        for generator in cfile.get('server', 'generators').split(','):
            try:
                mod = getattr(__import__("Bcfg2.Server.Generators.%s" %
                                         (generator)).Server.Generators, generator)
            except ImportError:
                syslog(LOG_ERR, 'Failed to load generator %s' % (generator))
                continue
            gen = getattr(mod, generator)
            try:
                self.generators.append(gen(self, self.datastore))
            except GeneratorInitError:
                syslog(LOG_ERR, "Failed to instantiate generator %s" % gen.__name__)
            except:
                print "Unexpected initiantiation failure for generator %s" % gen.__name__
                syslog(LOG_ERR, "Unexpected initiantiation failure for generator %s" % gen.__name__)
                (trace, val, trb)=exc_info()
                for line in extract_tb(trb):
                    syslog(LOG_ERR, '  File "%s", line %i, in %s\n    %s\n'%line)
                syslog(LOG_ERR, "%s: %s\n"%(trace, val))
                del trace, val, trb
        # we need to inventory and setup generators
        # Process generator requirements
        for gen in self.generators:
            for prq in gen.__requires__:
                if not self.pubspace.has_key(prq):
                    raise GeneratorError, (gen.name, prq)
            gen.CompleteSetup()

    def PublishValue(self, owner, key, value):
        '''Publish a shared generator value'''
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
        '''Read a value published by another generator'''
        if self.pubspace.has_key(key):
            return self.pubspace[key].value
        raise KeyError, key

    def GetStructures(self, metadata):
        '''Get all structures for client specified by metadata'''
        return reduce(lambda x, y:x+y,
                      [struct.Construct(metadata) for struct in self.structures])

    def BindStructure(self, structure, metadata):
        '''Bind a complete structure'''
        for entry in [child for child in structure.getchildren() if child.tag not in ['SymLink', 'Directory', 'Permission']]:
            try:
                self.Bind(entry, metadata)
            except GeneratorError:
                syslog(LOG_ERR, "Failed to bind entry: %s %s" %  (entry.tag, entry.get('name')))

    def Bind(self, entry, metadata):
        '''Bind an entry using the appropriate generator'''
        glist = [gen for gen in self.generators if
                 gen.__provides__.get(entry.tag, {}).has_key(entry.get('name'))]
        if len(glist) == 1:
            return glist[0].__provides__[entry.tag][entry.get('name')](entry, metadata)
        elif len(glist) > 1:
            syslog(LOG_ERR, "%s %s served by multiple generators" % (entry.tag, entry.get('name')))
        else:
            for gen in self.generators:
                if hasattr(gen, "FindHandler"):
                    return gen.FindHandler(entry)(entry, metadata)
            raise GeneratorError, (entry.tag, entry.get('name'))
                
    def RunCronTasks(self):
        '''Run periodic tasks for generators'''
        generators = [gen for gen in self.generators if gen.__croninterval__]
        for generator in generators:
            current = time()
            if ((current - self.cron.get(generator, 0)) > generator.__croninterval__):
                generator.Cron()
                self.cron[generator] = current

    def BuildConfiguration(self, client):
        '''Build Configuration for client'''
        start = time()
        config = Element("Configuration", version='2.0')
        try:
            meta = self.metadata.FetchMetadata(client)
        except MetadataConsistencyError:
            syslog(LOG_ERR, "Metadata consistency error for client %s" % client)
            return Element("error", type='metadata error')

        config.set('toolset', meta.toolset)
        try:
            structures = self.GetStructures(meta)
        except:
            self.LogFailure("GetStructures")
            return Element("error", type='structure error')
        
        for astruct in structures:
            try:
                self.BindStructure(astruct, meta)
                config.append(astruct)
            except:
                self.LogFailure("BindStructure")
        syslog(LOG_INFO, "Generated config for %s in %s seconds"%(client, time() - start))
        return config

    def LogFailure(self, failure):
        '''Log Failures in unexpected cases'''
        (trace, val, trb) = exc_info()
        syslog(LOG_ERR, "Unexpected failure in %s" % (failure))
        for line in extract_tb(trb):
            syslog(LOG_ERR, '  File "%s", line %i, in %s\n    %s\n' % line)
        syslog(LOG_ERR, "%s: %s\n"%(trace, val))
        del trace, val, trb
