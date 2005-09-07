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
from Bcfg2.Server.Plugin import PluginInitError
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
        self.generators = []
        self.structures = []
        self.cron = {}
        self.setup = setup
        self.plugins = {}
        
        mpath = cfile.get('server','metadata')
        try:
            self.metadata = MetadataStore("%s/metadata.xml" % mpath, self.fam)
        except OSError:
            raise CoreInitError, "metadata path incorrect"
        
        self.stats = Statistics("%s/statistics.xml" % (mpath))

        structures = cfile.get('server', 'structures').split(',')
        generators = cfile.get('server', 'generators').split(',')

        for plugin in structures + generators:
            if not self.plugins.has_key(plugin):
                try:
                    mod = getattr(__import__("Bcfg2.Server.Plugins.%s" %
                                             (structure)).Server.Plugins, structure)
                except ImportError:
                    syslog(LOG_ERR, "Failed to load plugin %s" % (plugin))
                    continue
                struct = getattr(mod, plugin)
                try:
                    self.plugins[structure] = struct(self, self.datastore)
                except PluginInitError:
                    syslog(LOG_ERR, "Failed to instantiate plugin %s" % (plugin))
                except:
                    syslog(LOG_ERR, "Unexpected initiantiation failure for plugin %s" % (plugin))
                    (trace, val, trb)=exc_info()
                    for line in extract_tb(trb):
                        syslog(LOG_ERR, '  File "%s", line %i, in %s\n    %s\n'%line)
                        syslog(LOG_ERR, "%s: %s\n"%(trace, val))
                        del trace, val, trb

        for plugin in structures:
            if self.plugins.has_key(plugin):
                self.structures.append(self.plugins[plugin])
            else:
                syslog(LOG_ERR, "Plugin %s not loaded. Not enabled as a Structure" % (plugin))
        for plugin in generators:
            if self.plugins.has_key(plugin):
                self.generators.append(self.plugins[plugin])
            else:
                syslog(LOG_ERR, "Plugin %s not loaded. Not enabled as a Generator" % (plugin))
                    
    def GetStructures(self, metadata):
        '''Get all structures for client specified by metadata'''
        return reduce(lambda x, y:x+y,
                      [struct.BuildStructures(metadata) for struct in self.structures])

    def BindStructure(self, structure, metadata):
        '''Bind a complete structure'''
        for entry in [child for child in structure.getchildren() if child.tag not in ['SymLink', 'Directory', 'Permissions', 'PostInstall']]:
            try:
                self.Bind(entry, metadata)
            except GeneratorError:
                syslog(LOG_ERR, "Failed to bind entry: %s %s" %  (entry.tag, entry.get('name')))

    def Bind(self, entry, metadata):
        '''Bind an entry using the appropriate generator'''
        glist = [gen for gen in self.generators if
                 gen.Entries.get(entry.tag, {}).has_key(entry.get('name'))]
        if len(glist) == 1:
            return glist[0].Entries[entry.tag][entry.get('name')](entry, metadata)
        elif len(glist) > 1:
            syslog(LOG_ERR, "%s %s served by multiple generators" % (entry.tag, entry.get('name')))
        else:
            for gen in self.generators:
                if hasattr(gen, "FindHandler"):
                    return gen.FindHandler(entry)(entry, metadata)
            raise GeneratorError, (entry.tag, entry.get('name'))
                
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

    def Service(self):
        '''Perform periodic update tasks'''
        while self.fam.fm.pending:
            try:
                self.fam.HandleEvent()
            except:
                self.LogFailure("FamEvent")
        try:
            self.core.stats.WriteBack()
        except:
            self.LogFailure("Statistics")
            
