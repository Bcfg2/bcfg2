'''Bcfg2.Server.Core provides the runtime support for bcfg2 modules'''
__revision__ = '$Revision$'

from time import time
from Bcfg2.Server.Plugin import PluginInitError, PluginExecutionError
from Bcfg2.Server.Statistics import Statistics
from Bcfg2.Settings import settings

import logging, lxml.etree, os, stat, ConfigParser
import Bcfg2.Server.Plugins.Metadata

logger = logging.getLogger('Bcfg2.Core')

def ShouldIgnore(event):
    '''Test if the event should be suppresed'''
    if event.filename.split('/')[-1] == '.svn':
        return True
    if event.filename.endswith('~') or event.filename.endswith('.tmp') \
    or event.filename.endswith('.tmp'):
        logger.error("Suppressing event for file %s" % (event.filename))
        return True
    return False

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
            if ShouldIgnore(event):
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
                      GAMDeleted: 'deleted', GAMEndExist: 'endExist', GAMMoved: 'moved'}
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
            if ShouldIgnore(event):
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
    from gamin import WatchMonitor, GAMCreated, GAMExists, GAMEndExist, GAMChanged, GAMDeleted, GAMMoved
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
    def __init__(self):
        object.__init__(self)
        self.datastore = settings.SERVER_REPOSITORY
        try:
            self.fam = monitor()
        except IOError:
            raise CoreInitError, "failed to connect to fam"
        self.pubspace = {}
        self.generators = []
        self.structures = []
        self.cron = {}
        self.plugins = {}
        self.revision = '-1'

        try:
            if settings.SERVER_SVN:
                self.read_svn_revision()
        except:
          settings.SERVER_SVN = False

        self.svn = settings.SERVER_SVN

        mpath = settings.SERVER_REPOSITORY
        self.stats = Statistics("%s/etc/statistics.xml" % (mpath))

        structures = settings.SERVER_STRUCTURES
        generators = settings.SERVER_GENERATORS
        [data.remove('') for data in [structures, generators] if '' in data]

        for plugin in structures + generators + ['Metadata']:
            if not self.plugins.has_key(plugin):
                try:
                    mod = getattr(__import__("Bcfg2.Server.Plugins.%s" %
                                             (plugin)).Server.Plugins, plugin)
                except ImportError, e:
                    logger.error("Failed to load plugin %s: %s" % (plugin, e))
                    continue
                struct = getattr(mod, plugin)
                try:
                    self.plugins[plugin] = struct(self, self.datastore)
                except PluginInitError:
                    logger.error("Failed to instantiate plugin %s" % (plugin))
                except:
                    logger.error("Unexpected instantiation failure for plugin %s" % (plugin), exc_info=1)

        self.metadata = self.plugins['Metadata']
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
                      [struct.BuildStructures(metadata) for struct in self.structures], [])

    def BindStructure(self, structure, metadata):
        '''Bind a complete structure'''
        for entry in [child for child in structure.getchildren() if child.tag not in ['PostInstall']]:
            try:
                self.Bind(entry, metadata)
            except PluginExecutionError:
                logger.error("Failed to bind entry: %s %s" %  (entry.tag, entry.get('name')))
            except:
                logger.error("Unexpected failure in BindStructure: %s %s" % (entry.tag, entry.get('name')),
                             exc_info=1)

    def Bind(self, entry, metadata):
        '''Bind an entry using the appropriate generator'''
        if 'altsrc' in entry.attrib:
            oldname = entry.get('name')
            entry.set('name', entry.get('altsrc'))
            entry.set('realname', oldname)
            del entry.attrib['altsrc']
            try:
                ret = self.Bind(entry, metadata)
                entry.set('name', oldname)
                del entry.attrib['realname']
                return ret
            except:
                entry.set('name', oldname)
                logger.error("Failed binding entry %s:%s with altsrc %s" \
                             % (entry.tag, entry.get('name'),
                                entry.get('altsrc')))
                logger.error("Falling back to %s:%s" % (entry.tag,
                                                        entry.get('name')))

        glist = [gen for gen in self.generators if
                 gen.Entries.get(entry.tag, {}).has_key(entry.get('name'))]
        if len(glist) == 1:
            return glist[0].Entries[entry.tag][entry.get('name')](entry, metadata)
        elif len(glist) > 1:
            generators = ", ".join([gen.__name__ for gen in glist])
            logger.error("%s %s served by multiple generators: %s" % \
                         (entry.tag, entry.get('name'), generators))
        g2list = [gen for gen in self.generators if gen.HandlesEntry(entry)]
        if len(g2list) == 1:
            return g2list[0].HandleEntry(entry, metadata)
        raise PluginExecutionError, (entry.tag, entry.get('name'))
                
    def BuildConfiguration(self, client):
        '''Build Configuration for client'''
        start = time()
        config = lxml.etree.Element("Configuration", version='2.0', revision=self.revision)
        try:
            meta = self.metadata.get_metadata(client)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            logger.error("Metadata consistency error for client %s" % client)
            return lxml.etree.Element("error", type='metadata error')

        try:
            structures = self.GetStructures(meta)
        except:
            logger.error("error in GetStructures", exc_info=1)
            return lxml.etree.Element("error", type='structure error')

        if self.plugins.has_key('Deps'):
            # do prereq processing
            prereqs = self.plugins['Deps'].GeneratePrereqs(structures, meta)
            structures.append(prereqs)

        # Perform altsrc consistency checking
        esrcs = {}
        for struct in structures:
            for entry in struct:
                key = (entry.tag, entry.get('name'))
                if key in esrcs:
                    if esrcs[key] != entry.get('altsrc'):
                        logger.error("Found inconsistent altsrc mapping for entry %s:%s" % key)
                else:
                    esrcs[key] = entry.get('altsrc', None)
        del esrcs
        
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
        count = self.fam.Service()
        if count and self.svn:
            self.read_svn_revision()
        try:
            self.stats.WriteBack()
        except:
            logger.error("error in Statistics", exc_info=1)
            
    def read_svn_revision(self):
        '''Read svn revision information for the bcfg2 repository'''
        try:
            data = os.popen("svn info %s" % (self.datastore)).readlines()
            revline = [line.split(': ')[1].strip() for line in data if line[:9] == 'Revision:'][-1]
            self.revision = revline
        except IndexError:
            logger.error("Failed to read svn info; disabling svn support")
            logger.error('''Ran command "svn info %s"''' % (self.datastore))
            logger.error("Got output: %s" % data)
            self.svn = False
