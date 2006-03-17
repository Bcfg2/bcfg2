'''Bcfg2.Server.Core provides the runtime support for bcfg2 modules'''
__revision__ = '$Revision$'

from time import time
from Bcfg2.Server.Plugin import PluginInitError, PluginExecutionError
from Bcfg2.Server.Statistics import Statistics

import logging, lxml.etree, os, stat, Bcfg2.Server.Metadata, ConfigParser

logger = logging.getLogger('Bcfg2.Core')

class CoreInitError(Exception):
    '''This error is raised when the core cannot be initialized'''
    pass

class FamFam(object):
    '''The fam object is a set of callbacks for file alteration events (FAM support)'''
    
    def __init__(self):
        object.__init__(self)
        self.fm = _fam.open()
        self.users = {}
        self.handles = {}

    def fileno(self):
        '''return fam file handle number'''
        return self.fm.fileno()

    def AddMonitor(self, path, obj):
        '''add a monitor to path, installing a callback to obj.HandleEvent'''
        mode = os.stat(path)[stat.ST_MODE]
        if stat.S_ISDIR(mode):
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
            try:
                self.users[reqid].HandleEvent(event)
            except:
                logger.error("handling event for file %s" % (event.filename), exc_info=1)

    def Service(self):
        '''Handle all fam work'''
        count = 0
        collapsed = 0
        rawevents = []
        start = time()
        now = time()
        while (time() - now) < 0.10:
            if self.fm.pending():
                while self.fm.pending():
                    count += 1
                    rawevents.append(self.fm.nextEvent())
                now = time()
        unique = []
        bookkeeping = []
        for event in rawevents:
            if event.filename.split('/')[-1] == '.svn':
                # ignore svn directories
                continue
            if event.code2str() != 'changed':
                # process all non-change events
                unique.append(event)
            else:
                if (event.filename, event.requestID) not in bookkeeping:
                    bookkeeping.append((event.filename, event.requestID))
                    unique.append(event)
                else:
                    collapsed += 1
        for event in unique:
            if self.users.has_key(event.requestID):
                try:
                    self.users[event.requestID].HandleEvent(event)
                except:
                    logger.error("handling event for file %s" % (event.filename), exc_info=1)
        end = time()
        logger.info("Processed %s fam events in %03.03f seconds. %s coalesced" %
                    (count, (end - start), collapsed))
        return count

class GaminEvent(object):
    '''This class provides an event analogous to python-fam events based on gamin sources'''
    def __init__(self, request_id, filename, code):
        action_map = {GAMCreated: 'created', GAMExists: 'exists', GAMChanged: 'changed',
                      GAMDeleted: 'deleted', GAMEndExist: 'endExist'}
        self.requestID = request_id
        self.filename = filename
        if action_map.has_key(code):
            self.action = action_map[code]

    def code2str(self):
        '''return static code for event'''
        return self.action

class GaminFam(object):
    '''The fam object is a set of callbacks for file alteration events (Gamin support)'''
    def __init__(self):
        object.__init__(self)
        self.mon = WatchMonitor()
        self.handles = {}
        self.counter = 0
        self.events = []

    def fileno(self):
        '''return fam file handle number'''
        return self.mon.get_fd()

    def queue(self, path, action, request_id):
        '''queue up the event for later handling'''
        self.events.append(GaminEvent(request_id, path, action))

    def AddMonitor(self, path, obj):
        '''add a monitor to path, installing a callback to obj.HandleEvent'''
        handle = self.counter
        self.counter += 1
        mode = os.stat(path)[stat.ST_MODE]
        if stat.S_ISDIR(mode):
            self.mon.watch_directory(path, self.queue, handle)
            #print "adding callback for directory %s to %s, handle :%s:" % ( path, obj, handle.requestID())
        else:
            self.mon.watch_file(path, self.queue, handle)
        self.handles[handle] = obj
        return handle

    def Service(self):
        '''Handle all gamin work'''
        count = 0
        collapsed = 0
        start = time()
        now = time()
        while (time() - now) < 0.10:
            if self.mon.event_pending():
                while self.mon.event_pending():
                    count += 1
                    self.mon.handle_one_event()
                now = time()
        unique = []
        bookkeeping = []
        for event in self.events:
            if event.filename.split('/')[-1] == '.svn':
                # skip svn directories
                continue
            if event.code2str() != 'changed':
                # process all non-change events
                unique.append(event)
            else:
                if (event.filename, event.requestID) not in bookkeeping:
                    bookkeeping.append((event.filename, event.requestID))
                    unique.append(event)
                else:
                    collapsed += 1
        self.events = []
        for event in unique:
            if self.handles.has_key(event.requestID):
                try:
                    self.handles[event.requestID].HandleEvent(event)
                except:
                    logger.error("error in handling of gamin event for %s" % (event.filename), exc_info=1)
            else:
                logger.info("Got event for unexpected id %s, file %s" %
                            (event.requestID, event.filename))
        end = time()
        logger.info("Processed %s gamin events in %03.03f seconds. %s collapsed" %
                    (count, (end - start), collapsed))
        return count
        
try:
    from gamin import WatchMonitor, GAMCreated, GAMExists, GAMEndExist, GAMChanged, GAMDeleted
    monitor = GaminFam
except ImportError:
    # fall back to _fam
    try:
        import _fam
        monitor = FamFam
    except ImportError:
        print "Couldn't locate Fam module, exiting"
        raise SystemExit, 1

class Core(object):
    '''The Core object is the container for all Bcfg2 Server logic, and modules'''
    def __init__(self, setup, configfile):
        object.__init__(self)
        cfile = ConfigParser.ConfigParser()
        cfile.read([configfile])
        self.datastore = cfile.get('server','repository')
        try:
            self.fam = monitor()
        except IOError:
            raise CoreInitError, "failed to connect to fam"
        self.pubspace = {}
        self.generators = []
        self.structures = []
        self.cron = {}
        self.setup = setup
        self.plugins = {}
        try:
            self.svn = cfile.get('server', 'svn') == 'yes'
        except:
            self.svn = False
        self.revision = '-1'
        
        mpath = cfile.get('server','repository')
        try:
            self.metadata = Bcfg2.Server.Metadata.Metadata(self.fam, mpath)
        except OSError:
            raise CoreInitError, "metadata path incorrect"
        
        self.stats = Statistics("%s/etc/statistics.xml" % (mpath))

        structures = cfile.get('server', 'structures').split(',')
        generators = cfile.get('server', 'generators').split(',')

        for plugin in structures + generators:
            if not self.plugins.has_key(plugin):
                try:
                    mod = getattr(__import__("Bcfg2.Server.Plugins.%s" %
                                             (plugin)).Server.Plugins, plugin)
                except ImportError:
                    logger.error("Failed to load plugin %s" % (plugin))
                    continue
                struct = getattr(mod, plugin)
                try:
                    self.plugins[plugin] = struct(self, self.datastore)
                except PluginInitError:
                    logger.error("Failed to instantiate plugin %s" % (plugin))
                except:
                    logger.error("Unexpected initiantiation failure for plugin %s" % (plugin), exc_info=1)

        for plugin in structures:
            if self.plugins.has_key(plugin):
                self.structures.append(self.plugins[plugin])
            else:
                logger.error("Plugin %s not loaded. Not enabled as a Structure" % (plugin))
        for plugin in generators:
            if self.plugins.has_key(plugin):
                self.generators.append(self.plugins[plugin])
            else:
                logger.error("Plugin %s not loaded. Not enabled as a Generator" % (plugin))
                    
    def GetStructures(self, metadata):
        '''Get all structures for client specified by metadata'''
        return reduce(lambda x, y:x+y,
                      [struct.BuildStructures(metadata) for struct in self.structures])

    def BindStructure(self, structure, metadata):
        '''Bind a complete structure'''
        for entry in [child for child in structure.getchildren() if child.tag not in ['SymLink', 'Directory', 'Permissions', 'PostInstall']]:
            try:
                self.Bind(entry, metadata)
            except PluginExecutionError:
                logger.error("Failed to bind entry: %s %s" %  (entry.tag, entry.get('name')))
            except:
                logger.error("Unexpected failure in BindStructure: %s %s" % (entry.tag, entry.get('name')),
                             exc_info=1)

    def Bind(self, entry, metadata):
        '''Bind an entry using the appropriate generator'''
        glist = [gen for gen in self.generators if
                 gen.Entries.get(entry.tag, {}).has_key(entry.get('name'))]
        if len(glist) == 1:
            return glist[0].Entries[entry.tag][entry.get('name')](entry, metadata)
        elif len(glist) > 1:
            generators = ", ".join([gen.__name__ for gen in glist])
            logger.error("%s %s served by multiple generators: %s" % (entry.tag,
                                                                           entry.get('name'), generators))
        raise PluginExecutionError, (entry.tag, entry.get('name'))
                
    def BuildConfiguration(self, client):
        '''Build Configuration for client'''
        start = time()
        config = lxml.etree.Element("Configuration", version='2.0', revision=self.revision)
        try:
            meta = self.metadata.get_metadata(client)
        except Bcfg2.Server.Metadata.MetadataConsistencyError:
            logger.error("Metadata consistency error for client %s" % client)
            return lxml.etree.Element("error", type='metadata error')

        config.set('toolset', meta.toolset)
        try:
            structures = self.GetStructures(meta)
        except:
            logger.error("error in GetStructures", exc_info=1)
            return lxml.etree.Element("error", type='structure error')
        
        for astruct in structures:
            try:
                self.BindStructure(astruct, meta)
                config.append(astruct)
            except:
                logger.error("error in BindStructure", exc_info=1)
        logger.info("Generated config for %s in %s seconds"%(client, time() - start))
        return config

    def Service(self):
        '''Perform periodic update tasks'''
        while self.fam.fm.pending:
            try:
                if self.fam.HandleEvent() and self.svn:
                    self.read_svn_revision()
            except:
                logger.error("error in FamEvent", exc_info=1)
        try:
            self.stats.WriteBack()
        except:
            logger.error("error in Statistics", exc_info=1)
            
    def read_svn_revision(self):
        '''Read svn revision information for the bcfg2 repository'''
        revline = [line.split(': ')[1].strip() for line in os.popen("svn info %s" % (self.datastore)).readlines() if
                   line[:9] == 'Revision:'][-1]
        self.revision = revline
