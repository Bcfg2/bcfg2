"""Bcfg2.Server.Core provides the runtime support for Bcfg2 modules."""
__revision__ = '$Revision$'

import atexit
import logging
import select
import sys
import threading
import time
try:
    import lxml.etree
except ImportError:
    print("Failed to import lxml dependency. Shutting down server.")
    raise SystemExit(1)

from Bcfg2.Component import Component, exposed
from Bcfg2.Server.Plugin import PluginInitError, PluginExecutionError
import Bcfg2.Server.FileMonitor
import Bcfg2.Server.Plugins.Metadata
# Compatibility imports
from Bcfg2.Bcfg2Py3k import xmlrpclib
if sys.hexversion >= 0x03000000:
    from functools import reduce

logger = logging.getLogger('Bcfg2.Server.Core')


def critical_error(operation):
    """Log and err, traceback and return an xmlrpc fault to client."""
    logger.error(operation, exc_info=1)
    raise xmlrpclib.Fault(7, "Critical unexpected failure: %s" % (operation))

try:
    import psyco
    psyco.full()
except:
    pass


class CoreInitError(Exception):
    """This error is raised when the core cannot be initialized."""
    pass


class Core(Component):
    """The Core object is the container for all
    Bcfg2 Server logic and modules.
    """
    name = 'bcfg2-server'
    implementation = 'bcfg2-server'

    def __init__(self, repo, plugins, password, encoding,
                 cfile='/etc/bcfg2.conf', ca=None,
                 filemonitor='default', start_fam_thread=False):
        Component.__init__(self)
        self.datastore = repo
        if filemonitor not in Bcfg2.Server.FileMonitor.available:
            logger.error("File monitor driver %s not available; "
                         "forcing to default" % filemonitor)
            filemonitor = 'default'
        try:
            self.fam = Bcfg2.Server.FileMonitor.available[filemonitor]()
        except IOError:
            logger.error("Failed to instantiate fam driver %s" % filemonitor,
                         exc_info=1)
            raise CoreInitError("failed to instantiate fam driver (used %s)" % \
                                filemonitor)
        self.pubspace = {}
        self.cfile = cfile
        self.cron = {}
        self.plugins = {}
        self.plugin_blacklist = {}
        self.revision = '-1'
        self.password = password
        self.encoding = encoding
        atexit.register(self.shutdown)
        # Create an event to signal worker threads to shutdown
        self.terminate = threading.Event()

        if '' in plugins:
            plugins.remove('')

        for plugin in plugins:
            if not plugin in self.plugins:
                self.init_plugins(plugin)
        # Remove blacklisted plugins
        for p, bl in list(self.plugin_blacklist.items()):
            if len(bl) > 0:
                logger.error("The following plugins conflict with %s;"
                             "Unloading %s" % (p, bl))
            for plug in bl:
                del self.plugins[plug]
        # This section logs the experimental plugins
        expl = [plug for (name, plug) in list(self.plugins.items())
                if plug.experimental]
        if expl:
            logger.info("Loading experimental plugin(s): %s" % \
                        (" ".join([x.name for x in expl])))
            logger.info("NOTE: Interfaces subject to change")
        # This section logs the deprecated plugins
        depr = [plug for (name, plug) in list(self.plugins.items())
                if plug.deprecated]
        if depr:
            logger.info("Loading deprecated plugin(s): %s" % \
                        (" ".join([x.name for x in depr])))

        mlist = self.plugins_by_type(Bcfg2.Server.Plugin.Metadata)
        if len(mlist) == 1:
            self.metadata = mlist[0]
        else:
            logger.error("No Metadata Plugin loaded; failed to instantiate Core")
            raise CoreInitError("No Metadata Plugin")
        self.statistics = self.plugins_by_type(Bcfg2.Server.Plugin.Statistics)
        self.pull_sources = self.plugins_by_type(Bcfg2.Server.Plugin.PullSource)
        self.generators = self.plugins_by_type(Bcfg2.Server.Plugin.Generator)
        self.structures = self.plugins_by_type(Bcfg2.Server.Plugin.Structure)
        self.connectors = self.plugins_by_type(Bcfg2.Server.Plugin.Connector)
        self.ca = ca
        self.fam_thread = threading.Thread(target=self._file_monitor_thread)
        if start_fam_thread:
            self.fam_thread.start()

    def plugins_by_type(self, base_cls):
        """Return a list of loaded plugins that match the passed type.

        The returned list is sorted in ascending order by the Plugins'
        sort_order value. The sort_order defaults to 500 in Plugin.py,
        but can be overridden by individual plugins. Plugins with the
        same numerical sort_order value are sorted in alphabetical
        order by their name.
        """
        return sorted([plugin for plugin in self.plugins.values()
                       if isinstance(plugin, base_cls)],
                      key=lambda p: (p.sort_order, p.name))

    def _file_monitor_thread(self):
        """The thread for monitor the files."""
        famfd = self.fam.fileno()
        terminate = self.terminate
        while not terminate.isSet():
            try:
                if famfd:
                    select.select([famfd], [], [], 2)
                else:
                    if not self.fam.pending():
                        terminate.wait(15)
                self.fam.handle_event_set(self.lock)
            except:
                continue
            # VCS plugin periodic updates
            for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.Version):
                self.revision = plugin.get_revision()

    def init_plugins(self, plugin):
        """Handling for the plugins."""
        try:
            mod = getattr(__import__("Bcfg2.Server.Plugins.%s" %
                                (plugin)).Server.Plugins, plugin)
        except ImportError:
            try:
                mod = __import__(plugin)
            except:
                logger.error("Failed to load plugin %s" % (plugin))
                return
        plug = getattr(mod, plugin)
        # Blacklist conflicting plugins
        cplugs = [conflict for conflict in plug.conflicts
                  if conflict in self.plugins]
        self.plugin_blacklist[plug.name] = cplugs
        try:
            self.plugins[plugin] = plug(self, self.datastore)
        except PluginInitError:
            logger.error("Failed to instantiate plugin %s" % (plugin))
        except:
            logger.error("Unexpected instantiation failure for plugin %s" %
                (plugin), exc_info=1)

    def shutdown(self):
        """Shutting down the plugins."""
        if not self.terminate.isSet():
            self.terminate.set()
            for plugin in list(self.plugins.values()):
                plugin.shutdown()

    def validate_structures(self, metadata, data):
        """Checks the data structure."""
        for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.StructureValidator):
            try:
                plugin.validate_structures(metadata, data)
            except Bcfg2.Server.Plugin.ValidationError:
                err = sys.exc_info()[1]
                logger.error("Plugin %s structure validation failed: %s" \
                             % (plugin.name, err.message))
                raise
            except:
                logger.error("Plugin %s: unexpected structure validation failure" \
                             % (plugin.name), exc_info=1)

    def validate_goals(self, metadata, data):
        """Checks that the config matches the goals enforced by the plugins."""
        for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.GoalValidator):
            try:
                plugin.validate_goals(metadata, data)
            except Bcfg2.Server.Plugin.ValidationError:
                err = sys.exc_info()[1]
                logger.error("Plugin %s goal validation failed: %s" \
                             % (plugin.name, err.message))
                raise
            except:
                logger.error("Plugin %s: unexpected goal validation failure" \
                             % (plugin.name), exc_info=1)

    def GetStructures(self, metadata):
        """Get all structures for client specified by metadata."""
        structures = reduce(lambda x, y: x + y,
                            [struct.BuildStructures(metadata) for struct \
                             in self.structures], [])
        sbundles = [b.get('name') for b in structures if b.tag == 'Bundle']
        missing = [b for b in metadata.bundles if b not in sbundles]
        if missing:
            logger.error("Client %s configuration missing bundles: %s" \
                         % (metadata.hostname, ':'.join(missing)))
        return structures

    def BindStructure(self, structure, metadata):
        """Bind a complete structure."""
        for entry in structure.getchildren():
            if entry.tag.startswith("Bound"):
                entry.tag = entry.tag[5:]
                continue
            try:
                self.Bind(entry, metadata)
            except PluginExecutionError:
                if 'failure' not in entry.attrib:
                    entry.set('failure', 'bind error')
                logger.error("Failed to bind entry: %s %s" % \
                             (entry.tag, entry.get('name')))
            except:
                logger.error("Unexpected failure in BindStructure: %s %s" \
                             % (entry.tag, entry.get('name')), exc_info=1)

    def Bind(self, entry, metadata):
        """Bind an entry using the appropriate generator."""
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
            return glist[0].Entries[entry.tag][entry.get('name')](entry,
                                                                  metadata)
        elif len(glist) > 1:
            generators = ", ".join([gen.name for gen in glist])
            logger.error("%s %s served by multiple generators: %s" % \
                         (entry.tag, entry.get('name'), generators))
        g2list = [gen for gen in self.generators if
                  gen.HandlesEntry(entry, metadata)]
        if len(g2list) == 1:
            return g2list[0].HandleEntry(entry, metadata)
        entry.set('failure', 'no matching generator')
        raise PluginExecutionError(entry.tag, entry.get('name'))

    def BuildConfiguration(self, client):
        """Build configuration for clients."""
        start = time.time()
        config = lxml.etree.Element("Configuration", version='2.0', \
                                    revision=self.revision)
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

        self.validate_structures(meta, structures)

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
        self.validate_goals(meta, config)
        logger.info("Generated config for %s in %.03f seconds" % \
                    (client, time.time() - start))
        return config

    def GetDecisions(self, metadata, mode):
        """Get data for the decision list."""
        result = []
        for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.Decision):
            try:
                result += plugin.GetDecisions(metadata, mode)
            except:
                logger.error("Plugin: %s failed to generate decision list" \
                             % plugin.name, exc_info=1)
        return result

    def build_metadata(self, client_name):
        """Build the metadata structure."""
        if not hasattr(self, 'metadata'):
            # some threads start before metadata is even loaded
            raise Bcfg2.Server.Plugins.Metadata.MetadataRuntimeError
        imd = self.metadata.get_initial_metadata(client_name)
        for conn in self.connectors:
            grps = conn.get_additional_groups(imd)
            self.metadata.merge_additional_groups(imd, grps)
        for conn in self.connectors:
            data = conn.get_additional_data(imd)
            self.metadata.merge_additional_data(imd, conn.name, data)
        imd.query.by_name = self.build_metadata
        return imd

    def process_statistics(self, client_name, statistics):
        """Proceed statistics for client."""
        meta = self.build_metadata(client_name)
        state = statistics.find(".//Statistics")
        if state.get('version') >= '2.0':
            for plugin in self.statistics:
                try:
                    plugin.process_statistics(meta, statistics)
                except:
                    logger.error("Plugin %s failed to process stats from %s" \
                                 % (plugin.name, meta.hostname),
                                 exc_info=1)

        logger.info("Client %s reported state %s" % (client_name,
                                                     state.get('state')))
    # XMLRPC handlers start here

    @exposed
    def GetProbes(self, address):
        """Fetch probes for a particular client."""
        resp = lxml.etree.Element('probes')
        try:
            name = self.metadata.resolve_client(address, cleanup_cache=True)
            meta = self.build_metadata(name)

            for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.Probing):
                for probe in plugin.GetProbes(meta):
                    resp.append(probe)
            return lxml.etree.tostring(resp, encoding='UTF-8',
                                       xml_declaration=True)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            warning = 'Client metadata resolution error for %s; check server log' % address[0]
            self.logger.warning(warning)
            raise xmlrpclib.Fault(6, warning)
        except Bcfg2.Server.Plugins.Metadata.MetadataRuntimeError:
            err_msg = 'Metadata system runtime failure'
            self.logger.error(err_msg)
            raise xmlrpclib.Fault(6, err_msg)
        except:
            critical_error("Error determining client probes")

    @exposed
    def RecvProbeData(self, address, probedata):
        """Receive probe data from clients."""
        try:
            name = self.metadata.resolve_client(address)
            meta = self.build_metadata(name)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            warning = 'Metadata consistency error'
            self.logger.warning(warning)
            raise xmlrpclib.Fault(6, warning)
        # clear dynamic groups
        self.metadata.cgroups[meta.hostname] = []
        try:
            xpdata = lxml.etree.XML(probedata.encode('utf-8'))
        except:
            self.logger.error("Failed to parse probe data from client %s" % \
                              (address[0]))
            return False

        sources = []
        [sources.append(data.get('source')) for data in xpdata
         if data.get('source') not in sources]
        for source in sources:
            if source not in self.plugins:
                self.logger.warning("Failed to locate plugin %s" % (source))
                continue
            dl = [data for data in xpdata if data.get('source') == source]
            try:
                self.plugins[source].ReceiveData(meta, dl)
            except:
                logger.error("Failed to process probe data from client %s" % \
                             (address[0]), exc_info=1)
        return True

    @exposed
    def AssertProfile(self, address, profile):
        """Set profile for a client."""
        try:
            client = self.metadata.resolve_client(address)
            self.metadata.set_profile(client, profile, address)
        except (Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError,
                Bcfg2.Server.Plugins.Metadata.MetadataRuntimeError):
            warning = 'Metadata consistency error'
            self.logger.warning(warning)
            raise xmlrpclib.Fault(6, warning)
        return True

    @exposed
    def GetConfig(self, address, checksum=False):
        """Build config for a client."""
        try:
            client = self.metadata.resolve_client(address)
            config = self.BuildConfiguration(client)
            return lxml.etree.tostring(config, encoding='UTF-8',
                                       xml_declaration=True)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            self.logger.warning("Metadata consistency failure for %s" % (address))
            raise xmlrpclib.Fault(6, "Metadata consistency failure")

    @exposed
    def RecvStats(self, address, stats):
        """Act on statistics upload."""
        sdata = lxml.etree.XML(stats.encode('utf-8'))
        client = self.metadata.resolve_client(address)
        self.process_statistics(client, sdata)
        return "<ok/>"

    def authenticate(self, cert, user, password, address):
        if self.ca:
            acert = cert
        else:
            # No ca, so no cert validation can be done
            acert = None
        return self.metadata.AuthenticateConnection(acert, user, password, address)

    @exposed
    def GetDecisionList(self, address, mode):
        """Get the data of the decision list."""
        client = self.metadata.resolve_client(address)
        meta = self.build_metadata(client)
        return self.GetDecisions(meta, mode)
