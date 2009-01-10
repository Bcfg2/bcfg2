'''Bcfg2.Server.Core provides the runtime support for bcfg2 modules'''
__revision__ = '$Revision$'

from time import time

from Bcfg2.Server.Plugin import PluginInitError, PluginExecutionError
import Bcfg2.Server.FileMonitor

import logging, lxml.etree, os
import Bcfg2.Server.Plugins.Metadata

logger = logging.getLogger('Bcfg2.Core')

try:
    import psyco
    psyco.full()
except:
    pass

class CoreInitError(Exception):
    '''This error is raised when the core cannot be initialized'''
    pass

class Core(object):
    '''The Core object is the container for all Bcfg2 Server logic, and modules'''

    def __init__(self, repo, plugins, structures, generators, connectors,
                 password, svn, encoding, filemonitor='default'):
        object.__init__(self)
        self.datastore = repo
        if filemonitor not in Bcfg2.Server.FileMonitor.available:
            logger.error("File monitor driver %s not available; forcing to default" % filemonitor)
            filemonitor = 'default'
        try:
            self.fam = Bcfg2.Server.FileMonitor.available[filemonitor]()
        except IOError:
            raise CoreInitError, "failed to instantiate fam driver (used %s)" % \
                  filemonitor
        self.pubspace = {}
        self.generators = []
        self.structures = []
        self.connectors = []
        self.cron = {}
        self.plugins = {}
        self.revision = '-1'
        self.password = password
        self.svn = svn
        self.encoding = encoding
        try:
            if self.svn:
                self.read_svn_revision()
        except:
            self.svn = False

        [data.remove('') for data in [plugins, structures, generators]
         if '' in data]
        
        for plugin in structures + generators + plugins + connectors:
            if not plugin in self.plugins:
                self.init_plugins(plugin)    

        chk_plugins = self.plugins.values()
        while True:
            try:
                plugin = chk_plugins.pop()
                if isinstance(plugin, Bcfg2.Server.Plugin.Metadata):
                    self.metadata = plugin
                    break
            except:
                pass
            if not chk_plugins:
                self.init_plugins("Metadata")
                self.metadata = self.plugins["Metadata"]
                break

        chk_plugins = self.plugins.values()
        while True:
            try:
                plugin = chk_plugins.pop()
                if isinstance(plugin, Bcfg2.Server.Plugin.Statistics):
                    self.stats = plugin
                    break
            except:
                pass
            if not chk_plugins:
                self.init_plugins("Statistics")
                self.stats = self.plugins["Statistics"]
                break

        for plug_names, plug_tname, plug_type, collection in \
            [(structures, 'structure', Bcfg2.Server.Plugin.Structure,
              self.structures),
             (generators, 'generator', Bcfg2.Server.Plugin.Generator,
              self.generators),
             (connectors, 'connector', Bcfg2.Server.Plugin.Connector,
              self.connectors),
             ]:
            for plugin in plug_names:
                if plugin in self.plugins:
                    if not isinstance(self.plugins[plugin], plug_type):
                        logger.error("Plugin %s is not a %s plugin; unloading" \
                                 % (plugin, plug_tname))
                        del self.plugins[plugin]
                    else:
                        collection.append(self.plugins[plugin])
                else:
                    logger.error("Plugin %s not loaded. Not enabled as a %s" \
                                 % (plugin, plug_tname))
    
    def init_plugins(self, plugin):
        try:
            mod = getattr(__import__("Bcfg2.Server.Plugins.%s" %
                                (plugin)).Server.Plugins, plugin)
        except ImportError, e:
            logger.error("Failed to load plugin %s: %s" % (plugin, e))
            return
        plug = getattr(mod, plugin)
        if plug.experimental:
            logger.info("Loading experimental plugin %s" % (plugin))
            logger.info("NOTE: Interface subject to change")
        try:
            self.plugins[plugin] = plug(self, self.datastore)
        except PluginInitError:
            logger.error("Failed to instantiate plugin %s" % (plugin))
        except:
            logger.error("Unexpected instantiation failure for plugin %s" % 
                (plugin), exc_info=1)    
            

    def validate_data(self, metadata, data, base_cls):
        for plugin in self.plugins.values():
            if isinstance(plugin, base_cls):
                try:
                    if base_cls == Bcfg2.Server.Plugin.StructureValidator:
                        plugin.validate_structures(metadata, data)
                    elif base_cls == Bcfg2.Server.Plugin.GoalValidator:
                        plugin.validate_goals(metadata, data)
                except Bcfg2.Server.Plugin.ValidationError, err:
                    logger.error("Plugin %s structure validation failed: %s" \
                                 % (plugin.name, err.message))
                    raise
                except:
                    logger.error("Plugin %s: unexpected structure val failure" \
                                 % (plugin.name), exc_info=1)

    def GetStructures(self, metadata):
        '''Get all structures for client specified by metadata'''
        return reduce(lambda x, y:x+y,
                      [struct.BuildStructures(metadata) for struct \
                       in self.structures], [])

    def BindStructure(self, structure, metadata):
        '''Bind a complete structure'''
        for entry in structure.getchildren():
            if entry.tag.startswith("Bound"):
                entry.tag = entry.tag[5:]
                continue
            try:
                self.Bind(entry, metadata)
            except PluginExecutionError:
                logger.error("Failed to bind entry: %s %s" % \
                             (entry.tag, entry.get('name')))
            except:
                logger.error("Unexpected failure in BindStructure: %s %s" \
                             % (entry.tag, entry.get('name')), exc_info=1)

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
                 entry.get('name') in gen.Entries.get(entry.tag, {})]
        if len(glist) == 1:
            return glist[0].Entries[entry.tag][entry.get('name')](entry, metadata)
        elif len(glist) > 1:
            generators = ", ".join([gen.name for gen in glist])
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
            meta = self.build_metadata(client)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            logger.error("Metadata consistency error for client %s" % client)
            return lxml.etree.Element("error", type='metadata error')

        try:
            structures = self.GetStructures(meta)
        except:
            logger.error("error in GetStructures", exc_info=1)
            return lxml.etree.Element("error", type='structure error')

        self.validate_data(meta, structures,
                           Bcfg2.Server.Plugin.StructureValidator)

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
        self.validate_data(meta, config, Bcfg2.Server.Plugin.GoalValidator)
        logger.info("Generated config for %s in %s seconds" % \
                    (client, time() - start))
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
            data = os.popen("env LC_ALL=C svn info %s" \
                            % (self.datastore)).readlines()
            revline = [line.split(': ')[1].strip() for line in data \
                       if line[:9] == 'Revision:'][-1]
            self.revision = revline
        except IndexError:
            logger.error("Failed to read svn info; disabling svn support")
            logger.error('''Ran command "svn info %s"''' % (self.datastore))
            logger.error("Got output: %s" % data)
            self.svn = False

    def GetDecisions(self, metadata, mode):
        result = []
        for plugin in self.plugins.values():
            try:
                if isinstance(plugin, Bcfg2.Server.Plugin.Decision):
                    result += plugin.GetDecisions(metadata, mode)
            except:
                logger.error("Plugin: %s failed to generate decision list" \
                             % plugin.name, exc_info=1)
        return result

    def build_metadata(self, client_name):
        imd = self.metadata.get_initial_metadata(client_name)
        for conn in self.connectors:
            grps, data = conn.get_additional_metadata(imd)
            self.metadata.merge_additional_metadata(imd, conn.name, grps, data)
        return imd
            
