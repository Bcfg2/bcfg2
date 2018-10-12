""" Bcfg2.Server.Core provides the base core object that server core
implementations inherit from. """

import os
import pwd
import atexit
import logging
import select
import sys
import threading
import time
import inspect
import lxml.etree
import daemon
import Bcfg2.Server
import Bcfg2.Logger
import Bcfg2.Options
import Bcfg2.DBSettings
import Bcfg2.Server.Statistics
import Bcfg2.Server.FileMonitor
from itertools import chain
from Bcfg2.Server.Cache import Cache
from Bcfg2.Compat import xmlrpclib, wraps  # pylint: disable=W0622
from Bcfg2.Server.Plugin.exceptions import *  # pylint: disable=W0401,W0614
from Bcfg2.Server.Plugin.interfaces import *  # pylint: disable=W0401,W0614
from Bcfg2.Server.Statistics import track_statistics

try:
    from django.core.exceptions import ImproperlyConfigured
    import django
    import django.conf
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

try:
    import psyco
    psyco.full()
except ImportError:
    pass


def exposed(func):
    """ Decorator that sets the ``exposed`` attribute of a function to
    ``True`` expose it via XML-RPC.  This currently works for both the
    builtin and CherryPy cores, although if other cores are added this
    may need to be made a core-specific function.

    :param func: The function to decorate
    :type func: callable
    :returns: callable - the decorated function"""
    func.exposed = True
    return func


def sort_xml(node, key=None):
    """ Recursively sort an XML document in a deterministic fashion.
    This shouldn't be used to perform a *useful* sort, merely to put
    XML in a deterministic, replicable order.  The document is sorted
    in-place.

    :param node: The root node of the XML tree to sort
    :type node: lxml.etree._Element or lxml.etree.ElementTree
    :param key: The key to sort by
    :type key: callable
    :returns: None
    """
    for child in node:
        sort_xml(child, key)

    try:
        sorted_children = sorted(node, key=key)
    except TypeError:
        sorted_children = node
    node[:] = sorted_children


def close_db_connection(func):
    """ Decorator that closes the Django database connection at the end of
    the function.  This should decorate any exposed function that
    might open a database connection. """
    @wraps(func)
    def inner(self, *args, **kwargs):
        """ The decorated function """
        rv = func(self, *args, **kwargs)
        if self._database_available:  # pylint: disable=W0212
            self.logger.debug("%s: Closing database connection" %
                              threading.current_thread().getName())

            if django.VERSION[0] == 1 and django.VERSION[1] >= 7:
                for connection in django.db.connections.all():
                    connection.close()
            else:
                django.db.close_connection()  # pylint: disable=E1101
        return rv

    return inner


class CoreInitError(Exception):
    """ Raised when the server core cannot be initialized. """
    pass


class NoExposedMethod (Exception):
    """ Raised when an XML-RPC method is called, but there is no
    method exposed with the given name. """


class DefaultACL(Plugin, ClientACLs):
    """ Default ACL 'plugin' that provides security by default. This
    is only loaded if no other ClientACLs plugin is enabled. """
    create = False

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.ClientACLs.__init__(self)

    def check_acl_ip(self, address, rmi):
        return (("." not in rmi and
                 not rmi.endswith("_debug") and
                 rmi != 'get_statistics' and
                 rmi != 'expire_metadata_cache') or
                address[0] == "127.0.0.1")

# in core we frequently want to catch all exceptions, regardless of
# type, so disable the pylint rule that catches that.
# pylint: disable=W0702


class Core(object):
    """ The server core is the container for all Bcfg2 server logic
    and modules. All core implementations must inherit from
    ``Core``. """

    options = [
        Bcfg2.Options.Common.plugins,
        Bcfg2.Options.Common.repository,
        Bcfg2.Options.Common.filemonitor,
        Bcfg2.Options.BooleanOption(
            "--no-fam-blocking", cf=('server', 'fam_blocking'),
            dest="fam_blocking", default=True,
            help='FAM blocks on startup until all events are processed'),
        Bcfg2.Options.BooleanOption(
            cf=('logging', 'performance'), dest="perflog",
            help="Periodically log performance statistics"),
        Bcfg2.Options.Option(
            cf=('logging', 'performance_interval'), default=300.0,
            type=Bcfg2.Options.Types.timeout,
            help="Performance statistics logging interval in seconds"),
        Bcfg2.Options.Option(
            cf=('caching', 'client_metadata'), dest='client_metadata_cache',
            default='off',
            choices=['off', 'on', 'initial', 'cautious', 'aggressive'])]

    #: The name of this server core. This can be overridden by core
    #: implementations to provide a more specific name.
    name = "Core"

    def __init__(self):  # pylint: disable=R0912,R0915
        """
        .. automethod:: _run
        .. automethod:: _block
        .. -----
        .. automethod:: _file_monitor_thread
        .. automethod:: _perflog_thread
        """
        # Record the core as a module variable
        Bcfg2.Server.core = self

        #: A :class:`logging.Logger` object for use by the core
        self.logger = logging.getLogger('bcfg2-server')

        #: Log levels for the various logging handlers with debug True
        #: and False.  Each loglevel dict is a dict of ``logger name
        #: => log level``; the logger names are set in
        #: :mod:`Bcfg2.Logger`.  The logger name ``default`` is
        #: special, and will be used for any log handlers whose name
        #: does not appear elsewhere in the dict.  At a minimum,
        #: ``default`` must be provided.
        self._loglevels = {
            True: dict(default=logging.DEBUG),
            False: dict(console=logging.INFO,
                        default=Bcfg2.Logger.default_log_level())}

        #: Used to keep track of the current debug state of the core.
        self.debug_flag = False

        # enable debugging on the core now.  debugging is enabled on
        # everything else later
        if Bcfg2.Options.setup.debug:
            self.set_core_debug(None, Bcfg2.Options.setup.debug)

        try:
            #: The :class:`Bcfg2.Server.FileMonitor.FileMonitor`
            #: object used by the core to monitor for Bcfg2 data
            #: changes.
            self.fam = Bcfg2.Server.FileMonitor.get_fam()
        except IOError:
            msg = "Failed to instantiate fam driver %s" % \
                Bcfg2.Options.setup.filemonitor
            self.logger.error(msg, exc_info=1)
            raise CoreInitError(msg)

        #: Path to bcfg2.conf
        self.cfile = Bcfg2.Options.setup.config

        #: Dict of plugins that are enabled.  Keys are the plugin
        #: names (just the plugin name, in the correct case; e.g.,
        #: "Cfg", not "Bcfg2.Server.Plugins.Cfg"), and values are
        #: plugin objects.
        self.plugins = {}

        #: Blacklist of plugins that conflict with enabled plugins.
        #: If two plugins are loaded that conflict with each other,
        #: the first one loaded wins.
        self.plugin_blacklist = {}

        #: The Metadata plugin
        self.metadata = None

        #: Revision of the Bcfg2 specification.  This will be sent to
        #: the client in the configuration, and can be set by a
        #: :class:`Bcfg2.Server.Plugin.interfaces.Version` plugin.
        self.revision = '-1'

        atexit.register(self.shutdown)
        #: if :func:`Bcfg2.Server.Core.shutdown` is called explicitly,
        #: then :mod:`atexit` calls it *again*, so it gets called
        #: twice.  This is potentially bad, so we use
        #: :attr:`Bcfg2.Server.Core._running` as a flag to determine
        #: if the core needs to be shutdown, and only do it once.
        self._running = True

        #: Threading event to signal worker threads (e.g.,
        #: :attr:`fam_thread`) to shutdown
        self.terminate = threading.Event()

        #: RLock to be held on writes to the backend db
        self.db_write_lock = threading.RLock()

        # mapping of group name => plugin name to record where groups
        # that are created by Connector plugins came from
        self._dynamic_groups = dict()

        #: The FAM :class:`threading.Thread`,
        #: :func:`_file_monitor_thread`
        self.fam_thread = \
            threading.Thread(name="%sFAMThread" %
                             Bcfg2.Options.setup.filemonitor.__name__,
                             target=self._file_monitor_thread)

        #: The :class:`threading.Thread` that reports performance
        #: statistics to syslog.
        self.perflog_thread = None
        if Bcfg2.Options.setup.perflog:
            self.perflog_thread = \
                threading.Thread(name="PerformanceLoggingThread",
                                 target=self._perflog_thread)

        #: A :func:`threading.Lock` for use by
        #: :func:`Bcfg2.Server.FileMonitor.FileMonitor.handle_event_set`
        self.lock = threading.Lock()

        #: A :class:`Bcfg2.Server.Cache.Cache` object for caching client
        #: metadata
        self.metadata_cache = Cache("Metadata")

        #: Whether or not it's possible to use the Django database
        #: backend for plugins that have that capability
        self._database_available = False
        if HAS_DJANGO:
            try:
                Bcfg2.DBSettings.sync_databases(interactive=False,
                                                verbosity=0)
                self._database_available = True
            except ImproperlyConfigured:
                self.logger.error("Django configuration problem: %s" %
                                  sys.exc_info()[1])
            except:
                self.logger.error("Updating database %s failed: %s" %
                                  (Bcfg2.Options.setup.db_name,
                                   sys.exc_info()[1]))

    def __str__(self):
        return self.__class__.__name__

    def plugins_by_type(self, base_cls):
        """ Return a list of loaded plugins that match the passed type.

        The returned list is sorted in ascending order by the plugins'
        ``sort_order`` value. The
        :attr:`Bcfg2.Server.Plugin.base.Plugin.sort_order` defaults to
        500, but can be overridden by individual plugins. Plugins with
        the same numerical sort_order value are sorted in alphabetical
        order by their name.

        :param base_cls: The base plugin interface class to match (see
                         :mod:`Bcfg2.Server.Plugin.interfaces`)
        :type base_cls: type
        :returns: list of :attr:`Bcfg2.Server.Plugin.base.Plugin`
                  objects
        """
        return sorted([plugin for plugin in self.plugins.values()
                       if isinstance(plugin, base_cls)],
                      key=lambda p: (p.sort_order, p.name))

    def _perflog_thread(self):
        """ The thread that periodically logs performance statistics
        to syslog. """
        self.logger.debug("Performance logging thread starting")
        while not self.terminate.isSet():
            self.terminate.wait(Bcfg2.Options.setup.performance_interval)
            if not self.terminate.isSet():
                for name, stats in self.get_statistics(None).items():
                    self.logger.info("Performance statistics: "
                                     "%s min=%.06f, max=%.06f, average=%.06f, "
                                     "count=%d" % ((name, ) + stats))
        self.logger.info("Performance logging thread terminated")

    def _file_monitor_thread(self):
        """ The thread that runs the
        :class:`Bcfg2.Server.FileMonitor.FileMonitor`. This also
        queries :class:`Bcfg2.Server.Plugin.interfaces.Version`
        plugins for the current revision of the Bcfg2 repo. """
        self.logger.debug("File monitor thread starting")
        famfd = self.fam.fileno()
        terminate = self.terminate
        while not terminate.isSet():
            if famfd:
                select.select([famfd], [], [], 2)
            elif not self.fam.pending():
                terminate.wait(15)

            if self.terminate.isSet():
                break

            if self.fam.pending():
                try:
                    self._update_vcs_revision()
                except:
                    self.logger.error("Error updating VCS revision: %s" %
                                      sys.exc_info()[1])
            try:
                self.fam.handle_event_set(self.lock)
            except:
                self.logger.error("Error handling event set: %s" %
                                  sys.exc_info()[1])
        self.logger.info("File monitor thread terminated")

    @track_statistics()
    def _update_vcs_revision(self):
        """ Update the revision of the current configuration on-disk
        from the VCS plugin """
        for plugin in self.plugins_by_type(Version):
            try:
                newrev = plugin.get_revision()
                if newrev != self.revision:
                    self.logger.debug("Updated to revision %s" % newrev)
                self.revision = newrev
                break
            except:
                self.logger.warning("Error getting revision from %s: %s" %
                                    (plugin.name, sys.exc_info()[1]))
                self.revision = '-1'

    def load_plugins(self):
        """ Load all plugins, setting
        :attr:`Bcfg2.Server.Core.BaseCore.plugins` and
        :attr:`Bcfg2.Server.Core.BaseCore.metadata` as side effects.
        This does not start plugin threads; that is done later, in
        :func:`Bcfg2.Server.Core.BaseCore.run` """
        for plugin in Bcfg2.Options.setup.plugins:
            if plugin not in self.plugins:
                self.init_plugin(plugin)

        # Remove blacklisted plugins
        for plugin, blacklist in list(self.plugin_blacklist.items()):
            if len(blacklist) > 0:
                self.logger.error("The following plugins conflict with %s;"
                                  "Unloading %s" % (plugin, blacklist))
            for plug in blacklist:
                del self.plugins[plug]

        # Log deprecated and experimental plugins
        expl = []
        depr = []
        for plug in list(self.plugins.values()):
            if plug.experimental:
                expl.append(plug)
            if plug.deprecated:
                depr.append(plug)
        if expl:
            self.logger.info("Loading experimental plugin(s): %s" %
                             (" ".join([x.name for x in expl])))
            self.logger.info("NOTE: Interfaces subject to change")
        if depr:
            self.logger.info("Loading deprecated plugin(s): %s" %
                             (" ".join([x.name for x in depr])))

        # Find the metadata plugin and set self.metadata
        mlist = self.plugins_by_type(Metadata)
        if len(mlist) >= 1:
            self.metadata = mlist[0]
            if len(mlist) > 1:
                self.logger.error("Multiple Metadata plugins loaded; using %s"
                                  % self.metadata)
        else:
            self.logger.error("No Metadata plugin loaded; "
                              "failed to instantiate Core")
            raise CoreInitError("No Metadata Plugin")

        # ensure that an ACL plugin is loaded
        if not self.plugins_by_type(Bcfg2.Server.Plugin.ClientACLs):
            self.init_plugin(DefaultACL)

    def init_plugin(self, plugin):
        """ Import and instantiate a single plugin.  The plugin is
        stored to :attr:`plugins`.

        :param plugin: The plugin class to load.
        :type plugin: type
        :returns: None
        """
        self.logger.debug("Loading plugin %s" % plugin.name)
        # Blacklist conflicting plugins
        cplugs = [conflict for conflict in plugin.conflicts
                  if conflict in self.plugins]
        self.plugin_blacklist[plugin.name] = cplugs
        try:
            self.plugins[plugin.name] = plugin(self)
        except PluginInitError:
            self.logger.error("Failed to instantiate plugin %s" % plugin,
                              exc_info=1)
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("Failed to add a file monitor while "
                              "instantiating plugin %s: %s" % (plugin, err))
        except:
            self.logger.error("Unexpected instantiation failure for plugin %s"
                              % plugin, exc_info=1)

    @close_db_connection
    def shutdown(self):
        """ Perform plugin and FAM shutdown tasks. """
        if not self._running:
            self.logger.debug("%s: Core already shut down" % self.name)
            return
        self.logger.info("%s: Shutting down core..." % self.name)
        if not self.terminate.isSet():
            self.terminate.set()
        self._running = False
        self.fam.shutdown()
        self.logger.info("%s: FAM shut down" % self.name)
        for plugin in list(self.plugins.values()):
            plugin.shutdown()
        self.logger.info("%s: All plugins shut down" % self.name)

    @property
    def metadata_cache_mode(self):
        """ Get the client :attr:`metadata_cache` mode.  Options are
        off, initial, cautious, aggressive, on (synonym for
        cautious). See :ref:`server-caching` for more details. """
        mode = Bcfg2.Options.setup.client_metadata_cache
        if mode == "on":
            return "cautious"
        else:
            return mode

    def client_run_hook(self, hook, metadata):
        """ Invoke hooks from
        :class:`Bcfg2.Server.Plugin.interfaces.ClientRunHooks` plugins
        for a given stage.

        :param hook: The name of the stage to run hooks for.  A stage
                     can be any abstract function defined in the
                     :class:`Bcfg2.Server.Plugin.interfaces.ClientRunHooks`
                     interface.
        :type hook: string
        :param metadata: Client metadata to run the hook for.  This
                         will be passed as the sole argument to each
                         hook.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        self.logger.debug("Running %s hooks for %s" % (hook,
                                                       metadata.hostname))
        start = time.time()
        try:
            for plugin in self.plugins_by_type(ClientRunHooks):
                try:
                    getattr(plugin, hook)(metadata)
                except AttributeError:
                    err = sys.exc_info()[1]
                    self.logger.error("Unknown attribute: %s" % err)
                    raise
                except:
                    err = sys.exc_info()[1]
                    self.logger.error("%s: Error invoking hook %s: %s" %
                                      (plugin, hook, err))
        finally:
            Bcfg2.Server.Statistics.stats.add_value(
                "%s:client_run_hook:%s" %
                (self.__class__.__name__, hook),
                time.time() - start)

    @track_statistics()
    def validate_structures(self, metadata, data):
        """ Checks the data structures by calling the
        :func:`Bcfg2.Server.Plugin.interfaces.StructureValidator.validate_structures`
        method of
        :class:`Bcfg2.Server.Plugin.interfaces.StructureValidator`
        plugins.

        :param metadata: Client metadata to validate structures for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param data: The list of structures (i.e., bundles) for this
                     client
        :type data: list of lxml.etree._Element objects
        """
        self.logger.debug("Validating structures for %s" % metadata.hostname)
        for plugin in self.plugins_by_type(StructureValidator):
            try:
                plugin.validate_structures(metadata, data)
            except ValidationError:
                err = sys.exc_info()[1]
                self.logger.error("Plugin %s structure validation failed: %s" %
                                  (plugin.name, err))
                raise
            except:
                self.logger.error("Plugin %s: unexpected structure validation "
                                  "failure" % plugin.name, exc_info=1)

    @track_statistics()
    def validate_goals(self, metadata, data):
        """ Checks that the config matches the goals enforced by
        :class:`Bcfg2.Server.Plugin.interfaces.GoalValidator` plugins
        by calling
        :func:`Bcfg2.Server.Plugin.interfaces.GoalValidator.validate_goals`.

        :param metadata: Client metadata to validate goals for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param data: The list of structures (i.e., bundles) for this
                     client
        :type data: list of lxml.etree._Element objects
        """
        self.logger.debug("Validating goals for %s" % metadata.hostname)
        for plugin in self.plugins_by_type(GoalValidator):
            try:
                plugin.validate_goals(metadata, data)
            except ValidationError:
                err = sys.exc_info()[1]
                self.logger.error("Plugin %s goal validation failed: %s" %
                                  (plugin.name, err.message))
                raise
            except:
                self.logger.error("Plugin %s: unexpected goal validation "
                                  "failure" % plugin.name, exc_info=1)

    @track_statistics()
    def GetStructures(self, metadata):
        """ Get all structures (i.e., bundles) for the given client

        :param metadata: Client metadata to get structures for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: list of :class:`lxml.etree._Element` objects
        """
        self.logger.debug("Getting structures for %s" % metadata.hostname)
        structures = list(
            chain(*[struct.BuildStructures(metadata)
                    for struct in self.plugins_by_type(Structure)]))
        sbundles = [b.get('name') for b in structures
                    if b.tag == 'Bundle' or b.tag == 'Independent']
        missing = [b for b in metadata.bundles if b not in sbundles]
        if missing:
            self.logger.error("Client %s configuration missing bundles: %s" %
                              (metadata.hostname, ':'.join(missing)))
        return structures

    @track_statistics()
    def BindStructures(self, structures, metadata, config):
        """ Given a list of structures (i.e. bundles), bind all the
        entries in them and add the structures to the config.

        :param structures: The list of structures for this client
        :type structures: list of lxml.etree._Element objects
        :param metadata: Client metadata to bind structures for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param config: The configuration document to add fully-bound
                       structures to. Modified in-place.
        :type config: lxml.etree._Element
        """
        self.logger.debug("Binding structures for %s" % metadata.hostname)
        for astruct in structures:
            try:
                self.BindStructure(astruct, metadata)
                config.append(astruct)
            except:
                self.logger.error("error in BindStructure", exc_info=1)

    @track_statistics()
    def BindStructure(self, structure, metadata):
        """ Bind all elements in a single structure (i.e., bundle).

        :param structure: The structure to bind.  Modified in-place.
        :type structures: lxml.etree._Element
        :param metadata: Client metadata to bind structure for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        self.logger.debug("Binding structure %s for %s" %
                          (structure.get("name", "unknown"),
                           metadata.hostname))
        for entry in structure.getchildren():
            if entry.tag.startswith("Bound"):
                entry.tag = entry.tag[5:]
                continue
            try:
                self.Bind(entry, metadata)
            except:
                exc = sys.exc_info()[1]
                if 'failure' not in entry.attrib:
                    entry.set('failure', 'bind error: %s' % exc)
                if isinstance(exc, PluginExecutionError):
                    msg = "Failed to bind entry"
                else:
                    msg = "Unexpected failure binding entry"
                self.logger.error("%s %s:%s: %s" %
                                  (msg, entry.tag, entry.get('name'), exc))

    def Bind(self, entry, metadata):
        """ Bind a single entry using the appropriate generator.

        :param entry: The entry to bind.  Modified in-place.
        :type entry: lxml.etree._Element
        :param metadata: Client metadata to bind structure for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        start = time.time()
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
                self.logger.error(
                    "Failed binding entry %s:%s with altsrc %s: %s" %
                    (entry.tag, entry.get('realname'), entry.get('name'),
                     sys.exc_info()[1]))
                entry.set('name', oldname)
                self.logger.error("Falling back to %s:%s" %
                                  (entry.tag, entry.get('name')))

        generators = self.plugins_by_type(Generator)
        glist = [gen for gen in generators
                 if entry.get('name') in gen.Entries.get(entry.tag, {})]
        if len(glist) == 1:
            return glist[0].Entries[entry.tag][entry.get('name')](entry,
                                                                  metadata)
        elif len(glist) > 1:
            generators = ", ".join([gen.name for gen in glist])
            self.logger.error("%s %s served by multiple generators: %s" %
                              (entry.tag, entry.get('name'), generators))
        g2list = [gen for gen in generators
                  if gen.HandlesEntry(entry, metadata)]
        try:
            if len(g2list) == 1:
                return g2list[0].HandleEntry(entry, metadata)
            entry.set('failure', 'no matching generator')
            raise PluginExecutionError("No matching generator: %s:%s" %
                                       (entry.tag, entry.get('name')))
        finally:
            Bcfg2.Server.Statistics.stats.add_value("%s:Bind:%s" %
                                                    (self.__class__.__name__,
                                                     entry.tag),
                                                    time.time() - start)

    def BuildConfiguration(self, client):
        """ Build the complete configuration for a client.

        :param client: The hostname of the client to build the
                       configuration for
        :type client: string
        :returns: :class:`lxml.etree._Element` - A complete Bcfg2
                  configuration document """
        self.logger.debug("Building configuration for %s" % client)
        start = time.time()
        config = lxml.etree.Element("Configuration", version='2.0',
                                    revision=str(self.revision))
        try:
            meta = self.build_metadata(client)
        except MetadataConsistencyError:
            self.logger.error("Metadata consistency error for client %s" %
                              client)
            return lxml.etree.Element("error", type='metadata error')

        self.client_run_hook("start_client_run", meta)

        try:
            structures = self.GetStructures(meta)
        except:
            self.logger.error("Error in GetStructures", exc_info=1)
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

        self.BindStructures(structures, meta, config)

        self.validate_goals(meta, config)

        self.client_run_hook("end_client_run", meta)

        sort_xml(config, key=lambda e: e.get('name'))

        self.logger.info("Generated config for %s in %.03f seconds" %
                         (client, time.time() - start))
        return config

    def HandleEvent(self, event):
        """ Handle a change in the Bcfg2 config file.

        :param event: The event to handle
        :type event: Bcfg2.Server.FileMonitor.Event
        """
        if event.filename != self.cfile:
            self.logger.error("Got event for unknown file: %s" %
                              event.filename)
            return
        if event.code2str() in ['deleted', 'exists']:
            # ignore config file deletion, and ignore the initial
            # 'exists' event as well.  we've already parsed options on
            # startup, we don't need to parse them twice.
            return
        Bcfg2.Options.get_parser().reparse()
        self.metadata_cache.expire()

    def block_for_fam_events(self, handle_events=False):
        """ Block until all fam events have been handleed, optionally
        handling events as well.  (Setting ``handle_events=True`` is
        useful for local server cores that don't spawn an event
        handling thread.)"""
        slept = 0
        log_interval = 3
        if handle_events:
            self.fam.handle_events_in_interval(1)
            slept += 1
        if Bcfg2.Options.setup.fam_blocking:
            time.sleep(1)
            slept += 1
            while self.fam.pending() != 0:
                time.sleep(1)
                slept += 1
                if slept % log_interval == 0:
                    self.logger.debug("Sleeping to handle FAM events...")
        self.logger.debug("Slept %s seconds while handling FAM events" % slept)

    def run(self):
        """ Run the server core. This calls :func:`_run`, starts the
        :attr:`fam_thread`, and calls :func:`_block`, but note that it
        is the responsibility of the server core implementation to
        call :func:`shutdown` under normal operation. This also
        handles creation of the directory containing the pidfile, if
        necessary."""
        if not self._run():
            self.shutdown()
            return False

        try:
            self.load_plugins()

            self.fam.start()
            self.fam_thread.start()
            self.fam.AddMonitor(self.cfile, self)
            if self.perflog_thread is not None:
                self.perflog_thread.start()

            for plug in self.plugins_by_type(Threaded):
                plug.start_threads()

            self.block_for_fam_events()
            self._block()
        except:
            self.shutdown()
            raise

    def _run(self):
        """ Start up the server; this method should return
        immediately.  This must be overridden by a core
        implementation. """
        raise NotImplementedError

    def _block(self):
        """ Enter the infinite loop.  This method should not return
        until the server is killed.  This must be overridden by a core
        implementation. """
        raise NotImplementedError

    def GetDecisions(self, metadata, mode):
        """ Get the decision list for a client.

        :param metadata: Client metadata to get the decision list for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param mode: The decision mode ("whitelist" or "blacklist")
        :type mode: string
        :returns: list of Decision tuples ``(<entry tag>, <entry name>)``
        """
        self.logger.debug("Getting decision list for %s" % metadata.hostname)
        result = []
        for plugin in self.plugins_by_type(Decision):
            try:
                result.extend(plugin.GetDecisions(metadata, mode))
            except:
                self.logger.error("Plugin: %s failed to generate decision list"
                                  % plugin.name, exc_info=1)
        return result

    @track_statistics()
    def check_acls(self, address, rmi):
        """ Check client IP address and metadata object against all
        :class:`Bcfg2.Server.Plugin.interfaces.ClientACLs` plugins.
        If any ACL plugin denies access, then access is denied.  ACLs
        are checked in two phases: First, with the client IP address;
        and second, with the client metadata object.  This lets an ACL
        interface do a quick rejection based on IP before metadata is
        ever built.

        :param address: The address pair of the client to check ACLs for
        :type address: tuple of (<ip address>, <port>)
        :param rmi: The fully-qualified name of the RPC call
        :param rmi: string
        :returns: bool
        """
        plugins = self.plugins_by_type(Bcfg2.Server.Plugin.ClientACLs)
        try:
            ip_checks = [p.check_acl_ip(address, rmi) for p in plugins]
        except:
            self.logger.error("Unexpected error checking ACLs for %s for %s: "
                              "%s" % (address[0], rmi, sys.exc_info()[1]))
            return False  # failsafe

        if all(ip_checks):
            # if all ACL plugins return True (allow), then allow
            self.logger.debug("Client %s passed IP-based ACL checks for %s" %
                              (address[0], rmi))
            return True
        elif False in ip_checks:
            # if any ACL plugin returned False (deny), then deny
            self.logger.warning("Client %s failed IP-based ACL checks for %s" %
                                (address[0], rmi))
            return False
        # else, no plugins returned False, but not all plugins
        # returned True, so some plugin returned None (defer), so
        # defer.

        client, metadata = self.resolve_client(address)
        try:
            rv = all(p.check_acl_metadata(metadata, rmi) for p in plugins)
            if rv:
                self.logger.debug(
                    "Client %s passed metadata ACL checks for %s" %
                    (metadata.hostname, rmi))
            else:
                self.logger.warning(
                    "Client %s failed metadata ACL checks for %s" %
                    (metadata.hostname, rmi))
            return rv
        except:
            self.logger.error("Unexpected error checking ACLs for %s for %s: "
                              "%s" % (client, rmi, sys.exc_info()[1]))
            return False  # failsafe

    @track_statistics()
    def build_metadata(self, client_name):
        """ Build initial client metadata for a client

        :param client_name: The name of the client to build metadata
                            for
        :type client_name: string
        :returns: :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata`
        """
        if not hasattr(self, 'metadata'):
            # some threads start before metadata is even loaded
            raise MetadataRuntimeError("Metadata not loaded yet")
        if self.metadata_cache_mode == 'initial':
            # the Metadata plugin handles loading the cached data if
            # we're only caching the initial metadata object
            imd = None
        else:
            imd = self.metadata_cache.get(client_name, None)
        if not imd:
            self.logger.debug("Building metadata for %s" % client_name)
            try:
                imd = self.metadata.get_initial_metadata(client_name)
            except MetadataConsistencyError:
                self.critical_error(
                    "Client metadata resolution error for %s: %s" %
                    (client_name, sys.exc_info()[1]))
            connectors = self.plugins_by_type(Connector)
            for conn in connectors:
                groups = conn.get_additional_groups(imd)
                groupnames = []
                for group in groups:
                    if hasattr(group, "name"):
                        groupname = group.name
                        if groupname in self._dynamic_groups:
                            if self._dynamic_groups[groupname] == conn.name:
                                self.metadata.groups[groupname] = group
                            else:
                                self.logger.warning(
                                    "Refusing to clobber dynamic group %s "
                                    "defined by %s" %
                                    (self._dynamic_groups[groupname],
                                     groupname))
                        elif groupname in self.metadata.groups:
                            # not recorded as a dynamic group, but
                            # present in metadata.groups -- i.e., a
                            # static group
                            self.logger.warning(
                                "Refusing to clobber predefined group %s" %
                                groupname)
                        else:
                            self.metadata.groups[groupname] = group
                            self._dynamic_groups[groupname] = conn.name
                        groupnames.append(groupname)
                    else:
                        groupnames.append(group)

                self.metadata.merge_additional_groups(imd, groupnames)
            for conn in connectors:
                data = conn.get_additional_data(imd)
                self.metadata.merge_additional_data(imd, conn.name, data)
            imd.query.by_name = self.build_metadata
            if self.metadata_cache_mode in ['cautious', 'aggressive']:
                self.metadata_cache[client_name] = imd
        else:
            self.logger.debug("Using cached metadata object for %s" %
                              client_name)
        return imd

    def process_statistics(self, client_name, statistics):
        """ Process uploaded statistics for client.

        :param client_name: The name of the client to process
                            statistics for
        :type client_name: string
        :param statistics: The statistics document to process
        :type statistics: lxml.etree._Element
        """
        self.logger.debug("Processing statistics for %s" % client_name)
        meta = self.build_metadata(client_name)
        state = statistics.find(".//Statistics")
        if state.get('version') >= '2.0':
            for plugin in self.plugins_by_type(Statistics):
                try:
                    plugin.process_statistics(meta, statistics)
                except:
                    self.logger.error("Plugin %s failed to process stats from "
                                      "%s" % (plugin.name, meta.hostname),
                                      exc_info=1)

        self.logger.info("Client %s reported state %s" % (client_name,
                                                          state.get('state')))
        self.client_run_hook("end_statistics", meta)

    @track_statistics()
    def resolve_client(self, address, cleanup_cache=False, metadata=True):
        """ Given a client address, get the client hostname and
        optionally metadata.

        :param address: The address pair of the client to get the
                        canonical hostname for.
        :type address: tuple of (<ip address>, <port>)
        :param cleanup_cache: Tell the
                              :class:`Bcfg2.Server.Plugin.interfaces.Metadata`
                              plugin in :attr:`metadata` to clean up
                              any client or session cache it might
                              keep
        :type cleanup_cache: bool
        :param metadata: Build a
                         :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata`
                         object for this client as well.  This is
                         offered for convenience.
        :type metadata: bool
        :returns: tuple - If ``metadata`` is False, returns
                  ``(<canonical hostname>, None)``; if ``metadata`` is
                  True, returns ``(<canonical hostname>, <client
                  metadata object>)``
        """
        try:
            client = self.metadata.resolve_client(address,
                                                  cleanup_cache=cleanup_cache)
            if metadata:
                meta = self.build_metadata(client)
            else:
                meta = None
        except MetadataConsistencyError:
            err = sys.exc_info()[1]
            self.critical_error("Client metadata resolution error for %s: %s" %
                                (address[0], err))
        except MetadataRuntimeError:
            err = sys.exc_info()[1]
            self.critical_error('Metadata system runtime failure for %s: %s' %
                                (address[0], err))
        return (client, meta)

    def critical_error(self, message):
        """ Log an error with its traceback and return an XML-RPC fault
        to the client.

        :param message: The message to log and return to the client
        :type message: string
        :raises: :exc:`xmlrpclib.Fault`
        """
        self.logger.error(message, exc_info=1)
        raise xmlrpclib.Fault(xmlrpclib.APPLICATION_ERROR,
                              "Critical failure: %s" % message)

    def _get_rmi_objects(self):
        """ Get a dict (name: object) of all objects that may have RMI
        calls.  Currently, that includes all plugins and the FAM. """
        rv = {self.fam.__class__.__name__: self.fam}
        rv.update(self.plugins)
        return rv

    def _get_rmi(self):
        """ Get a list of RMI calls exposed by plugins """
        rmi = dict()
        for pname, pinst in self._get_rmi_objects().items():
            for mname in pinst.__rmi__:
                rmi["%s.%s" % (pname, mname)] = getattr(pinst, mname)
        return rmi

    def _resolve_exposed_method(self, method_name):
        """ Resolve a method name to the callable that implements that
        method.

        :param method_name: Name of the method to resolve
        :type method_name: string
        :returns: callable
        """
        try:
            func = getattr(self, method_name)
        except AttributeError:
            raise NoExposedMethod(method_name)
        if not getattr(func, "exposed", False):
            raise NoExposedMethod(method_name)
        return func

    # XMLRPC handlers start here

    @exposed
    def listMethods(self, address):  # pylint: disable=W0613
        """ List all exposed methods, including plugin RMI.

        :param address: Client (address, port) pair
        :type address: tuple
        :returns: list of exposed method names
        """
        methods = [name
                   for name, func in inspect.getmembers(self, callable)
                   if (getattr(func, "exposed", False) and
                       self.check_acls(address, name))]
        methods.extend([m for m in self._get_rmi().keys()
                        if self.check_acls(address, m)])
        return methods

    @exposed
    def methodHelp(self, address, method_name):  # pylint: disable=W0613
        """ Get help from the docstring of an exposed method

        :param address: Client (address, port) pair
        :type address: tuple
        :param method_name: The name of the method to get help on
        :type method_name: string
        :returns: string - The help message from the method's docstring
        """
        try:
            func = self._resolve_exposed_method(method_name)
        except NoExposedMethod:
            return ""
        return func.__doc__

    @exposed
    @track_statistics()
    @close_db_connection
    def DeclareVersion(self, address, version):
        """ Declare the client version.

        :param address: Client (address, port) pair
        :type address: tuple
        :param version: The client's declared version
        :type version: string
        :returns: bool - True on success
        :raises: :exc:`xmlrpclib.Fault`
        """
        client = self.resolve_client(address, metadata=False)[0]
        self.logger.debug("%s is running Bcfg2 client version %s" % (client,
                                                                     version))
        try:
            self.metadata.set_version(client, version)
        except (MetadataConsistencyError, MetadataRuntimeError):
            err = sys.exc_info()[1]
            self.critical_error("Unable to set version for %s: %s" %
                                (client, err))
        return True

    @exposed
    @close_db_connection
    def GetProbes(self, address):
        """ Fetch probes for the client.

        :param address: Client (address, port) pair
        :type address: tuple
        :returns: lxml.etree._Element - XML tree describing probes for
                  this client
        :raises: :exc:`xmlrpclib.Fault`
        """
        resp = lxml.etree.Element('probes')
        client, metadata = self.resolve_client(address, cleanup_cache=True)
        self.logger.debug("Getting probes for %s" % client)
        try:
            for plugin in self.plugins_by_type(Probing):
                for probe in plugin.GetProbes(metadata):
                    resp.append(probe)
            self.logger.debug("Sending probe list to %s" % client)
            return lxml.etree.tostring(resp,
                                       xml_declaration=False).decode('UTF-8')
        except:
            err = sys.exc_info()[1]
            self.critical_error("Error determining probes for %s: %s" %
                                (client, err))

    @exposed
    @close_db_connection
    def RecvProbeData(self, address, probedata):
        """ Receive probe data from clients.

        :param address: Client (address, port) pair
        :type address: tuple
        :returns: bool - True on success
        :raises: :exc:`xmlrpclib.Fault`
        """
        client, metadata = self.resolve_client(address)
        self.logger.debug("Receiving probe data from %s" % client)
        if self.metadata_cache_mode == 'cautious':
            # clear the metadata cache right after building the
            # metadata object; that way the cache is cleared for any
            # new probe data that's received, but the metadata object
            # that's created for RecvProbeData doesn't get cached.
            # I.e., the next metadata object that's built, after probe
            # data is processed, is cached.
            self.metadata_cache.expire(client)
        try:
            xpdata = lxml.etree.XML(probedata.encode('utf-8'),
                                    parser=Bcfg2.Server.XMLParser)
        except lxml.etree.XMLSyntaxError:
            err = sys.exc_info()[1]
            self.critical_error("Failed to parse probe data from client %s: %s"
                                % (client, err))

        sources = []
        for data in xpdata:
            source = data.get('source')
            if source not in sources:
                if source not in self.plugins:
                    self.logger.warning("Failed to locate plugin %s" % source)
                    continue
                sources.append(source)

        for source in sources:
            datalist = [data for data in xpdata
                        if data.get('source') == source]
            try:
                self.plugins[source].ReceiveData(metadata, datalist)
            except:
                err = sys.exc_info()[1]
                self.critical_error("Failed to process probe data from client "
                                    "%s: %s" % (client, err))
        return True

    @exposed
    @close_db_connection
    def AssertProfile(self, address, profile):
        """ Set profile for a client.

        :param address: Client (address, port) pair
        :type address: tuple
        :returns: bool - True on success
        :raises: :exc:`xmlrpclib.Fault`
        """
        client = self.resolve_client(address, metadata=False)[0]
        self.logger.debug("%s sets its profile to %s" % (client, profile))
        try:
            self.metadata.set_profile(client, profile, address)
        except (MetadataConsistencyError, MetadataRuntimeError):
            err = sys.exc_info()[1]
            self.critical_error("Unable to assert profile for %s: %s" %
                                (client, err))
        return True

    @exposed
    @close_db_connection
    def GetConfig(self, address):
        """ Build config for a client by calling
        :func:`BuildConfiguration`.

        :param address: Client (address, port) pair
        :type address: tuple
        :returns: lxml.etree._Element - The full configuration
                  document for the client
        :raises: :exc:`xmlrpclib.Fault`
        """
        client = self.resolve_client(address)[0]
        try:
            config = self.BuildConfiguration(client)
            return lxml.etree.tostring(config,
                                       xml_declaration=False).decode('UTF-8')
        except MetadataConsistencyError:
            self.critical_error("Metadata consistency failure for %s" % client)

    @exposed
    @close_db_connection
    def RecvStats(self, address, stats):
        """ Act on statistics upload with :func:`process_statistics`.

        :param address: Client (address, port) pair
        :type address: tuple
        :returns: bool - True on success
        :raises: :exc:`xmlrpclib.Fault`
        """
        client = self.resolve_client(address)[0]
        sdata = lxml.etree.XML(stats.encode('utf-8'),
                               parser=Bcfg2.Server.XMLParser)
        self.process_statistics(client, sdata)
        return True

    @exposed
    @close_db_connection
    def GetDecisionList(self, address, mode):
        """ Get the decision list for the client with :func:`GetDecisions`.

        :param address: Client (address, port) pair
        :type address: tuple
        :returns: list of decision tuples
        :raises: :exc:`xmlrpclib.Fault`
        """
        metadata = self.resolve_client(address)[1]
        return self.GetDecisions(metadata, mode)

    @property
    def database_available(self):
        """ True if the database is configured and available, False
        otherwise. """
        return self._database_available

    @exposed
    def get_statistics(self, _):
        """ Get current statistics about component execution from
        :attr:`Bcfg2.Server.Statistics.stats`.

        :returns: dict - The statistics data as returned by
                  :func:`Bcfg2.Server.Statistics.Statistics.display` """
        return Bcfg2.Server.Statistics.stats.display()

    @exposed
    def toggle_debug(self, address):
        """ Toggle debug status of the FAM and all plugins

        :param address: Client (address, port) pair
        :type address: tuple
        :returns: bool - The new debug state of the FAM
        """
        return self.set_debug(address, not self.debug_flag)

    @exposed
    def toggle_core_debug(self, address):
        """ Toggle debug status of the server core

        :param address: Client (address, hostname) pair
        :type address: tuple
        :returns: bool - The new debug state of the FAM
        """
        return self.set_core_debug(address, not self.debug_flag)

    @exposed
    def toggle_fam_debug(self, address):
        """ Toggle debug status of the FAM

        :returns: bool - The new debug state of the FAM
        """
        self.logger.warning("Deprecated method set_fam_debug called by %s" %
                            address[0])
        return "This method is deprecated and will be removed in a future " + \
            "release\n%s" % self.fam.toggle_debug()

    @exposed
    def set_debug(self, address, debug):
        """ Explicitly set debug status of the FAM and all plugins

        :param address: Client (address, hostname) pair
        :type address: tuple
        :param debug: The new debug status.  This can either be a
                      boolean, or a string describing the state (e.g.,
                      "true" or "false"; case-insensitive)
        :type debug: bool or string
        :returns: bool - The new debug state
        """
        if debug not in [True, False]:
            debug = debug.lower() == "true"
        for plugin in self.plugins.values():
            plugin.set_debug(debug)
        rv = self.set_core_debug(address, debug)
        return self.fam.set_debug(debug) and rv

    @exposed
    def set_core_debug(self, _, debug):
        """ Explicity set debug status of the server core

        :param debug: The new debug status.  This can either be a
                      boolean, or a string describing the state (e.g.,
                      "true" or "false"; case-insensitive)
        :type debug: bool or string
        :returns: bool - The new debug state of the FAM
        """
        if debug not in [True, False]:
            debug = debug.lower() == "true"
        self.debug_flag = debug
        self.logger.info("Core: debug = %s" % debug)
        levels = self._loglevels[self.debug_flag]
        for handler in logging.root.handlers:
            try:
                level = levels.get(handler.name, levels['default'])
                self.logger.debug("Setting %s log handler to %s" %
                                  (handler.name, logging.getLevelName(level)))
            except AttributeError:
                level = levels['default']
                self.logger.debug("Setting unknown log handler %s to %s" %
                                  (handler, logging.getLevelName(level)))
            handler.setLevel(level)
        return self.debug_flag

    @exposed
    def set_fam_debug(self, address, debug):
        """ Explicitly set debug status of the FAM

        :param debug: The new debug status of the FAM.  This can
                      either be a boolean, or a string describing the
                      state (e.g., "true" or "false";
                      case-insensitive)
        :type debug: bool or string
        :returns: bool - The new debug state of the FAM
        """
        if debug not in [True, False]:
            debug = debug.lower() == "true"
        self.logger.warning("Deprecated method set_fam_debug called by %s" %
                            address[0])
        return "This method is deprecated and will be removed in a future " + \
            "release\n%s" % self.fam.set_debug(debug)

    @exposed
    def expire_metadata_cache(self, _, hostnames=None):
        """ Expire the metadata cache for one or all clients

        :param hostnames: A list of hostnames to expire the metadata
                          cache for or None. If None the cache of
                          all clients will be expired.
        :type hostnames: None or list of strings
        """
        if hostnames is not None:
            for hostname in hostnames:
                self.metadata_cache.expire(hostname)
        else:
            self.metadata_cache.expire()


class NetworkCore(Core):
    """ A server core that actually listens on the network, can be
    daemonized, etc."""
    options = Core.options + [
        Bcfg2.Options.Common.daemon, Bcfg2.Options.Common.syslog,
        Bcfg2.Options.Common.location, Bcfg2.Options.Common.ssl_ca,
        Bcfg2.Options.Common.protocol,
        Bcfg2.Options.PathOption(
            '--ssl-key', cf=('communication', 'key'), dest="key",
            help='Path to SSL key',
            default="/etc/pki/tls/private/bcfg2.key"),
        Bcfg2.Options.PathOption(
            cf=('communication', 'certificate'), dest="cert",
            help='Path to SSL certificate',
            default="/etc/pki/tls/certs/bcfg2.crt"),
        Bcfg2.Options.BooleanOption(
            '--listen-all', cf=('server', 'listen_all'), default=False,
            help="Listen on all interfaces"),
        Bcfg2.Options.Option(
            cf=('server', 'umask'), default='0077', help='Server umask',
            type=Bcfg2.Options.Types.octal),
        Bcfg2.Options.Option(
            cf=('server', 'user'), default=0, dest='daemon_uid',
            type=Bcfg2.Options.Types.username,
            help="User to run the server daemon as"),
        Bcfg2.Options.Option(
            cf=('server', 'group'), default=0, dest='daemon_gid',
            type=Bcfg2.Options.Types.groupname,
            help="Group to run the server daemon as")]

    def __init__(self):
        Core.__init__(self)

        #: The CA that signed the server cert
        self.ca = Bcfg2.Options.setup.ca

        if self._database_available:
            db_settings = django.conf.settings.DATABASES['default']
            if (Bcfg2.Options.setup.daemon and
                    Bcfg2.Options.setup.daemon_uid and
                    db_settings['ENGINE'].endswith(".sqlite3") and
                    not os.path.exists(db_settings['NAME'])):
                # syncdb will create the sqlite database, and we're
                # going to daemonize, dropping privs to a non-root
                # user, so we need to chown the database after
                # creating it
                try:
                    os.chown(db_settings['NAME'],
                             Bcfg2.Options.setup.daemon_uid,
                             Bcfg2.Options.setup.daemon_gid)
                except OSError:
                    err = sys.exc_info()[1]
                    self.logger.error("Failed to set ownership of database "
                                      "at %s: %s" % (db_settings['NAME'], err))
    __init__.__doc__ = Core.__init__.__doc__.split(".. -----")[0] + \
        "\n.. automethod:: _daemonize\n"

    def __str__(self):
        if hasattr(Bcfg2.Options.setup, "server"):
            return "%s(%s)" % (self.__class__.__name__,
                               Bcfg2.Options.setup.server)
        else:
            return Core.__str__(self)

    def run(self):
        """ Run the server core.  This calls :func:`_daemonize` before
        calling :func:`Bcfg2.Server.Core.Core.run` to run the server
        core. """
        if Bcfg2.Options.setup.daemon:
            # if we're dropping privs, then the pidfile is likely
            # /var/run/bcfg2-server/bcfg2-server.pid or similar.
            # since some OSes clean directories out of /var/run on
            # reboot, we need to ensure that the directory containing
            # the pidfile exists and has the appropriate permissions
            piddir = os.path.dirname(Bcfg2.Options.setup.daemon)
            if not os.path.exists(piddir):
                os.makedirs(piddir)
                os.chown(piddir,
                         Bcfg2.Options.setup.daemon_uid,
                         Bcfg2.Options.setup.daemon_gid)
                os.chmod(piddir, 493)  # 0775
            if not self._daemonize():
                return False

            # rewrite $HOME. pulp stores its auth creds in ~/.pulp, so
            # this is necessary to make that work when privileges are
            # dropped
            os.environ['HOME'] = \
                pwd.getpwuid(Bcfg2.Options.setup.daemon_uid)[5]
        else:
            os.umask(int(Bcfg2.Options.setup.umask, 8))

        Core.run(self)

    def authenticate(self, cert, user, password, address):
        """ Authenticate a client connection with
        :func:`Bcfg2.Server.Plugin.interfaces.Metadata.AuthenticateConnection`.

        :param cert: an x509 certificate
        :type cert: dict
        :param user: The username of the user trying to authenticate
        :type user: string
        :param password: The password supplied by the client
        :type password: string
        :param address: An address pair of ``(<ip address>, <port>)``
        :type address: tuple
        :return: bool - True if the authenticate succeeds, False otherwise
        """
        if self.ca:
            acert = cert
        else:
            # No ca, so no cert validation can be done
            acert = None
        return self.metadata.AuthenticateConnection(acert, user, password,
                                                    address)

    def _daemonize(self):
        """ Daemonize the server and write the pidfile.  This must be
        overridden by a core implementation. """
        raise NotImplementedError

    def _drop_privileges(self):
        """ This is called if not daemonized and running as root to
        drop the privileges to the configured daemon_uid and daemon_gid.
        """
        daemon.daemon.change_process_owner(
            Bcfg2.Options.setup.daemon_uid,
            Bcfg2.Options.setup.daemon_gid)
        self.logger.debug("Dropped privileges to %s:%s." %
                          (os.getuid(), os.getgid()))
