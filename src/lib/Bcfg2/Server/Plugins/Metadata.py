""" This file stores persistent metadata for the Bcfg2 Configuration
Repository. """

import re
import os
import sys
import time
import copy
import errno
import fcntl
import socket
import logging
import lxml.etree
import Bcfg2.Server
import Bcfg2.Server.Lint
import Bcfg2.Server.Plugin
import Bcfg2.Server.FileMonitor
from Bcfg2.Utils import locked
from Bcfg2.Compat import MutableMapping, all, wraps  # pylint: disable=W0622
from Bcfg2.version import Bcfg2VersionInfo

try:
    from django.db import models
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

LOGGER = logging.getLogger(__name__)


if HAS_DJANGO:
    class MetadataClientModel(models.Model,
                              Bcfg2.Server.Plugin.PluginDatabaseModel):
        """ django model for storing clients in the database """
        hostname = models.CharField(max_length=255, primary_key=True)
        version = models.CharField(max_length=31, null=True)

    class ClientVersions(MutableMapping,
                         Bcfg2.Server.Plugin.DatabaseBacked):
        """ dict-like object to make it easier to access client bcfg2
        versions from the database """

        create = False

        def __getitem__(self, key):
            try:
                return MetadataClientModel.objects.get(hostname=key).version
            except MetadataClientModel.DoesNotExist:
                raise KeyError(key)

        @Bcfg2.Server.Plugin.DatabaseBacked.get_db_lock
        def __setitem__(self, key, value):
            client, created = \
                MetadataClientModel.objects.get_or_create(hostname=key)
            if created or client.version != value:
                client.version = value
                client.save()

        @Bcfg2.Server.Plugin.DatabaseBacked.get_db_lock
        def __delitem__(self, key):
            # UserDict didn't require __delitem__, but MutableMapping
            # does.  we don't want deleting a client version record to
            # delete the client, so we just set the version to None,
            # which is kinda like deleting it, but not really.
            try:
                client = MetadataClientModel.objects.get(hostname=key)
            except MetadataClientModel.DoesNotExist:
                raise KeyError(key)
            client.version = None
            client.save()

        def __len__(self):
            return MetadataClientModel.objects.count()

        def __iter__(self):
            for client in MetadataClientModel.objects.all():
                yield client.hostname

        def keys(self):
            """ Get keys for the mapping """
            return [c.hostname for c in MetadataClientModel.objects.all()]

        def __contains__(self, key):
            try:
                MetadataClientModel.objects.get(hostname=key)
                return True
            except MetadataClientModel.DoesNotExist:
                return False


class XMLMetadataConfig(Bcfg2.Server.Plugin.XMLFileBacked):
    """Handles xml config files and all XInclude statements"""

    def __init__(self, metadata, watch_clients, basefile):
        # we tell XMLFileBacked _not_ to add a monitor for this file,
        # because the main Metadata plugin has already added one.
        # then we immediately set should_monitor to the proper value,
        # so that XInclude'd files get properly watched
        fpath = os.path.join(metadata.data, basefile)
        toptag = os.path.splitext(basefile)[0].title()
        Bcfg2.Server.Plugin.XMLFileBacked.__init__(self, fpath,
                                                   fam=metadata.core.fam,
                                                   should_monitor=False,
                                                   create=toptag)
        self.should_monitor = watch_clients
        self.metadata = metadata
        self.basefile = basefile
        self.data = None
        self.basedata = None
        self.basedir = metadata.data
        self.logger = metadata.logger
        self.pseudo_monitor = isinstance(metadata.core.fam,
                                         Bcfg2.Server.FileMonitor.Pseudo)

    def _get_xdata(self):
        """ getter for xdata property """
        if not self.data:
            raise Bcfg2.Server.Plugin.MetadataRuntimeError("%s has no data" %
                                                           self.basefile)
        return self.data

    def _set_xdata(self, val):
        """ setter for xdata property. in practice this should only be
        used by the test suite """
        self.data = val

    xdata = property(_get_xdata, _set_xdata)

    @property
    def base_xdata(self):
        """ property to get the data of the base file (without any
        xincludes processed) """
        if not self.basedata:
            raise Bcfg2.Server.Plugin.MetadataRuntimeError("%s has no data" %
                                                           self.basefile)
        return self.basedata

    def load_xml(self):
        """Load changes from XML"""
        try:
            xdata = lxml.etree.parse(os.path.join(self.basedir, self.basefile),
                                     parser=Bcfg2.Server.XMLParser)
        except lxml.etree.XMLSyntaxError:
            self.logger.error('Failed to parse %s' % self.basefile)
            return
        self.extras = []
        self.basedata = copy.deepcopy(xdata)
        self._follow_xincludes(xdata=xdata)
        if self.extras:
            try:
                xdata.xinclude()
            except lxml.etree.XIncludeError:
                self.logger.error("Failed to process XInclude for file %s" %
                                  self.basefile)
        self.data = xdata

    def write(self):
        """Write changes to xml back to disk."""
        self.write_xml(os.path.join(self.basedir, self.basefile),
                       self.basedata)

    def write_xml(self, fname, xmltree):
        """Write changes to xml back to disk."""
        tmpfile = "%s.new" % fname
        datafile = None
        fd = None
        i = 0  # counter to avoid flooding logs with lock messages
        while datafile is None:
            try:
                fd = os.open(tmpfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                datafile = os.fdopen(fd, 'w')
            except OSError:
                err = sys.exc_info()[1]
                if err.errno == errno.EEXIST:
                    # note: not a real lock.  this is here to avoid
                    # the scenario where two threads write to the file
                    # at the same-ish time, and one writes to
                    # foo.xml.new, then the other one writes to it
                    # (losing the first thread's changes), then the
                    # first renames it, then the second tries to
                    # rename it and borks.
                    if (i % 10) == 0:
                        self.logger.info("%s is locked, waiting" % fname)
                    i += 1
                    time.sleep(0.1)
                else:
                    msg = "Failed to write %s: %s" % (tmpfile, err)
                    self.logger.error(msg)
                    raise Bcfg2.Server.Plugin.MetadataRuntimeError(msg)
        # prep data
        dataroot = xmltree.getroot()
        newcontents = lxml.etree.tostring(dataroot, xml_declaration=False,
                                          pretty_print=True).decode('UTF-8')

        while locked(fd):
            pass
        try:
            datafile.write(newcontents)
        except:
            fcntl.lockf(fd, fcntl.LOCK_UN)
            msg = "Metadata: Failed to write new xml data to %s: %s" % \
                (tmpfile, sys.exc_info()[1])
            self.logger.error(msg, exc_info=1)
            os.unlink(tmpfile)
            raise Bcfg2.Server.Plugin.MetadataRuntimeError(msg)
        datafile.close()
        # check if clients.xml is a symlink
        if os.path.islink(fname):
            fname = os.readlink(fname)

        try:
            os.rename(tmpfile, fname)
        except:  # pylint: disable=W0702
            try:
                os.unlink(tmpfile)
            except:  # pylint: disable=W0702
                pass
            msg = "Metadata: Failed to rename %s: %s" % (tmpfile,
                                                         sys.exc_info()[1])
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.MetadataRuntimeError(msg)

    def find_xml_for_xpath(self, xpath):
        """Find and load xml file containing the xpath query"""
        if self.pseudo_monitor:
            # Reload xml if we don't have a real monitor
            self.load_xml()
        cli = self.basedata.xpath(xpath)
        if len(cli) > 0:
            return {'filename': os.path.join(self.basedir, self.basefile),
                    'xmltree': self.basedata,
                    'xquery': cli}
        else:
            # Try to find the data in included files
            for included in self.extras:
                try:
                    xdata = lxml.etree.parse(included,
                                             parser=Bcfg2.Server.XMLParser)
                    cli = xdata.xpath(xpath)
                    if len(cli) > 0:
                        return {'filename': included,
                                'xmltree': xdata,
                                'xquery': cli}
                except lxml.etree.XMLSyntaxError:
                    self.logger.error('Failed to parse %s' % included)
        return {}

    def add_monitor(self, fpath):
        self.extras.append(fpath)
        if self.fam and self.should_monitor:
            self.fam.AddMonitor(fpath, self.metadata)

    def HandleEvent(self, event=None):
        """Handle fam events"""
        filename = os.path.basename(event.filename)
        if event.filename in self.extras:
            if event.code2str() == 'exists':
                return False
        elif filename != self.basefile:
            return False
        if event.code2str() == 'endExist':
            return False
        self.load_xml()
        return True


class ClientMetadata(object):
    """This object contains client metadata."""
    # pylint: disable=R0913
    def __init__(self, client, profile, groups, bundles, aliases, addresses,
                 categories, uuid, password, version, query):
        #: The client hostname (as a string)
        self.hostname = client

        #: The client profile (as a string)
        self.profile = profile

        #: The set of all bundles this client gets
        self.bundles = bundles

        #: A list of all client aliases
        self.aliases = aliases

        #: A list of all addresses this client is known by
        self.addresses = addresses

        #: A list of groups this client is a member of
        self.groups = groups

        #: A dict of categories of this client's groups.  Keys are
        #: category names, values are corresponding group names.
        self.categories = categories

        #: The UUID identifier for this client
        self.uuid = uuid

        #: The Bcfg2 password for this client
        self.password = password

        #: Connector plugins known to this client
        self.connectors = []

        #: The version of the Bcfg2 client this client is running, as
        #: a string
        self.version = version
        try:
            #: The version of the Bcfg2 client this client is running,
            #: as a :class:`Bcfg2.version.Bcfg2VersionInfo` object.
            self.version_info = Bcfg2VersionInfo(version)
        except (ValueError, AttributeError):
            self.version_info = None

        #: A :class:`Bcfg2.Server.Plugins.Metadata.MetadataQuery`
        #: object for this client.
        self.query = query
    # pylint: enable=R0913

    def inGroup(self, group):
        """Test to see if client is a member of group.

        :returns: bool """
        return group in self.groups

    def group_in_category(self, category):
        """ Return the group in the given category that the client is
        a member of, or an empty string.

        :returns: string """
        for grp in self.query.all_groups_in_category(category):
            if grp in self.groups:
                return grp
        return ''

    def __repr__(self):
        return "%s(%s, profile=%s, groups=%s)" % (self.__class__.__name__,
                                                  self.hostname,
                                                  self.profile, self.groups)


class MetadataQuery(object):
    """ This class provides query methods for the metadata of all
    clients known to the Bcfg2 server, without being able to modify
    that data.

    Note that ``*by_groups()`` and ``*by_profiles()`` behave
    differently; for a client to be included in the return value of a
    ``*by_groups()`` method, it must be a member of *all* groups
    listed in the argument; for a client to be included in the return
    value of a ``*by_profiles()`` method, it must have *any* group
    listed as its profile group. """

    def __init__(self, by_name, get_clients, by_groups, by_profiles,
                 all_groups, all_groups_in_category):
        #: Get :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata`
        #: object for the given hostname.
        #:
        #: :returns: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        self.by_name = by_name

        #: Get a list of hostnames of clients that are in all given
        #: groups.
        #:
        #: :param groups: The groups to check clients for membership in
        #: :type groups: list
        #:
        #: :returns: list of strings
        self.names_by_groups = self._warn_string(by_groups)

        #: Get a list of hostnames of clients whose profile matches
        #: any given profile group.
        #:
        #: :param profiles: The profiles to check clients for
        #:                  membership in.
        #: :type profiles: list
        #: :returns: list of strings
        self.names_by_profiles = self._warn_string(by_profiles)

        #: Get all known client hostnames.
        #:
        #: :returns: list of strings
        self.all_clients = get_clients

        #: Get all known group names.
        #:
        #: :returns: list of strings
        self.all_groups = all_groups

        #: Get the names of all groups in the given category.
        #:
        #: :param category: The category to query for groups that
        #:                  belong to it.
        #: :type category: string
        #: :returns: list of strings
        self.all_groups_in_category = all_groups_in_category

    def _warn_string(self, func):
        """ decorator to warn that a MetadataQuery function that
        expects a list has been called with a single string argument
        instead.  this is a common mistake in templates, and it
        doesn't cause errors because strings are iterables """

        # pylint: disable=C0111
        @wraps(func)
        def inner(arg):
            if isinstance(arg, str):
                LOGGER.warning("%s: %s takes a list as argument, not a string"
                               % (self.__class__.__name__, func.__name__))
            return func(arg)
        # pylint: enable=C0111

        return inner

    def by_groups(self, groups):
        """ Get a list of
        :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata` objects
        that are in all given groups.

        :param groups: The groups to check clients for membership in.
        :type groups: list
        :returns: list of Bcfg2.Server.Plugins.Metadata.ClientMetadata
                  objects
        """
        # don't need to decorate this with _warn_string because
        # names_by_groups is decorated
        return [self.by_name(name) for name in self.names_by_groups(groups)]

    def by_profiles(self, profiles):
        """ Get a list of
        :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata` objects
        that have any of the given groups as their profile.

        :param profiles: The profiles to check clients for membership
                         in.
        :type profiles: list
        :returns: list of Bcfg2.Server.Plugins.Metadata.ClientMetadata
                  objects
        """
        # don't need to decorate this with _warn_string because
        # names_by_profiles is decorated
        return [self.by_name(name)
                for name in self.names_by_profiles(profiles)]

    def all(self):
        """ Get a list of all
        :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata` objects.

        :returns: list of Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        return [self.by_name(name) for name in self.all_clients()]


class MetadataGroup(tuple):  # pylint: disable=E0012,R0924
    """ representation of a metadata group.  basically just a named tuple """

    # pylint: disable=R0913,W0613
    def __new__(cls, name, bundles=None, category=None, is_profile=False,
                is_public=False):
        if bundles is None:
            bundles = set()
        return tuple.__new__(cls, (bundles, category))
    # pylint: enable=W0613

    def __init__(self, name, bundles=None, category=None, is_profile=False,
                 is_public=False):
        if bundles is None:
            bundles = set()
        tuple.__init__(self)
        self.name = name
        self.bundles = bundles
        self.category = category
        self.is_profile = is_profile
        self.is_public = is_public
        # record which clients we've warned about category suppression
        self.warned = []
    # pylint: enable=R0913

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return "%s %s (bundles=%s, category=%s)" % \
            (self.__class__.__name__, self.name, self.bundles,
             self.category)

    def __hash__(self):
        return hash(self.name)


class Metadata(Bcfg2.Server.Plugin.Metadata,
               Bcfg2.Server.Plugin.ClientRunHooks,
               Bcfg2.Server.Plugin.DatabaseBacked):
    """This class contains data for bcfg2 server metadata."""
    __author__ = 'bcfg-dev@mcs.anl.gov'
    sort_order = 500

    def __init__(self, core, datastore, watch_clients=True):
        Bcfg2.Server.Plugin.Metadata.__init__(self)
        Bcfg2.Server.Plugin.ClientRunHooks.__init__(self)
        Bcfg2.Server.Plugin.DatabaseBacked.__init__(self, core, datastore)
        self.watch_clients = watch_clients
        self.states = dict()
        self.extra = dict()
        self.handlers = dict()
        self.groups_xml = self._handle_file("groups.xml")
        if (self._use_db and
            os.path.exists(os.path.join(self.data, "clients.xml"))):
            self.logger.warning("Metadata: database enabled but clients.xml "
                                "found, parsing in compatibility mode")
            self.clients_xml = self._handle_file("clients.xml")
        elif not self._use_db:
            self.clients_xml = self._handle_file("clients.xml")

        # mapping of clientname -> authtype
        self.auth = dict()
        # list of clients required to have non-global password
        self.secure = []
        # list of floating clients
        self.floating = []
        # mapping of clientname -> password
        self.passwords = {}
        self.addresses = {}
        self.raddresses = {}
        # mapping of clientname -> [groups]
        self.clientgroups = {}
        # list of clients
        self.clients = []
        self.aliases = {}
        self.raliases = {}
        # mapping of groupname -> MetadataGroup object
        self.groups = {}
        # mappings of predicate -> MetadataGroup object
        self.group_membership = dict()
        self.negated_groups = dict()
        # mapping of hostname -> version string
        if self._use_db:
            self.versions = ClientVersions(core, datastore)
        else:
            self.versions = dict()
        self.uuid = {}
        self.session_cache = {}
        self.default = None
        self.pdirty = False
        self.password = core.setup['password']
        self.query = MetadataQuery(core.build_metadata,
                                   lambda: list(self.clients),
                                   self.get_client_names_by_groups,
                                   self.get_client_names_by_profiles,
                                   self.get_all_group_names,
                                   self.get_all_groups_in_category)

    @classmethod
    def init_repo(cls, repo, **kwargs):
        # must use super here; inheritance works funny with class methods
        super(Metadata, cls).init_repo(repo)

        for fname in ["clients.xml", "groups.xml"]:
            aname = re.sub(r'[^A-z0-9_]', '_', fname)
            if aname in kwargs:
                open(os.path.join(repo, cls.name, fname),
                     "w").write(kwargs[aname])

    @property
    def use_database(self):
        """ Expose self._use_db publicly for use in
        :class:`Bcfg2.Server.MultiprocessingCore.ChildCore` """
        return self._use_db

    def _handle_file(self, fname):
        """ set up the necessary magic for handling a metadata file
        (clients.xml or groups.xml, e.g.) """
        if self.watch_clients:
            try:
                self.core.fam.AddMonitor(os.path.join(self.data, fname), self)
            except:
                err = sys.exc_info()[1]
                msg = "Unable to add file monitor for %s: %s" % (fname, err)
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginInitError(msg)
            self.states[fname] = False
        xmlcfg = XMLMetadataConfig(self, self.watch_clients, fname)
        aname = re.sub(r'[^A-z0-9_]', '_', os.path.basename(fname))
        self.handlers[xmlcfg.HandleEvent] = getattr(self,
                                                    "_handle_%s_event" % aname)
        self.extra[fname] = []
        return xmlcfg

    def _search_xdata(self, tag, name, tree, alias=False):
        """ Generic method to find XML data (group, client, etc.) """
        for node in tree.findall("//%s" % tag):
            if node.get("name") == name:
                return node
            elif alias:
                for child in node:
                    if (child.tag == "Alias" and
                        child.attrib["name"] == name):
                        return node
        return None

    def search_group(self, group_name, tree):
        """Find a group."""
        return self._search_xdata("Group", group_name, tree)

    def search_bundle(self, bundle_name, tree):
        """Find a bundle."""
        return self._search_xdata("Bundle", bundle_name, tree)

    def search_client(self, client_name, tree):
        """ find a client in the given XML tree """
        return self._search_xdata("Client", client_name, tree, alias=True)

    def _add_xdata(self, config, tag, name, attribs=None, alias=False):
        """ Generic method to add XML data (group, client, etc.) """
        node = self._search_xdata(tag, name, config.xdata, alias=alias)
        if node is not None:
            raise Bcfg2.Server.Plugin.MetadataConsistencyError("%s \"%s\" "
                                                               "already exists"
                                                               % (tag, name))
        element = lxml.etree.SubElement(config.base_xdata.getroot(),
                                        tag, name=name)
        if attribs:
            for key, val in list(attribs.items()):
                element.set(key, val)
        config.write()
        return element

    def add_group(self, group_name, attribs):
        """Add group to groups.xml."""
        if self._use_db:
            msg = "Metadata does not support adding groups with " + \
                "use_database enabled"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        else:
            return self._add_xdata(self.groups_xml, "Group", group_name,
                                   attribs=attribs)

    def add_bundle(self, bundle_name):
        """Add bundle to groups.xml."""
        if self._use_db:
            msg = "Metadata does not support adding bundles with " + \
                "use_database enabled"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        else:
            return self._add_xdata(self.groups_xml, "Bundle", bundle_name)

    @Bcfg2.Server.Plugin.DatabaseBacked.get_db_lock
    def add_client(self, client_name, attribs=None):
        """Add client to clients.xml."""
        if attribs is None:
            attribs = dict()
        if self._use_db:
            try:
                client = MetadataClientModel.objects.get(hostname=client_name)
            except MetadataClientModel.DoesNotExist:
                client = MetadataClientModel(hostname=client_name)
                client.save()
            self.clients = self.list_clients()
            return client
        else:
            try:
                return self._add_xdata(self.clients_xml, "Client", client_name,
                                       attribs=attribs, alias=True)
            except Bcfg2.Server.Plugin.MetadataConsistencyError:
                # already exists
                err = sys.exc_info()[1]
                self.logger.info(err)
                return self._search_xdata("Client", client_name,
                                          self.clients_xml.xdata, alias=True)

    def _update_xdata(self, config, tag, name, attribs, alias=False):
        """ Generic method to modify XML data (group, client, etc.) """
        node = self._search_xdata(tag, name, config.xdata, alias=alias)
        if node is None:
            self.logger.error("%s \"%s\" does not exist" % (tag, name))
            raise Bcfg2.Server.Plugin.MetadataConsistencyError
        xdict = config.find_xml_for_xpath('.//%s[@name="%s"]' %
                                          (tag, node.get('name')))
        if not xdict:
            self.logger.error("Unexpected error finding %s \"%s\"" %
                              (tag, name))
            raise Bcfg2.Server.Plugin.MetadataConsistencyError
        for key, val in list(attribs.items()):
            xdict['xquery'][0].set(key, val)
        config.write_xml(xdict['filename'], xdict['xmltree'])

    def update_group(self, group_name, attribs):
        """Update a groups attributes."""
        if self._use_db:
            msg = "Metadata does not support updating groups with " + \
                "use_database enabled"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        else:
            return self._update_xdata(self.groups_xml, "Group", group_name,
                                      attribs)

    def update_client(self, client_name, attribs):
        """Update a clients attributes."""
        if self._use_db:
            msg = "Metadata does not support updating clients with " + \
                "use_database enabled"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        else:
            return self._update_xdata(self.clients_xml, "Client", client_name,
                                      attribs, alias=True)

    def list_clients(self):
        """ List all clients in client database """
        if self._use_db:
            return set([c.hostname for c in MetadataClientModel.objects.all()])
        else:
            return self.clients

    def _remove_xdata(self, config, tag, name):
        """ Generic method to remove XML data (group, client, etc.) """
        node = self._search_xdata(tag, name, config.xdata)
        if node is None:
            self.logger.error("%s \"%s\" does not exist" % (tag, name))
            raise Bcfg2.Server.Plugin.MetadataConsistencyError
        xdict = config.find_xml_for_xpath('.//%s[@name="%s"]' %
                                          (tag, node.get('name')))
        if not xdict:
            self.logger.error("Unexpected error finding %s \"%s\"" %
                              (tag, name))
            raise Bcfg2.Server.Plugin.MetadataConsistencyError
        xdict['xquery'][0].getparent().remove(xdict['xquery'][0])
        config.write_xml(xdict['filename'], xdict['xmltree'])

    def remove_group(self, group_name):
        """Remove a group."""
        if self._use_db:
            msg = "Metadata does not support removing groups with " + \
                "use_database enabled"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        else:
            return self._remove_xdata(self.groups_xml, "Group", group_name)

    def remove_bundle(self, bundle_name):
        """Remove a bundle."""
        if self._use_db:
            msg = "Metadata does not support removing bundles with " + \
                "use_database enabled"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        else:
            return self._remove_xdata(self.groups_xml, "Bundle", bundle_name)

    def remove_client(self, client_name):
        """Remove a bundle."""
        if self._use_db:
            try:
                client = MetadataClientModel.objects.get(hostname=client_name)
            except MetadataClientModel.DoesNotExist:
                msg = "Client %s does not exist" % client_name
                self.logger.warning(msg)
                raise Bcfg2.Server.Plugin.MetadataConsistencyError(msg)
            client.delete()
            self.clients = self.list_clients()
        else:
            return self._remove_xdata(self.clients_xml, "Client", client_name)

    def _handle_clients_xml_event(self, _):  # pylint: disable=R0912
        """ handle all events for clients.xml and files xincluded from
        clients.xml """
        xdata = self.clients_xml.xdata
        self.clients = []
        self.clientgroups = {}
        self.aliases = {}
        self.raliases = {}
        self.secure = []
        self.floating = []
        self.addresses = {}
        self.raddresses = {}
        for client in xdata.findall('.//Client'):
            clname = client.get('name').lower()
            if 'address' in client.attrib:
                caddr = client.get('address')
                if caddr in self.addresses:
                    self.addresses[caddr].append(clname)
                else:
                    self.addresses[caddr] = [clname]
                if clname not in self.raddresses:
                    self.raddresses[clname] = set()
                self.raddresses[clname].add(caddr)
            if 'auth' in client.attrib:
                self.auth[client.get('name')] = client.get('auth')
            if 'uuid' in client.attrib:
                self.uuid[client.get('uuid')] = clname
            if client.get('secure', 'false').lower() == 'true':
                self.secure.append(clname)
            if (client.get('location', 'fixed') == 'floating' or
                client.get('floating', 'false').lower() == 'true'):
                self.floating.append(clname)
            if 'password' in client.attrib:
                self.passwords[clname] = client.get('password')
            if 'version' in client.attrib:
                self.versions[clname] = client.get('version')

            self.raliases[clname] = set()
            for alias in client.findall('Alias'):
                self.aliases.update({alias.get('name'): clname})
                self.raliases[clname].add(alias.get('name'))
                if 'address' not in alias.attrib:
                    continue
                if alias.get('address') in self.addresses:
                    self.addresses[alias.get('address')].append(clname)
                else:
                    self.addresses[alias.get('address')] = [clname]
                if clname not in self.raddresses:
                    self.raddresses[clname] = set()
                self.raddresses[clname].add(alias.get('address'))
            self.clients.append(clname)
            profile = client.get("profile")
            if self.groups:  # check if we've parsed groups.xml yet
                if profile not in self.groups:
                    self.logger.warning("Metadata: %s has nonexistent "
                                        "profile group %s" % (clname, profile))
                elif not self.groups[profile].is_profile:
                    self.logger.warning("Metadata: %s set as profile for "
                                        "%s, but is not a profile group" %
                                        (profile, clname))
            try:
                self.clientgroups[clname].append(profile)
            except KeyError:
                self.clientgroups[clname] = [profile]
        self.states['clients.xml'] = True
        if self._use_db:
            self.clients = self.list_clients()

    def _handle_groups_xml_event(self, _):  # pylint: disable=R0912
        """ re-read groups.xml on any event on it """
        self.groups = {}

        # these three functions must be separate functions in order to
        # ensure that the scope is right for the closures they return
        def get_condition(element):
            """ Return a predicate that returns True if a client meets
            the condition specified in the given Group or Client
            element """
            negate = element.get('negate', 'false').lower() == 'true'
            pname = element.get("name")
            if element.tag == 'Group':
                return lambda c, g, _: negate != (pname in g)
            elif element.tag == 'Client':
                return lambda c, g, _: negate != (pname == c)

        def get_category_condition(category, gname):
            """ get a predicate that returns False if a client is
            already a member of a group in the given category, True
            otherwise """
            def in_cat(client, groups, categories):  # pylint: disable=W0613
                """ return True if the client is already a member of a
                group in the category given in the enclosing function,
                False otherwise """
                if category in categories:
                    if (gname not in self.groups or
                        client not in self.groups[gname].warned):
                        self.logger.warning("%s: Group %s suppressed by "
                                            "category %s; %s already a member "
                                            "of %s" %
                                            (self.name, gname, category,
                                             client, categories[category]))
                        if gname in self.groups:
                            self.groups[gname].warned.append(client)
                    return False
                return True
            return in_cat

        def aggregate_conditions(conditions):
            """ aggregate all conditions on a given group declaration
            into a single predicate """
            return lambda client, groups, cats: \
                all(cond(client, groups, cats) for cond in conditions)

        # first, we get a list of all of the groups declared in the
        # file.  we do this in two stages because the old way of
        # parsing groups.xml didn't support nested groups; in the old
        # way, only Group tags under a Groups tag counted as
        # declarative.  so we parse those first, and then parse the
        # other Group tags if they haven't already been declared.
        # this lets you set options on a group (e.g., public="false")
        # at the top level and then just use the name elsewhere, which
        # is the original behavior
        for grp in self.groups_xml.xdata.xpath("//Groups/Group") + \
                self.groups_xml.xdata.xpath("//Groups/Group//Group"):
            if grp.get("name") in self.groups:
                continue
            self.groups[grp.get("name")] = \
                MetadataGroup(grp.get("name"),
                              bundles=[b.get("name")
                                       for b in grp.findall("Bundle")],
                              category=grp.get("category"),
                              is_profile=grp.get("profile", "false") == "true",
                              is_public=grp.get("public", "false") == "true")
            if grp.get('default', 'false') == 'true':
                self.default = grp.get('name')

        self.group_membership = dict()
        self.negated_groups = dict()

        # confusing loop condition; the XPath query asks for all
        # elements under a Group tag under a Groups tag; that is
        # infinitely recursive, so "all" elements really means _all_
        # elements.  We then manually filter out non-Group elements
        # since there doesn't seem to be a way to get Group elements
        # of arbitrary depth with particular ultimate ancestors in
        # XPath.  We do the same thing for Client tags.
        for el in self.groups_xml.xdata.xpath("//Groups/Group//*") + \
                self.groups_xml.xdata.xpath("//Groups/Client//*"):
            if ((el.tag != 'Group' and el.tag != 'Client') or
                el.getchildren()):
                continue

            conditions = []
            for parent in el.iterancestors():
                cond = get_condition(parent)
                if cond:
                    conditions.append(cond)

            gname = el.get("name")
            if el.get("negate", "false").lower() == "true":
                self.negated_groups[aggregate_conditions(conditions)] = \
                    self.groups[gname]
            else:
                if self.groups[gname].category:
                    conditions.append(
                        get_category_condition(self.groups[gname].category,
                                               gname))

                self.group_membership[aggregate_conditions(conditions)] = \
                    self.groups[gname]
        self.states['groups.xml'] = True

    def HandleEvent(self, event):
        """Handle update events for data files."""
        for handles, event_handler in self.handlers.items():
            if handles(event):
                # clear the entire cache when we get an event for any
                # metadata file
                self.core.metadata_cache.expire()
                event_handler(event)

        if False not in list(self.states.values()) and self.debug_flag:
            # check that all groups are real and complete. this is
            # just logged at a debug level because many groups might
            # be probed, and we don't want to warn about them.
            for client, groups in list(self.clientgroups.items()):
                for group in groups:
                    if group not in self.groups:
                        self.debug_log("Client %s set as nonexistent group %s"
                                       % (client, group))

    def set_profile(self, client, profile,  # pylint: disable=W0221
                    addresspair, require_public=True):
        """Set group parameter for provided client."""
        self.logger.info("Asserting client %s profile to %s" % (client,
                                                                profile))
        if False in list(self.states.values()):
            raise Bcfg2.Server.Plugin.MetadataRuntimeError("Metadata has not "
                                                           "been read yet")
        if profile not in self.groups:
            msg = "Profile group %s does not exist" % profile
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.MetadataConsistencyError(msg)
        group = self.groups[profile]
        if require_public and not group.is_public:
            msg = "Cannot set client %s to private group %s" % (client,
                                                                profile)
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.MetadataConsistencyError(msg)

        if client in self.clients:
            if self._use_db:
                msg = "DBMetadata does not support asserting client profiles"
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

            profiles = [g for g in self.clientgroups[client]
                        if g in self.groups and self.groups[g].is_profile]
            self.logger.info("Changing %s profile from %s to %s" %
                             (client, profiles, profile))
            self.update_client(client, dict(profile=profile))
            if client in self.clientgroups:
                for prof in profiles:
                    self.clientgroups[client].remove(prof)
                self.clientgroups[client].append(profile)
            else:
                self.clientgroups[client] = [profile]
        else:
            self.logger.info("Creating new client: %s, profile %s" %
                             (client, profile))
            if self._use_db:
                self.add_client(client)
            else:
                if addresspair in self.session_cache:
                    # we are working with a uuid'd client
                    self.add_client(self.session_cache[addresspair][1],
                                    dict(uuid=client, profile=profile,
                                         address=addresspair[0]))
                else:
                    self.add_client(client, dict(profile=profile))
                self.clients.append(client)
                self.clientgroups[client] = [profile]
        if not self._use_db:
            self.clients_xml.write()

    def set_version(self, client, version):
        """Set version for provided client."""
        if client not in self.clients:
            # this creates the client as a side effect
            self.get_initial_metadata(client)

        if client not in self.versions or version != self.versions[client]:
            self.logger.info("Setting client %s version to %s" % (client,
                                                                  version))
            if not self._use_db:
                self.update_client(client, dict(version=version))
                self.clients_xml.write()
            self.versions[client] = version

    def resolve_client(self, addresspair, cleanup_cache=False):
        """Lookup address locally or in DNS to get a hostname."""
        if addresspair in self.session_cache:
            # client _was_ cached, so there can be some expired
            # entries. we need to clean them up to avoid potentially
            # infinite memory swell
            cache_ttl = 90
            if cleanup_cache:
                # remove entries for this client's IP address with
                # _any_ port numbers - perhaps a priority queue could
                # be faster?
                curtime = time.time()
                for addrpair in list(self.session_cache.keys()):
                    if addresspair[0] == addrpair[0]:
                        (stamp, _) = self.session_cache[addrpair]
                        if curtime - stamp > cache_ttl:
                            del self.session_cache[addrpair]
            # return the cached data
            try:
                stamp = self.session_cache[addresspair][0]
                if time.time() - stamp < cache_ttl:
                    return self.session_cache[addresspair][1]
            except KeyError:
                # we cleaned all cached data for this client in cleanup_cache
                pass
        address = addresspair[0]
        if address in self.addresses:
            if len(self.addresses[address]) != 1:
                err = ("Address %s has multiple reverse assignments; a "
                       "uuid must be used" % address)
                self.logger.error(err)
                raise Bcfg2.Server.Plugin.MetadataConsistencyError(err)
            return self.addresses[address][0]
        try:
            cname = socket.getnameinfo(addresspair,
                                       socket.NI_NAMEREQD)[0].lower()
            if cname in self.aliases:
                return self.aliases[cname]
            return cname
        except socket.herror:
            err = "Address resolution error for %s: %s" % (address,
                                                           sys.exc_info()[1])
            self.logger.error(err)
            raise Bcfg2.Server.Plugin.MetadataConsistencyError(err)

    def _merge_groups(self, client, groups, categories=None):
        """ set group membership based on the contents of groups.xml
        and initial group membership of this client. Returns a tuple
        of (allgroups, categories)"""
        numgroups = -1  # force one initial pass
        if categories is None:
            categories = dict()
        while numgroups != len(groups):
            numgroups = len(groups)
            for predicate, group in self.group_membership.items():
                if group.name in groups:
                    continue
                if predicate(client, groups, categories):
                    groups.add(group.name)
                    if group.category:
                        categories[group.category] = group.name
            for predicate, group in self.negated_groups.items():
                if group.name not in groups:
                    continue
                if predicate(client, groups, categories):
                    groups.remove(group.name)
                    if group.category:
                        del categories[group.category]
        return (groups, categories)

    def get_initial_metadata(self, client):  # pylint: disable=R0914,R0912
        """Return the metadata for a given client."""
        if False in list(self.states.values()):
            raise Bcfg2.Server.Plugin.MetadataRuntimeError("Metadata has not "
                                                           "been read yet")
        client = client.lower()
        if client in self.core.metadata_cache:
            return self.core.metadata_cache[client]

        if client in self.aliases:
            client = self.aliases[client]

        groups = set()
        categories = dict()
        profile = None

        def _add_group(grpname):
            """ Add a group to the set of groups for this client.
            Handles setting categories and category suppression.
            Returns the new profile for the client (which might be
            unchanged). """
            groups.add(grpname)
            if grpname in self.groups:
                group = self.groups[grpname]
                category = group.category
                if category:
                    if category in categories:
                        self.logger.warning("%s: Group %s suppressed by "
                                            "category %s; %s already a member "
                                            "of %s" %
                                            (self.name, grpname, category,
                                             client, categories[category]))
                        return
                    categories[category] = grpname
                if not profile and group.is_profile:
                    return grpname
                else:
                    return profile

        if client not in self.clients:
            pgroup = None
            if client in self.clientgroups:
                pgroup = self.clientgroups[client][0]
            elif self.default:
                pgroup = self.default

            if pgroup:
                self.set_profile(client, pgroup, (None, None),
                                 require_public=False)
                profile = _add_group(pgroup)
            else:
                msg = "Cannot add new client %s; no default group set" % client
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.MetadataConsistencyError(msg)

        for cgroup in self.clientgroups.get(client, []):
            if cgroup in groups:
                continue
            if cgroup not in self.groups:
                self.groups[cgroup] = MetadataGroup(cgroup)
            profile = _add_group(cgroup)

        groups, categories = self._merge_groups(client, groups,
                                                categories=categories)

        if len(groups) == 0 and self.default:
            # no initial groups; add the default profile
            profile = _add_group(self.default)
            groups, categories = self._merge_groups(client, groups,
                                                    categories=categories)

        bundles = set()
        for group in groups:
            try:
                bundles.update(self.groups[group].bundles)
            except KeyError:
                self.logger.warning("%s: %s is a member of undefined group %s"
                                    % (self.name, client, group))

        aliases = self.raliases.get(client, set())
        addresses = self.raddresses.get(client, set())
        version = self.versions.get(client, None)
        if client in self.passwords:
            password = self.passwords[client]
        else:
            password = None
        uuids = [item for item, value in list(self.uuid.items())
                 if value == client]
        if uuids:
            uuid = uuids[0]
        else:
            uuid = None
        if not profile:
            # one last ditch attempt at setting the profile
            profiles = [g for g in groups
                        if g in self.groups and self.groups[g].is_profile]
            if len(profiles) >= 1:
                profile = profiles[0]

        rv = ClientMetadata(client, profile, groups, bundles, aliases,
                            addresses, categories, uuid, password, version,
                            self.query)
        if self.core.metadata_cache_mode == 'initial':
            self.core.metadata_cache[client] = rv
        return rv

    def get_all_group_names(self):
        """ return a list of all group names """
        all_groups = set()
        all_groups.update(self.groups.keys())
        all_groups.update([g.name for g in self.group_membership.values()])
        all_groups.update([g.name for g in self.negated_groups.values()])
        for grp in self.clientgroups.values():
            all_groups.update(grp)
        return all_groups

    def get_all_groups_in_category(self, category):
        """ return a list of names of groups in the given category """
        return set([g.name for g in self.groups.values()
                    if g.category == category])

    def get_client_names_by_profiles(self, profiles):
        """ return a list of names of clients in the given profile groups """
        rv = []
        for client in list(self.clients):
            mdata = self.core.build_metadata(client)
            if mdata.profile in profiles:
                rv.append(client)
        return rv

    def get_client_names_by_groups(self, groups):
        """ return a list of names of clients in the given groups """
        mdata = [self.core.build_metadata(client) for client in self.clients]
        return [md.hostname for md in mdata if md.groups.issuperset(groups)]

    def get_client_names_by_bundles(self, bundles):
        """ given a list of bundles, return a list of names of clients
        that use those bundles """
        mdata = [self.core.build_metadata(client) for client in self.clients]
        return [md.hostname for md in mdata if md.bundles.issuperset(bundles)]

    def merge_additional_groups(self, imd, groups):
        for group in groups:
            if group in imd.groups:
                continue
            if group in self.groups and self.groups[group].category:
                category = self.groups[group].category
                if self.groups[group].category in imd.categories:
                    self.logger.warning("%s: Group %s suppressed by category "
                                        "%s; %s already a member of %s" %
                                        (self.name, group, category,
                                         imd.hostname,
                                         imd.categories[category]))
                    continue
                imd.categories[category] = group
            imd.groups.add(group)

        self._merge_groups(imd.hostname, imd.groups,
                           categories=imd.categories)

        for group in imd.groups:
            if group in self.groups:
                imd.bundles.update(self.groups[group].bundles)

        if not imd.profile:
            # if the client still doesn't have a profile group after
            # initial metadata, try to find one in the additional
            # groups
            profiles = [g for g in groups
                        if g in self.groups and self.groups[g].is_profile]
            if len(profiles) >= 1:
                imd.profile = profiles[0]
            elif self.default:
                imd.profile = self.default

    def merge_additional_data(self, imd, source, data):
        if not hasattr(imd, source):
            setattr(imd, source, data)
            imd.connectors.append(source)

    def validate_client_address(self, client, addresspair):
        """Check address against client."""
        address = addresspair[0]
        if client in self.floating:
            self.debug_log("Client %s is floating" % client)
            return True
        if address in self.addresses:
            if client in self.addresses[address]:
                self.debug_log("Client %s matches address %s" %
                               (client, address))
                return True
            else:
                self.logger.error("Got request for non-float client %s from %s"
                                  % (client, address))
                return False
        resolved = self.resolve_client(addresspair)
        if resolved.lower() == client.lower():
            return True
        else:
            self.logger.error("Got request for %s from incorrect address %s" %
                              (client, address))
            self.logger.error("Resolved to %s" % resolved)
            return False

    # pylint: disable=R0911,R0912
    def AuthenticateConnection(self, cert, user, password, address):
        """This function checks auth creds."""
        if not isinstance(user, str):
            user = user.decode('utf-8')
        if cert:
            id_method = 'cert'
            certinfo = dict([x[0] for x in cert['subject']])
            # look at cert.cN
            client = certinfo['commonName']
            self.debug_log("Got cN %s; using as client name" % client)
            auth_type = self.auth.get(client,
                                      self.core.setup['authentication'])
        elif user == 'root':
            id_method = 'address'
            try:
                client = self.resolve_client(address)
            except Bcfg2.Server.Plugin.MetadataConsistencyError:
                err = sys.exc_info()[1]
                self.logger.error("Client %s failed to resolve: %s" %
                                  (address[0], err))
                return False
        else:
            id_method = 'uuid'
            # user maps to client
            if user not in self.uuid:
                client = user
                self.uuid[user] = user
            else:
                client = self.uuid[user]

        # we have the client name
        self.debug_log("Authenticating client %s" % client)

        # next we validate the address
        if (id_method != 'uuid' and
            not self.validate_client_address(client, address)):
            return False

        if id_method == 'cert' and auth_type != 'cert+password':
            # remember the cert-derived client name for this connection
            if client in self.floating:
                self.session_cache[address] = (time.time(), client)
            # we are done if cert+password not required
            return True

        if client not in self.passwords and client in self.secure:
            self.logger.error("Client %s in secure mode but has no password" %
                              address[0])
            return False

        if client not in self.secure:
            if client in self.passwords:
                plist = [self.password, self.passwords[client]]
            else:
                plist = [self.password]
            if password not in plist:
                self.logger.error("Client %s failed to use an allowed password"
                                  % address[0])
                return False
        else:
            # client in secure mode and has a client password
            if password != self.passwords[client]:
                self.logger.error("Client %s failed to use client password in "
                                  "secure mode" % address[0])
                return False
        # populate the session cache
        if user != 'root':
            self.session_cache[address] = (time.time(), client)
        return True
    # pylint: enable=R0911,R0912

    def end_statistics(self, metadata):
        """ Hook to toggle clients in bootstrap mode """
        if self.auth.get(metadata.hostname,
                         self.core.setup['authentication']) == 'bootstrap':
            self.update_client(metadata.hostname, dict(auth='cert'))

    def viz(self, hosts, bundles, key, only_client, colors):
        """Admin mode viz support."""
        clientmeta = None
        if only_client:
            clientmeta = self.core.build_metadata(only_client)

        groups = self.groups_xml.xdata.getroot()
        categories = {'default': 'grey83'}
        viz_str = []
        egroups = groups.findall("Group") + groups.findall('.//Groups/Group')
        color = 0
        for group in egroups:
            if not group.get('category') in categories:
                categories[group.get('category')] = colors[color]
                color = (color + 1) % len(colors)
            group.set('color', categories[group.get('category')])
        if None in categories:
            del categories[None]
        if hosts:
            viz_str.extend(self._viz_hosts(only_client))
        if bundles:
            viz_str.extend(self._viz_bundles(bundles, clientmeta))
        viz_str.extend(self._viz_groups(egroups, bundles, clientmeta))
        if key:
            for category in categories:
                viz_str.append('"%s" [label="%s", shape="record", '
                               'style="filled", fillcolor="%s"];' %
                               (category, category, categories[category]))
        return "\n".join("\t" + s for s in viz_str)

    def _viz_hosts(self, only_client):
        """ add hosts to the viz graph """
        def include_client(client):
            """ return True if the given client should be included in
            the graph"""
            return not only_client or client != only_client

        instances = {}
        rv = []
        for client in list(self.clients):
            if include_client(client):
                continue
            if client in self.clientgroups:
                grps = self.clientgroups[client]
            elif self.default:
                grps = [self.default]
            else:
                continue
            for group in grps:
                try:
                    instances[group].append(client)
                except KeyError:
                    instances[group] = [client]
        for group, clist in list(instances.items()):
            clist.sort()
            rv.append('"%s-instances" [ label="%s", shape="record" ];' %
                      (group, '|'.join(clist)))
            rv.append('"%s-instances" -> "group-%s";' % (group, group))
        return rv

    def _viz_bundles(self, bundles, clientmeta):
        """ add bundles to the viz graph """

        def include_bundle(bundle):
            """ return True if the given bundle should be included in
            the graph"""
            return not clientmeta or bundle in clientmeta.bundles

        bundles = list(set(bund.get('name'))
                       for bund in self.groups_xml.xdata.findall('.//Bundle')
                       if include_bundle(bund.get('name')))
        bundles.sort()
        return ['"bundle-%s" [ label="%s", shape="septagon"];' % (bundle,
                                                                  bundle)
                for bundle in bundles]

    def _viz_groups(self, egroups, bundles, clientmeta):
        """ add groups to the viz graph """

        def include_group(group):
            """ return True if the given group should be included in
            the graph """
            return not clientmeta or group in clientmeta.groups

        rv = []
        gseen = []
        for group in egroups:
            if group.get('profile', 'false') == 'true':
                style = "filled, bold"
            else:
                style = "filled"
            gseen.append(group.get('name'))
            if include_group(group.get('name')):
                rv.append('"group-%s" [label="%s", style="%s", fillcolor=%s];'
                          % (group.get('name'), group.get('name'), style,
                             group.get('color')))
                if bundles:
                    for bundle in group.findall('Bundle'):
                        rv.append('"group-%s" -> "bundle-%s";' %
                                  (group.get('name'), bundle.get('name')))
        gfmt = '"group-%s" [label="%s", style="filled", fillcolor="grey83"];'
        for group in egroups:
            for parent in group.findall('Group'):
                if (parent.get('name') not in gseen and
                    include_group(parent.get('name'))):
                    rv.append(gfmt % (parent.get('name'),
                                      parent.get('name')))
                    gseen.append(parent.get("name"))
                if include_group(group.get('name')):
                    rv.append('"group-%s" -> "group-%s";' %
                              (group.get('name'), parent.get('name')))
        return rv


class MetadataLint(Bcfg2.Server.Lint.ServerPlugin):
    """ ``bcfg2-lint`` plugin for :ref:`Metadata
    <server-plugins-grouping-metadata>`.  This checks for several things:

    * ``<Client>`` tags nested inside other ``<Client>`` tags;
    * Deprecated options (like ``location="floating"``);
    * Profiles that don't exist, or that aren't profile groups;
    * Groups or clients that are defined multiple times;
    * Multiple default groups or a default group that isn't a profile
      group.
    """

    def Run(self):
        self.nested_clients()
        self.deprecated_options()
        self.bogus_profiles()
        self.duplicate_groups()
        self.duplicate_default_groups()
        self.duplicate_clients()
        self.default_is_profile()

    @classmethod
    def Errors(cls):
        return {"nested-client-tags": "warning",
                "deprecated-clients-options": "warning",
                "nonexistent-profile-group": "error",
                "non-profile-set-as-profile": "error",
                "duplicate-group": "error",
                "duplicate-client": "error",
                "multiple-default-groups": "error",
                "default-is-not-profile": "error"}

    def deprecated_options(self):
        """ Check for the ``location='floating'`` option, which has
        been deprecated in favor of ``floating='true'``. """
        if not hasattr(self.metadata, "clients_xml"):
            # using metadata database
            return
        clientdata = self.metadata.clients_xml.xdata
        for el in clientdata.xpath("//Client"):
            loc = el.get("location")
            if loc:
                if loc == "floating":
                    floating = True
                else:
                    floating = False
                self.LintError("deprecated-clients-options",
                               "The location='%s' option is deprecated.  "
                               "Please use floating='%s' instead:\n%s" %
                               (loc, floating, self.RenderXML(el)))

    def nested_clients(self):
        """ Check for a ``<Client/>`` tag inside a ``<Client/>`` tag,
        which is either redundant or will never match. """
        groupdata = self.metadata.groups_xml.xdata
        for el in groupdata.xpath("//Client//Client"):
            self.LintError("nested-client-tags",
                           "Client %s nested within Client tag: %s" %
                           (el.get("name"), self.RenderXML(el)))

    def bogus_profiles(self):
        """ Check for clients that have profiles that are either not
        flagged as profile groups in ``groups.xml``, or don't exist. """
        if not hasattr(self.metadata, "clients_xml"):
            # using metadata database
            return
        for client in self.metadata.clients_xml.xdata.findall('.//Client'):
            profile = client.get("profile")
            if profile not in self.metadata.groups:
                self.LintError("nonexistent-profile-group",
                               "%s has nonexistent profile group %s:\n%s" %
                               (client.get("name"), profile,
                                self.RenderXML(client)))
            elif not self.metadata.groups[profile].is_profile:
                self.LintError("non-profile-set-as-profile",
                               "%s is set as profile for %s, but %s is not a "
                               "profile group:\n%s" %
                               (profile, client.get("name"), profile,
                                self.RenderXML(client)))

    def duplicate_default_groups(self):
        """ Check for multiple default groups. """
        defaults = []
        for grp in self.metadata.groups_xml.xdata.xpath("//Groups/Group") + \
                self.metadata.groups_xml.xdata.xpath("//Groups/Group//Group"):
            if grp.get("default", "false").lower() == "true":
                defaults.append(self.RenderXML(grp))
        if len(defaults) > 1:
            self.LintError("multiple-default-groups",
                           "Multiple default groups defined:\n%s" %
                           "\n".join(defaults))

    def duplicate_clients(self):
        """ Check for clients that are defined more than once. """
        if not hasattr(self.metadata, "clients_xml"):
            # using metadata database
            return
        self.duplicate_entries(
            self.metadata.clients_xml.xdata.xpath("//Client"),
            "client")

    def duplicate_groups(self):
        """ Check for groups that are defined more than once.  We
        count a group tag as a definition if it a) has profile or
        public set; or b) has any children."""
        allgroups = [
            g
            for g in self.metadata.groups_xml.xdata.xpath("//Groups/Group") +
            self.metadata.groups_xml.xdata.xpath("//Groups/Group//Group")
            if g.get("profile") or g.get("public") or g.getchildren()]
        self.duplicate_entries(allgroups, "group")

    def duplicate_entries(self, allentries, etype):
        """ Generic duplicate entry finder.

        :param allentries: A list of all entries to check for
                           duplicates.
        :type allentries: list of lxml.etree._Element
        :param etype: The entry type. This will be used to determine
                      the error name (``duplicate-<etype>``) and for
                      display to the end user.
        :type etype: string
        """
        entries = dict()
        for el in allentries:
            if el.get("name") in entries:
                entries[el.get("name")].append(self.RenderXML(el))
            else:
                entries[el.get("name")] = [self.RenderXML(el)]
        for ename, els in entries.items():
            if len(els) > 1:
                self.LintError("duplicate-%s" % etype,
                               "%s %s is defined multiple times:\n%s" %
                               (etype.title(), ename, "\n".join(els)))

    def default_is_profile(self):
        """ Ensure that the default group is a profile group. """
        if (self.metadata.default and
            not self.metadata.groups[self.metadata.default].is_profile):
            xdata = \
                self.metadata.groups_xml.xdata.xpath("//Group[@name='%s']" %
                                                     self.metadata.default)[0]
            self.LintError("default-is-not-profile",
                           "Default group is not a profile group:\n%s" %
                           self.RenderXML(xdata))
