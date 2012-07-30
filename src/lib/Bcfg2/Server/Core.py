"""Bcfg2.Server.Core provides the runtime support for Bcfg2 modules."""

import os
import atexit
import logging
import select
import sys
import threading
import time
import inspect
import lxml.etree
from traceback import format_exc

# this must be set before we import the Metadata plugin
os.environ['DJANGO_SETTINGS_MODULE'] = 'Bcfg2.settings'

import Bcfg2.settings
import Bcfg2.Server
import Bcfg2.Logger
import Bcfg2.Server.FileMonitor
import Bcfg2.Server.Plugins.Metadata
from Bcfg2.Bcfg2Py3k import xmlrpclib
from Bcfg2.Server.Plugin import PluginInitError, PluginExecutionError

if sys.hexversion >= 0x03000000:
    from functools import reduce

try:
    import psyco
    psyco.full()
except:
    pass

def exposed(func):
    func.exposed = True
    return func

def sort_xml(node, key=None):
    for child in node:
        sort_xml(child, key)

    try:
        sorted_children = sorted(node, key=key)
    except TypeError:
        sorted_children = node
    node[:] = sorted_children


class CoreInitError(Exception):
    """This error is raised when the core cannot be initialized."""
    pass


class BaseCore(object):
    """The Core object is the container for all
    Bcfg2 Server logic and modules.
    """

    def __init__(self, setup, start_fam_thread=False):
        self.datastore = setup['repo']

        self.logger = logging.getLogger('bcfg2-server')
        if 'debug' in setup and setup['debug']:
            level = logging.DEBUG
        else:
            level = logging.INFO
        self.logger.setLevel(level)
        Bcfg2.Logger.setup_logging('bcfg2-server',
                                   to_console=True,
                                   to_syslog=True,
                                   to_file=setup['logging'],
                                   level=level)

        try:
            fm = Bcfg2.Server.FileMonitor.available[setup['filemonitor']]
        except KeyError:
            self.logger.error("File monitor driver %s not available; "
                              "forcing to default" % filemonitor)
            fm = Bcfg2.Server.FileMonitor.available['default']
        famargs = dict(ignore=[], debug=False)
        if 'ignore' in setup:
            famargs['ignore'] = setup['ignore']
        if 'debug' in setup:
            famargs['debug'] = setup['debug']
        try:
            self.fam = fm(**famargs)
        except IOError:
            msg = "Failed to instantiate fam driver %s" % setup['filemonitor']
            self.logger.error(msg, exc_info=1)
            raise CoreInitError(msg)
        self.pubspace = {}
        self.cfile = setup['configfile']
        self.cron = {}
        self.plugins = {}
        self.plugin_blacklist = {}
        self.revision = '-1'
        self.password = setup['password']
        self.encoding = setup['encoding']
        self.setup = setup
        atexit.register(self.shutdown)
        # Create an event to signal worker threads to shutdown
        self.terminate = threading.Event()

        # generate Django ORM settings.  this must be done _before_ we
        # load plugins
        Bcfg2.settings.read_config(cfile=self.cfile, repo=self.datastore)

        if '' in setup['plugins']:
            setup['plugins'].remove('')

        for plugin in setup['plugins']:
            if not plugin in self.plugins:
                self.init_plugins(plugin)
        # Remove blacklisted plugins
        for p, bl in list(self.plugin_blacklist.items()):
            if len(bl) > 0:
                self.logger.error("The following plugins conflict with %s;"
                                  "Unloading %s" % (p, bl))
            for plug in bl:
                del self.plugins[plug]
        # This section logs the experimental plugins
        expl = [plug for (name, plug) in list(self.plugins.items())
                if plug.experimental]
        if expl:
            self.logger.info("Loading experimental plugin(s): %s" %
                             (" ".join([x.name for x in expl])))
            self.logger.info("NOTE: Interfaces subject to change")
        # This section logs the deprecated plugins
        depr = [plug for (name, plug) in list(self.plugins.items())
                if plug.deprecated]
        if depr:
            self.logger.info("Loading deprecated plugin(s): %s" %
                             (" ".join([x.name for x in depr])))

        mlist = self.plugins_by_type(Bcfg2.Server.Plugin.Metadata)
        if len(mlist) == 1:
            self.metadata = mlist[0]
        else:
            self.logger.error("No Metadata Plugin loaded; "
                              "failed to instantiate Core")
            raise CoreInitError("No Metadata Plugin")
        self.statistics = self.plugins_by_type(Bcfg2.Server.Plugin.Statistics)
        self.pull_sources = self.plugins_by_type(Bcfg2.Server.Plugin.PullSource)
        self.generators = self.plugins_by_type(Bcfg2.Server.Plugin.Generator)
        self.structures = self.plugins_by_type(Bcfg2.Server.Plugin.Structure)
        self.connectors = self.plugins_by_type(Bcfg2.Server.Plugin.Connector)
        self.ca = setup['ca']
        self.fam_thread = \
            threading.Thread(name="%sFAMThread" % setup['filemonitor'],
                             target=self._file_monitor_thread)
        self.lock = threading.Lock()

        if start_fam_thread:
            self.fam_thread.start()
            self.fam.AddMonitor(self.cfile, self.setup)

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
        self.logger.debug("Loading plugin %s" % plugin)
        try:
            mod = getattr(__import__("Bcfg2.Server.Plugins.%s" %
                                (plugin)).Server.Plugins, plugin)
        except ImportError:
            try:
                mod = __import__(plugin)
            except:
                self.logger.error("Failed to load plugin %s" % plugin)
                return
        plug = getattr(mod, plugin)
        # Blacklist conflicting plugins
        cplugs = [conflict for conflict in plug.conflicts
                  if conflict in self.plugins]
        self.plugin_blacklist[plug.name] = cplugs
        try:
            self.plugins[plugin] = plug(self, self.datastore)
        except PluginInitError:
            logger.error("Failed to instantiate plugin %s" % plugin, exc_info=1)
        except:
            self.logger.error("Unexpected instantiation failure for plugin %s" %
                              plugin, exc_info=1)

    def shutdown(self):
        """Shutting down the plugins."""
        if not self.terminate.isSet():
            self.terminate.set()
            self.fam.shutdown()
            for plugin in list(self.plugins.values()):
                plugin.shutdown()

    def client_run_hook(self, hook, metadata):
        """Checks the data structure."""
        for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.ClientRunHooks):
            try:
                getattr(plugin, hook)(metadata)
            except AttributeError:
                err = sys.exc_info()[1]
                self.logger.error("Unknown attribute: %s" % err)
                raise
            except:
                err = sys.exc_info()[1]
                self.logger.error("%s: Error invoking hook %s: %s" % (plugin,
                                                                      hook,
                                                                      err))

    def validate_structures(self, metadata, data):
        """Checks the data structure."""
        for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.StructureValidator):
            try:
                plugin.validate_structures(metadata, data)
            except Bcfg2.Server.Plugin.ValidationError:
                err = sys.exc_info()[1]
                self.logger.error("Plugin %s structure validation failed: %s" %
                                  (plugin.name, err))
                raise
            except:
                self.logger.error("Plugin %s: unexpected structure validation "
                                  "failure" % plugin.name, exc_info=1)

    def validate_goals(self, metadata, data):
        """Checks that the config matches the goals enforced by the plugins."""
        for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.GoalValidator):
            try:
                plugin.validate_goals(metadata, data)
            except Bcfg2.Server.Plugin.ValidationError:
                err = sys.exc_info()[1]
                self.logger.error("Plugin %s goal validation failed: %s" %
                                  (plugin.name, err.message))
                raise
            except:
                self.logger.error("Plugin %s: unexpected goal validation "
                                  "failure" % plugin.name, exc_info=1)

    def GetStructures(self, metadata):
        """Get all structures for client specified by metadata."""
        structures = reduce(lambda x, y: x + y,
                            [struct.BuildStructures(metadata)
                             for struct in self.structures], [])
        sbundles = [b.get('name') for b in structures if b.tag == 'Bundle']
        missing = [b for b in metadata.bundles if b not in sbundles]
        if missing:
            self.logger.error("Client %s configuration missing bundles: %s" %
                              (metadata.hostname, ':'.join(missing)))
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
                exc = sys.exc_info()[1]
                if 'failure' not in entry.attrib:
                    entry.set('failure', 'bind error: %s' % format_exc())
                self.logger.error("Failed to bind entry %s:%s: %s" %
                                  (entry.tag, entry.get('name'), exc))
            except Exception:
                exc = sys.exc_info()[1]
                if 'failure' not in entry.attrib:
                    entry.set('failure', 'bind error: %s' % format_exc())
                self.logger.error("Unexpected failure in BindStructure: %s %s" %
                                  (entry.tag, entry.get('name')), exc_info=1)

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
                self.logger.error("Failed binding entry %s:%s with altsrc %s" %
                                  (entry.tag, entry.get('name'),
                                   entry.get('altsrc')))
                self.logger.error("Falling back to %s:%s" % (entry.tag,
                                                             entry.get('name')))

        glist = [gen for gen in self.generators if
                 entry.get('name') in gen.Entries.get(entry.tag, {})]
        if len(glist) == 1:
            return glist[0].Entries[entry.tag][entry.get('name')](entry,
                                                                  metadata)
        elif len(glist) > 1:
            generators = ", ".join([gen.name for gen in glist])
            self.logger.error("%s %s served by multiple generators: %s" %
                              (entry.tag, entry.get('name'), generators))
        g2list = [gen for gen in self.generators if
                  gen.HandlesEntry(entry, metadata)]
        if len(g2list) == 1:
            return g2list[0].HandleEntry(entry, metadata)
        entry.set('failure', 'no matching generator')
        raise PluginExecutionError("No matching generator: %s:%s" %
                                   (entry.tag, entry.get('name')))

    def BuildConfiguration(self, client):
        """Build configuration for clients."""
        start = time.time()
        config = lxml.etree.Element("Configuration", version='2.0',
                                    revision=self.revision)
        try:
            meta = self.build_metadata(client)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            self.logger.error("Metadata consistency error for client %s" %
                              client)
            return lxml.etree.Element("error", type='metadata error')

        self.client_run_hook("start_client_run", meta)

        try:
            structures = self.GetStructures(meta)
        except:
            self.logger.error("error in GetStructures", exc_info=1)
            return lxml.etree.Element("error", type='structure error')

        self.validate_structures(meta, structures)

        # Perform altsrc consistency checking
        esrcs = {}
        for struct in structures:
            for entry in struct:
                key = (entry.tag, entry.get('name'))
                if key in esrcs:
                    if esrcs[key] != entry.get('altsrc'):
                        self.logger.error("Found inconsistent altsrc mapping "
                                          "for entry %s:%s" % key)
                else:
                    esrcs[key] = entry.get('altsrc', None)
        del esrcs

        for astruct in structures:
            try:
                self.BindStructure(astruct, meta)
                config.append(astruct)
            except:
                self.logger.error("error in BindStructure", exc_info=1)
        self.validate_goals(meta, config)

        self.client_run_hook("end_client_run", meta)

        sort_xml(config, key=lambda e: e.get('name'))

        self.logger.info("Generated config for %s in %.03f seconds" %
                         (client, time.time() - start))
        return config

    def run(self, **kwargs):
        """ run the server core """
        raise NotImplementedError

    def _daemonize(self):
        child_pid = os.fork()
        if child_pid != 0:
            return

        os.setsid()

        child_pid = os.fork()
        if child_pid != 0:
            os._exit(0)
            
        redirect_file = open("/dev/null", "w+")
        os.dup2(redirect_file.fileno(), sys.__stdin__.fileno())
        os.dup2(redirect_file.fileno(), sys.__stdout__.fileno())
        os.dup2(redirect_file.fileno(), sys.__stderr__.fileno())

        os.chdir(os.sep)
        
        pidfile = open(self.setup['daemon'] or "/dev/null", "w")
        pidfile.write("%s\n" % os.getpid())
        pidfile.close()

        return os.getpid()

    def critical_error(self, operation):
        """ this should be overridden by child classes """
        self.logger.fatal(operation, exc_info=1)

    def GetDecisions(self, metadata, mode):
        """Get data for the decision list."""
        result = []
        for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.Decision):
            try:
                result += plugin.GetDecisions(metadata, mode)
            except:
                self.logger.error("Plugin: %s failed to generate decision list"
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
                    self.logger.error("Plugin %s failed to process stats from "
                                      "%s" % (plugin.name, meta.hostname),
                                      exc_info=1)

        self.logger.info("Client %s reported state %s" % (client_name,
                                                          state.get('state')))
        self.client_run_hook("end_statistics", meta)

    def resolve_client(self, address, cleanup_cache=False, metadata=True):
        try:
            client = self.metadata.resolve_client(address,
                                                  cleanup_cache=cleanup_cache)
            if metadata:
                meta = self.build_metadata(client)
            else:
                meta = None
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            err = sys.exc_info()[1]
            self.critical_error("Client metadata resolution error for %s: %s" %
                                (address[0], err))
        except Bcfg2.Server.Plugins.Metadata.MetadataRuntimeError:
            err = sys.exc_info()[1]
            self.critical_error('Metadata system runtime failure for %s: %s' %
                                (address[0], err))
        return (client, meta)

    def critical_error(self, operation):
        """Log and err, traceback and return an xmlrpc fault to client."""
        self.logger.error(operation, exc_info=1)
        raise xmlrpclib.Fault(xmlrpclib.APPLICATION_ERROR,
                              "Critical failure: %s" % operation)

    def _get_rmi(self):
        rmi = dict()
        if self.plugins:
            for pname, pinst in list(self.plugins.items()):
                for mname in pinst.__rmi__:
                    rmi["%s.%s" % (pname, mname)] = getattr(pinst, mname)
        return rmi

    # XMLRPC handlers start here
    @exposed
    def listMethods(self, address):
        methods = [name
                   for name, func in inspect.getmembers(self, callable)
                   if getattr(func, "exposed", False)]
        methods.extend(self._get_rmi().keys())
        return methods

    @exposed
    def methodHelp(self, address, method_name):
        raise NotImplementedError

    @exposed
    def DeclareVersion(self, address, version):
        """ declare the client version """
        client, metadata = self.resolve_client(address)
        try:
            self.metadata.set_version(client, version)
        except (Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError,
                Bcfg2.Server.Plugins.Metadata.MetadataRuntimeError):
            err = sys.exc_info()[1]
            self.critical_error("Unable to set version for %s: %s" %
                                (client, err))
        return True

    @exposed
    def GetProbes(self, address):
        """Fetch probes for a particular client."""
        resp = lxml.etree.Element('probes')
        client, metadata = self.resolve_client(address, cleanup_cache=True)
        try:
            for plugin in self.plugins_by_type(Bcfg2.Server.Plugin.Probing):
                for probe in plugin.GetProbes(metadata):
                    resp.append(probe)
            return lxml.etree.tostring(resp, encoding='UTF-8',
                                       xml_declaration=True)
        except:
            err = sys.exc_info()[1]
            self.critical_error("Error determining probes for %s" %
                                (client, err))

    @exposed
    def RecvProbeData(self, address, probedata):
        """Receive probe data from clients."""
        client, metadata = self.resolve_client(address)
        try:
            xpdata = lxml.etree.XML(probedata.encode('utf-8'),
                                    parser=Bcfg2.Server.XMLParser)
        except:
            err = sys.exc_info()[1]
            self.critical_error("Failed to parse probe data from client %s: %s"
                                % (client, err))

        sources = []
        [sources.append(data.get('source')) for data in xpdata
         if data.get('source') not in sources]
        for source in sources:
            if source not in self.plugins:
                self.logger.warning("Failed to locate plugin %s" % source)
                continue
            dl = [data for data in xpdata if data.get('source') == source]
            try:
                self.plugins[source].ReceiveData(metadata, dl)
            except:
                err = sys.exc_info()[1]
                self.critical_error("Failed to process probe data from client "
                                    "%s: %s" %
                                    (client, err))
        return True

    @exposed
    def AssertProfile(self, address, profile):
        """Set profile for a client."""
        client = self.resolve_client(address, metadata=False)[0]
        try:
            self.metadata.set_profile(client, profile, address)
        except (Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError,
                Bcfg2.Server.Plugins.Metadata.MetadataRuntimeError):
            err = sys.exc_info()[1]
            self.critical_error("Unable to assert profile for %s: %s" %
                           (client, err))
        return True

    @exposed
    def GetConfig(self, address, checksum=False):
        """Build config for a client."""
        client = self.resolve_client(address)[0]
        try:
            config = self.BuildConfiguration(client)
            return lxml.etree.tostring(config, encoding='UTF-8',
                                       xml_declaration=True)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            self.critical_error("Metadata consistency failure for %s" % client)

    @exposed
    def RecvStats(self, address, stats):
        """Act on statistics upload."""
        client = self.resolve_client(address)[0]
        sdata = lxml.etree.XML(stats.encode('utf-8'),
                               parser=Bcfg2.Server.XMLParser)
        self.process_statistics(client, sdata)
        return "<ok/>"

    def authenticate(self, cert, user, password, address):
        if self.ca:
            acert = cert
        else:
            # No ca, so no cert validation can be done
            acert = None
        return self.metadata.AuthenticateConnection(acert, user, password,
                                                    address)

    @exposed
    def GetDecisionList(self, address, mode):
        """Get the data of the decision list."""
        client, metadata = self.resolve_client(address)
        return self.GetDecisions(metadata, mode)
