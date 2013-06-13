""" Interface definitions for Bcfg2 server plugins """

import os
import sys
import copy
import threading
import lxml.etree
import Bcfg2.Server
from Bcfg2.Compat import Queue, Empty, Full, cPickle
from Bcfg2.Server.Plugin.base import Plugin
from Bcfg2.Server.Plugin.exceptions import PluginInitError, \
    MetadataRuntimeError, MetadataConsistencyError


class Generator(object):
    """ Generator plugins contribute to literal client configurations.
    That is, they generate entry contents.

    An entry is generated in one of two ways:

    #. The Bcfg2 core looks in the ``Entries`` dict attribute of the
       plugin object.  ``Entries`` is expected to be a dict whose keys
       are entry tags (e.g., ``"Path"``, ``"Service"``, etc.) and
       whose values are dicts; those dicts should map the ``name``
       attribute of an entry to a callable that will be called to
       generate the content.  The callable will receive two arguments:
       the abstract entry (as an lxml.etree._Element object), and the
       client metadata object the entry is being generated for.

    #. If the entry is not listed in ``Entries``, the Bcfg2 core calls
       :func:`HandlesEntry`; if that returns True, then it calls
       :func:`HandleEntry`.
    """

    def HandlesEntry(self, entry, metadata):  # pylint: disable=W0613
        """ HandlesEntry is the slow path method for routing
        configuration binding requests.  It is called if the
        ``Entries`` dict does not contain a method for binding the
        entry.

        :param entry: The entry to bind
        :type entry: lxml.etree._Element
        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: bool - Whether or not this plugin can handle the entry
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginExecutionError`
        """
        return False

    def HandleEntry(self, entry, metadata):  # pylint: disable=W0613
        """ HandleEntry is the slow path method for binding
        configuration binding requests.  It is called if the
        ``Entries`` dict does not contain a method for binding the
        entry, and :func:`HandlesEntry`
        returns True.

        :param entry: The entry to bind
        :type entry: lxml.etree._Element
        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: lxml.etree._Element - The fully bound entry
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginExecutionError`
        """
        return entry


class Structure(object):
    """ Structure Plugins contribute to abstract client
    configurations.  That is, they produce lists of entries that will
    be generated for a client. """

    def BuildStructures(self, metadata):
        """ Build a list of lxml.etree._Element objects that will be
        added to the top-level ``<Configuration>`` tag of the client
        configuration.  Consequently, each object in the list returned
        by ``BuildStructures()`` must consist of a container tag
        (e.g., ``<Bundle>`` or ``<Independent>``) which contains the
        entry tags.  It must not return a list of entry tags.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: list of lxml.etree._Element objects
        """
        raise NotImplementedError


class Metadata(object):
    """ Metadata plugins handle initial metadata construction,
    accumulating data from :class:`Connector` plugins, and producing
    :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata` objects. """

    def viz(self, hosts, bundles, key, only_client, colors):
        """ Return a string containing a graphviz document that maps
        out the Metadata for :ref:`bcfg2-admin viz <server-admin-viz>`

        :param hosts: Include hosts in the graph
        :type hosts: bool
        :param bundles: Include bundles in the graph
        :type bundles: bool
        :param key: Include a key in the graph
        :type key: bool
        :param only_client: Only include data for the specified client
        :type only_client: string
        :param colors: Use the specified graphviz colors
        :type colors: list of strings
        :return: string
        """
        raise NotImplementedError

    def set_version(self, client, version):
        """ Set the version for the named client to the specified
        version string.

        :param client: Hostname of the client
        :type client: string
        :param profile: Client Bcfg2 version
        :type profile: string
        :return: None
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.MetadataRuntimeError`,
                 :class:`Bcfg2.Server.Plugin.exceptions.MetadataConsistencyError`
        """
        pass

    def set_profile(self, client, profile, address):
        """ Set the profile for the named client to the named profile
        group.

        :param client: Hostname of the client
        :type client: string
        :param profile: Name of the profile group
        :type profile: string
        :param address: Address pair of ``(<ip address>, <hostname>)``
        :type address: tuple
        :return: None
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.MetadataRuntimeError`,
                 :class:`Bcfg2.Server.Plugin.exceptions.MetadataConsistencyError`
        """
        pass

    # pylint: disable=W0613
    def resolve_client(self, address, cleanup_cache=False):
        """ Resolve the canonical name of this client.  If this method
        is not implemented, the hostname claimed by the client is
        used.  (This may be a security risk; it's highly recommended
        that you implement ``resolve_client`` if you are writing a
        Metadata plugin.)

        :param address: Address pair of ``(<ip address>, <hostname>)``
        :type address: tuple
        :param cleanup_cache: Whether or not to remove expire the
                              entire client hostname resolution class
        :type cleanup_cache: bool
        :return: string - canonical client hostname
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.MetadataRuntimeError`,
                 :class:`Bcfg2.Server.Plugin.exceptions.MetadataConsistencyError`
        """
        return address[1]
    # pylint: enable=W0613

    def AuthenticateConnection(self, cert, user, password, address):
        """ Authenticate the given client.

        :param cert: an x509 certificate
        :type cert: dict
        :param user: The username of the user trying to authenticate
        :type user: string
        :param password: The password supplied by the client
        :type password: string
        :param addresspair: An address pair of ``(<ip address>,
                            <hostname>)``
        :type addresspair: tuple
        :return: bool - True if the authenticate succeeds, False otherwise
        """
        raise NotImplementedError

    def get_initial_metadata(self, client_name):
        """ Return a
        :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata` object
        that fully describes everything the Metadata plugin knows
        about the named client.

        :param client_name: The hostname of the client
        :type client_name: string
        :return: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        raise NotImplementedError

    def merge_additional_data(self, imd, source, data):
        """ Add arbitrary data from a
        :class:`Connector` plugin to the given
        metadata object.

        :param imd: An initial metadata object
        :type imd: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param source: The name of the plugin providing this data
        :type source: string
        :param data: The data to add
        :type data: any
        :return: None
        """
        raise NotImplementedError

    def merge_additional_groups(self, imd, groups):
        """ Add groups from a
        :class:`Connector` plugin to the given
        metadata object.

        :param imd: An initial metadata object
        :type imd: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param groups: The groups to add
        :type groups: list of strings
        :return: None
        """
        raise NotImplementedError


class Connector(object):
    """ Connector plugins augment client metadata instances with
    additional data, additional groups, or both. """

    def get_additional_groups(self, metadata):  # pylint: disable=W0613
        """ Return a list of additional groups for the given client.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: list of strings
        """
        return list()

    def get_additional_data(self, metadata):  # pylint: disable=W0613
        """ Return arbitrary additional data for the given
        ClientMetadata object.  By convention this is usually a dict
        object, but doesn't need to be.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: dict
        """
        return dict()


class Probing(object):
    """ Probing plugins can collect data from clients and process it.
    """

    def GetProbes(self, metadata):
        """ Return a list of probes for the given client.  Each probe
        should be an lxml.etree._Element object that adheres to
        the following specification.  Each probe must the following
        attributes:

        * ``name``: The unique name of the probe.
        * ``source``: The origin of the probe; probably the name of
          the plugin that supplies the probe.
        * ``interpreter``: The command that will be run on the client
          to interpret the probe script.  Compiled (i.e.,
          non-interpreted) probes are not supported.

        The text of the XML tag should be the contents of the probe,
        i.e., the code that will be run on the client.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: list of lxml.etree._Element objects
        """
        raise NotImplementedError

    def ReceiveData(self, metadata, datalist):
        """ Process data returned from the probes for the given
        client.  ``datalist`` is a list of lxml.etree._Element
        objects, each of which is a single tag; the ``name`` attribute
        holds the unique name of the probe that was run, and the text
        contents of the tag hold the results of the probe.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param datalist: The probe data
        :type datalist: list of lxml.etree._Element objects
        :return: None
        """
        raise NotImplementedError


class Statistics(Plugin):
    """ Statistics plugins handle statistics for clients.  In general,
    you should avoid using Statistics and use
    :class:`ThreadedStatistics` instead."""

    create = False

    def process_statistics(self, client, xdata):
        """ Process the given XML statistics data for the specified
        client.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param data: The statistics data
        :type data: lxml.etree._Element
        :return: None
        """
        raise NotImplementedError


class Threaded(object):
    """ Threaded plugins use threads in any way.  The thread must be
    started after daemonization, so this class implements a single
    method, :func:`start_threads`, that can be used to start threads
    after daemonization of the server core. """

    def start_threads(self):
        """ Start this plugin's threads after daemonization.

        :return: None
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginInitError`
        """
        raise NotImplementedError


class ThreadedStatistics(Statistics, Threaded, threading.Thread):
    """ ThreadedStatistics plugins process client statistics in a
    separate thread. """

    def __init__(self, core, datastore):
        Statistics.__init__(self, core, datastore)
        Threaded.__init__(self)
        threading.Thread.__init__(self)
        # Event from the core signaling an exit
        self.terminate = core.terminate
        self.work_queue = Queue(100000)
        self.pending_file = os.path.join(datastore, "etc",
                                         "%s.pending" % self.name)
        self.daemon = False

    def start_threads(self):
        self.start()

    def _save(self):
        """Save any pending data to a file."""
        pending_data = []
        try:
            while not self.work_queue.empty():
                (metadata, xdata) = self.work_queue.get_nowait()
                data = \
                    lxml.etree.tostring(xdata,
                                        xml_declaration=False).decode("UTF-8")
                pending_data.append((metadata.hostname, data))
        except Empty:
            pass

        try:
            savefile = open(self.pending_file, 'w')
            cPickle.dump(pending_data, savefile)
            savefile.close()
            self.logger.info("Saved pending %s data" % self.name)
        except (IOError, TypeError):
            err = sys.exc_info()[1]
            self.logger.warning("Failed to save pending data: %s" % err)

    def _load(self):
        """Load any pending data from a file."""
        if not os.path.exists(self.pending_file):
            return True
        pending_data = []
        try:
            savefile = open(self.pending_file, 'r')
            pending_data = cPickle.load(savefile)
            savefile.close()
        except (IOError, cPickle.UnpicklingError):
            err = sys.exc_info()[1]
            self.logger.warning("Failed to load pending data: %s" % err)
            return False
        for (pmetadata, pdata) in pending_data:
            # check that shutdown wasnt called early
            if self.terminate.isSet():
                return False

            try:
                while True:
                    try:
                        metadata = self.core.build_metadata(pmetadata)
                        break
                    except MetadataRuntimeError:
                        pass

                    self.terminate.wait(5)
                    if self.terminate.isSet():
                        return False

                self.work_queue.put_nowait(
                    (metadata,
                     lxml.etree.XML(pdata, parser=Bcfg2.Server.XMLParser)))
            except Full:
                self.logger.warning("Queue.Full: Failed to load queue data")
                break
            except lxml.etree.LxmlError:
                lxml_error = sys.exc_info()[1]
                self.logger.error("Unable to load saved interaction: %s" %
                                  lxml_error)
            except MetadataConsistencyError:
                self.logger.error("Unable to load metadata for save "
                                  "interaction: %s" % pmetadata)
        try:
            os.unlink(self.pending_file)
        except OSError:
            self.logger.error("Failed to unlink save file: %s" %
                              self.pending_file)
        self.logger.info("Loaded pending %s data" % self.name)
        return True

    def run(self):
        if not self._load():
            return
        while not self.terminate.isSet() and self.work_queue is not None:
            try:
                (client, xdata) = self.work_queue.get(block=True, timeout=2)
            except Empty:
                continue
            except:
                err = sys.exc_info()[1]
                self.logger.error("ThreadedStatistics: %s" % err)
                continue
            self.handle_statistic(client, xdata)
        if self.work_queue is not None and not self.work_queue.empty():
            self._save()

    def process_statistics(self, metadata, data):
        try:
            self.work_queue.put_nowait((metadata, copy.copy(data)))
        except Full:
            self.logger.warning("%s: Queue is full.  Dropping interactions." %
                                self.name)

    def handle_statistic(self, metadata, data):
        """ Process the given XML statistics data for the specified
        client object.  This differs from the
        :func:`Statistics.process_statistics` method only in that
        ThreadedStatistics first adds the data to a queue, and then
        processes them in a separate thread.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param data: The statistics data
        :type data: lxml.etree._Element
        :return: None
        """
        raise NotImplementedError


# pylint: disable=C0111
# Someone who understands these interfaces better needs to write docs
# for PullSource and PullTarget
class PullSource(object):
    def GetExtra(self, client):  # pylint: disable=W0613
        return []

    def GetCurrentEntry(self, client, e_type, e_name):
        raise NotImplementedError


class PullTarget(object):
    def AcceptChoices(self, entry, metadata):
        raise NotImplementedError

    def AcceptPullData(self, specific, new_entry, verbose):
        raise NotImplementedError
# pylint: enable=C0111


class Decision(object):
    """ Decision plugins produce decision lists for affecting which
    entries are actually installed on clients. """

    def GetDecisions(self, metadata, mode):
        """ Return a list of tuples of ``(<entry type>, <entry
        name>)`` to be used as the decision list for the given
        client in the specified mode.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param mode: The decision mode ("whitelist" or "blacklist")
        :type mode: string
        :return: list of tuples
        """
        raise NotImplementedError


class StructureValidator(object):
    """ StructureValidator plugins can modify the list of structures
    after it has been created but before the entries have been
    concretely bound. """

    def validate_structures(self, metadata, structures):
        """ Given a list of structures (i.e., of tags that contain
        entry tags), modify that list or the structures in it
        in-place.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param config: A list of lxml.etree._Element objects
                       describing the structures (i.e., bundles) for
                       this client.  This can be modified in place.
        :type config: list of lxml.etree._Element
        :returns: None
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.ValidationError`
        """
        raise NotImplementedError


class GoalValidator(object):
    """ GoalValidator plugins can modify the concretely-bound configuration of
    a client as a last stage before the configuration is sent to the
    client. """

    def validate_goals(self, metadata, config):
        """ Given a monolithic XML document of the full configuration,
        modify the document in-place.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param config: The full configuration for the client
        :type config: lxml.etree._Element
        :returns: None
        :raises: :class:`Bcfg2.Server.Plugin.exceptions:ValidationError`
        """
        raise NotImplementedError


class Version(Plugin):
    """ Version plugins interact with various version control systems. """

    create = False

    #: The path to the VCS metadata file or directory, relative to the
    #: base of the Bcfg2 repository.  E.g., for Subversion this would
    #: be ".svn"
    __vcs_metadata_path__ = None

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)

        if core.setup['vcs_root']:
            self.vcs_root = core.setup['vcs_root']
        else:
            self.vcs_root = datastore
        if self.__vcs_metadata_path__:
            self.vcs_path = os.path.join(self.vcs_root,
                                         self.__vcs_metadata_path__)

            if not os.path.exists(self.vcs_path):
                raise PluginInitError("%s is not present" % self.vcs_path)
        else:
            self.vcs_path = None
    __init__.__doc__ = Plugin.__init__.__doc__ + """
.. autoattribute:: __vcs_metadata_path__ """

    def get_revision(self):
        """ Return the current revision of the Bcfg2 specification.
        This will be included in the ``revision`` attribute of the
        top-level tag of the XML configuration sent to the client.

        :returns: string - the current version
        """
        raise NotImplementedError


class ClientRunHooks(object):
    """ ClientRunHooks can hook into various parts of a client run to
    perform actions at various times without needing to pretend to be
    a different plugin type. """

    def start_client_run(self, metadata):
        """ Invoked at the start of a client run, after all probe data
        has been received and decision lists have been queried (if
        applicable), but before the configuration is generated.

        :param metadata: The client metadata object
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        pass

    def end_client_run(self, metadata):
        """ Invoked at the end of a client run, immediately after
        :class:`GoalValidator` plugins have been run and just before
        the configuration is returned to the client.

        :param metadata: The client metadata object
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        pass

    def end_statistics(self, metadata):
        """ Invoked after statistics are processed for a client.

        :param metadata: The client metadata object
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        pass
