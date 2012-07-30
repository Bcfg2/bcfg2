"""
This file stores persistent metadata for the Bcfg2 Configuration Repository.
"""

import re
import copy
import fcntl
import lxml.etree
import os
import socket
import sys
import time
import Bcfg2.Server
import Bcfg2.Server.Lint
import Bcfg2.Server.Plugin
import Bcfg2.Server.FileMonitor
from Bcfg2.version import Bcfg2VersionInfo

def locked(fd):
    """Aquire a lock on a file"""
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return True
    return False


class MetadataConsistencyError(Exception):
    """This error gets raised when metadata is internally inconsistent."""
    pass


class MetadataRuntimeError(Exception):
    """This error is raised when the metadata engine
    is called prior to reading enough data.
    """
    pass


class XMLMetadataConfig(Bcfg2.Server.Plugin.XMLFileBacked):
    """Handles xml config files and all XInclude statements"""
    def __init__(self, metadata, watch_clients, basefile):
        # we tell XMLFileBacked _not_ to add a monitor for this file,
        # because the main Metadata plugin has already added one.
        # then we immediately set should_monitor to the proper value,
        # so that XInclude'd files get properly watched
        fpath = os.path.join(metadata.data, basefile)
        Bcfg2.Server.Plugin.XMLFileBacked.__init__(self, fpath,
                                                   fam=metadata.core.fam,
                                                   should_monitor=False)
        self.should_monitor = watch_clients
        self.metadata = metadata
        self.basefile = basefile
        self.data = None
        self.basedata = None
        self.basedir = metadata.data
        self.logger = metadata.logger
        self.pseudo_monitor = isinstance(metadata.core.fam,
                                         Bcfg2.Server.FileMonitor.Pseudo)

    @property
    def xdata(self):
        if not self.data:
            raise MetadataRuntimeError("%s has no data" % self.basefile)
        return self.data

    @property
    def base_xdata(self):
        if not self.basedata:
            raise MetadataRuntimeError("%s has no data" % self.basefile)
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
        self.basedata = copy.copy(xdata)
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
        try:
            datafile = open(tmpfile, 'w')
        except IOError:
            msg = "Failed to write %s: %s" % (tmpfile, sys.exc_info()[1])
            self.logger.error(msg)
            raise MetadataRuntimeError(msg)
        # prep data
        dataroot = xmltree.getroot()
        newcontents = lxml.etree.tostring(dataroot, pretty_print=True)

        fd = datafile.fileno()
        while locked(fd) == True:
            pass
        try:
            datafile.write(newcontents)
        except:
            fcntl.lockf(fd, fcntl.LOCK_UN)
            msg = "Metadata: Failed to write new xml data to %s: %s" % \
                (tmpfile, sys.exc_info()[1])
            self.logger.error(msg, exc_info=1)
            os.unlink(tmpfile)
            raise MetadataRuntimeError(msg)
        datafile.close()
        # check if clients.xml is a symlink
        if os.path.islink(fname):
            fname = os.readlink(fname)

        try:
            os.rename(tmpfile, fname)

        except:
            msg = "Metadata: Failed to rename %s: %s" % (tmpfile,
                                                         sys.exc_info()[1])
            self.logger.error(msg)
            raise MetadataRuntimeError(msg)

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
            """Try to find the data in included files"""
            for included in self.extras:
                try:
                    xdata = lxml.etree.parse(os.path.join(self.basedir,
                                                          included),
                                             parser=Bcfg2.Server.XMLParser)
                    cli = xdata.xpath(xpath)
                    if len(cli) > 0:
                        return {'filename': os.path.join(self.basedir,
                                                         included),
                                'xmltree': xdata,
                                'xquery': cli}
                except lxml.etree.XMLSyntaxError:
                    self.logger.error('Failed to parse %s' % (included))
        return {}

    def add_monitor(self, fpath, fname):
        self.extras.append(fname)
        if self.fam and self.should_monitor:
            self.fam.AddMonitor(fpath, self.metadata)

    def HandleEvent(self, event):
        """Handle fam events"""
        filename = os.path.basename(event.filename)
        if filename in self.extras:
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
    def __init__(self, client, profile, groups, bundles, aliases, addresses,
                 categories, uuid, password, version, query):
        self.hostname = client
        self.profile = profile
        self.bundles = bundles
        self.aliases = aliases
        self.addresses = addresses
        self.groups = groups
        self.categories = categories
        self.uuid = uuid
        self.password = password
        self.connectors = []
        self.version = version
        try:
            self.version_info = Bcfg2VersionInfo(version)
        except:
            self.version_info = None
        self.query = query

    def inGroup(self, group):
        """Test to see if client is a member of group."""
        return group in self.groups

    def group_in_category(self, category):
        for grp in self.query.all_groups_in_category(category):
            if grp in self.groups:
                return grp
        return ''


class MetadataQuery(object):
    def __init__(self, by_name, get_clients, by_groups, by_profiles,
                 all_groups, all_groups_in_category):
        # resolver is set later
        self.by_name = by_name
        self.names_by_groups = by_groups
        self.names_by_profiles = by_profiles
        self.all_clients = get_clients
        self.all_groups = all_groups
        self.all_groups_in_category = all_groups_in_category

    def by_groups(self, groups):
        return [self.by_name(name) for name in self.names_by_groups(groups)]

    def by_profiles(self, profiles):
        return [self.by_name(name) for name in self.names_by_profiles(profiles)]

    def all(self):
        return [self.by_name(name) for name in self.all_clients()]


class MetadataGroup(tuple):
    def __new__(cls, name, bundles=None, category=None,
                 is_profile=False, is_public=False, is_private=False):
        if bundles is None:
            bundles = set()
        return tuple.__new__(cls, (bundles, category))

    def __init__(self, name, bundles=None, category=None,
                 is_profile=False, is_public=False, is_private=False):
        if bundles is None:
            bundles = set()
        tuple.__init__(self)
        self.name = name
        self.bundles = bundles
        self.category = category
        self.is_profile = is_profile
        self.is_public = is_public
        self.is_private = is_private

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return "%s %s (bundles=%s, category=%s)" % \
            (self.__class__.__name__, self.name, self.bundles,
             self.category)

    def __hash__(self):
        return hash(self.name)

class Metadata(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.Metadata,
               Bcfg2.Server.Plugin.Statistics):
    """This class contains data for bcfg2 server metadata."""
    __author__ = 'bcfg-dev@mcs.anl.gov'
    name = "Metadata"
    sort_order = 500
    __files__ = ["groups.xml", "clients.xml"]

    def __init__(self, core, datastore, watch_clients=True):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Metadata.__init__(self)
        Bcfg2.Server.Plugin.Statistics.__init__(self)
        self.watch_clients = watch_clients
        self.states = dict()
        self.extra = dict()
        self.handlers = []
        for fname in self.__files__:
            self._handle_file(fname)

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
        self.versions = dict()
        self.uuid = {}
        self.session_cache = {}
        self.default = None
        self.pdirty = False
        self.password = core.password
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

        for fname in cls.__files__:
            aname = re.sub(r'[^A-z0-9_]', '_', fname)
            if aname in kwargs:
                open(os.path.join(repo, cls.name, fname),
                     "w").write(kwargs[aname])

    def _handle_file(self, fname):
        if self.watch_clients:
            try:
                self.core.fam.AddMonitor(os.path.join(self.data, fname), self)
            except:
                err = sys.exc_info()[1]
                msg = "Unable to add file monitor for %s: %s" % (fname, err)
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginInitError(msg)
            self.states[fname] = False
        aname = re.sub(r'[^A-z0-9_]', '_', fname)
        xmlcfg = XMLMetadataConfig(self, self.watch_clients, fname)
        setattr(self, aname, xmlcfg)
        self.handlers.append(xmlcfg.HandleEvent)
        self.extra[fname] = []

    def _search_xdata(self, tag, name, tree, alias=False):
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
        return self._search_xdata("Client", client_name, tree, alias=True)

    def _add_xdata(self, config, tag, name, attribs=None, alias=False):
        node = self._search_xdata(tag, name, config.xdata, alias=alias)
        if node != None:
            self.logger.error("%s \"%s\" already exists" % (tag, name))
            raise MetadataConsistencyError
        element = lxml.etree.SubElement(config.base_xdata.getroot(),
                                        tag, name=name)
        if attribs:
            for key, val in list(attribs.items()):
                element.set(key, val)
        config.write()

    def add_group(self, group_name, attribs):
        """Add group to groups.xml."""
        return self._add_xdata(self.groups_xml, "Group", group_name,
                               attribs=attribs)

    def add_bundle(self, bundle_name):
        """Add bundle to groups.xml."""
        return self._add_xdata(self.groups_xml, "Bundle", bundle_name)

    def add_client(self, client_name, attribs):
        """Add client to clients.xml."""
        return self._add_xdata(self.clients_xml, "Client", client_name,
                               attribs=attribs, alias=True)

    def _update_xdata(self, config, tag, name, attribs, alias=False):
        node = self._search_xdata(tag, name, config.xdata, alias=alias)
        if node == None:
            self.logger.error("%s \"%s\" does not exist" % (tag, name))
            raise MetadataConsistencyError
        xdict = config.find_xml_for_xpath('.//%s[@name="%s"]' %
                                          (tag, node.get('name')))
        if not xdict:
            self.logger.error("Unexpected error finding %s \"%s\"" %
                              (tag, name))
            raise MetadataConsistencyError
        for key, val in list(attribs.items()):
            xdict['xquery'][0].set(key, val)
        config.write_xml(xdict['filename'], xdict['xmltree'])

    def update_group(self, group_name, attribs):
        """Update a groups attributes."""
        return self._update_xdata(self.groups_xml, "Group", group_name, attribs)

    def update_client(self, client_name, attribs):
        """Update a clients attributes."""
        return self._update_xdata(self.clients_xml, "Client", client_name,
                                  attribs, alias=True)

    def _remove_xdata(self, config, tag, name, alias=False):
        node = self._search_xdata(tag, name, config.xdata)
        if node == None:
            self.logger.error("%s \"%s\" does not exist" % (tag, name))
            raise MetadataConsistencyError
        xdict = config.find_xml_for_xpath('.//%s[@name="%s"]' %
                                          (tag, node.get('name')))
        if not xdict:
            self.logger.error("Unexpected error finding %s \"%s\"" %
                              (tag, name))
            raise MetadataConsistencyError
        xdict['xquery'][0].getparent().remove(xdict['xquery'][0])
        config.write_xml(xdict['filename'], xdict['xmltree'])

    def remove_group(self, group_name):
        """Remove a group."""
        return self._remove_xdata(self.groups_xml, "Group", group_name)

    def remove_bundle(self, bundle_name):
        """Remove a bundle."""
        return self._remove_xdata(self.groups_xml, "Bundle", bundle_name)

    def remove_client(self, client_name):
        """Remove a bundle."""
        return self._remove_xdata(self.clients_xml, "Client", client_name)

    def _handle_clients_xml_event(self, event):
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
                self.auth[client.get('name')] = client.get('auth',
                                                           'cert+password')
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
            try:
                self.clientgroups[clname].append(client.get('profile'))
            except KeyError:
                self.clientgroups[clname] = [client.get('profile')]
        self.states['clients.xml'] = True

    def _handle_groups_xml_event(self, event):
        self.groups = {}

        # get_condition and aggregate_conditions must be separate
        # functions in order to ensure that the scope is right for the
        # closures they return
        def get_condition(element):
            negate = element.get('negate', 'false').lower() == 'true'
            pname = element.get("name")
            if element.tag == 'Group':
                return lambda c, g, _: negate != (pname in g)
            elif element.tag == 'Client':
                return lambda c, g, _: negate != (pname == c)

        def aggregate_conditions(conditions):
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
                              is_public=grp.get("public", "false") == "true",
                              is_private=grp.get("public", "true") == "false")
            if grp.get('default', 'false') == 'true':
                self.default = grp.get('name')

        self.group_membership = dict()
        self.negated_groups = dict()
        self.options = dict()
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
                if self.groups[gname].category and gname in self.groups:
                    category = self.groups[gname].category

                    def in_cat(client, groups, categories):
                        if category in categories:
                            self.logger.warning("%s: Group %s suppressed by "
                                                "category %s; %s already a "
                                                "member of %s" %
                                                (self.name, gname, category,
                                                 client, categories[category]))
                            return False
                        return True
                    conditions.append(in_cat)

                self.group_membership[aggregate_conditions(conditions)] = \
                    self.groups[gname]
        self.states['groups.xml'] = True

    def HandleEvent(self, event):
        """Handle update events for data files."""
        for hdlr in self.handlers:
            aname = re.sub(r'[^A-z0-9_]', '_', os.path.basename(event.filename))
            if hdlr(event):
                try:
                    proc = getattr(self, "_handle_%s_event" % aname)
                except AttributeError:
                    proc = self._handle_default_event
                proc(event)

        if False not in list(self.states.values()) and self.debug_flag:
            # check that all groups are real and complete. this is
            # just logged at a debug level because many groups might
            # be probed, and we don't want to warn about them.
            for client, groups in list(self.clientgroups.items()):
                for group in groups:
                    if group not in self.groups:
                        self.debug_log("Client %s set as nonexistent group %s" %
                                       (client, group))
            for gname, ginfo in list(self.groups.items()):
                for group in ginfo.groups:
                    if group not in self.groups:
                        self.debug_log("Group %s set as nonexistent group %s" %
                                       (gname, group))


    def set_profile(self, client, profile, addresspair, force=False):
        """Set group parameter for provided client."""
        self.logger.info("Asserting client %s profile to %s" %
                         (client, profile))
        if False in list(self.states.values()):
            raise MetadataRuntimeError
        if not force and profile not in self.groups:
            msg = "Profile group %s does not exist" % profile
            self.logger.error(msg)
            raise MetadataConsistencyError(msg)
        group = self.groups[profile]
        if not force and not group.is_public:
            msg = "Cannot set client %s to private group %s" % (client, profile)
            self.logger.error(msg)
            raise MetadataConsistencyError(msg)
        self._set_profile(client, profile, addresspair)

    def _set_profile(self, client, profile, addresspair):
        if client in self.clients:
            profiles = [g for g in self.clientgroups[client]
                        if g in self.groups and self.groups[g].is_profile]
            self.logger.info("Changing %s profile from %s to %s" %
                             (client, profiles, profile))
            self.update_client(client, dict(profile=profile))
            if client in self.clientgroups:
                for p in profiles:
                    self.clientgroups[client].remove(p)
                self.clientgroups[client].append(profile)
            else:
                self.clientgroups[client] = [profile]
        else:
            self.logger.info("Creating new client: %s, profile %s" %
                             (client, profile))
            if addresspair in self.session_cache:
                # we are working with a uuid'd client
                self.add_client(self.session_cache[addresspair][1],
                                dict(uuid=client, profile=profile,
                                     address=addresspair[0]))
            else:
                self.add_client(client, dict(profile=profile))
            self.clients.append(client)
            self.clientgroups[client] = [profile]
        self.clients_xml.write()

    def set_version(self, client, version):
        """Set group parameter for provided client."""
        self.logger.info("Setting client %s version to %s" % (client, version))
        if client in self.clients:
            self.logger.info("Setting version on client %s to %s" %
                             (client, version))
            self.update_client(client, dict(version=version))
        else:
            msg = "Cannot set version on non-existent client %s" % client
            self.logger.error(msg)
            raise MetadataConsistencyError(msg)
        self.versions[client] = version
        self.clients_xml.write()

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
                for addrpair in self.session_cache.keys():
                     if addresspair[0] == addrpair[0]:
                         (stamp, _) = self.session_cache[addrpair]
                         if curtime - stamp > cache_ttl:
                             del self.session_cache[addrpair]
            # return the cached data
            try:
                (stamp, uuid) = self.session_cache[addresspair]
                if time.time() - stamp < cache_ttl:
                    return self.session_cache[addresspair][1]
            except KeyError:
                # we cleaned all cached data for this client in cleanup_cache
                pass
        address = addresspair[0]
        if address in self.addresses:
            if len(self.addresses[address]) != 1:
                err = "Address %s has multiple reverse assignments; a uuid must be used" % address
                self.logger.error(err)
                raise MetadataConsistencyError(err)
            return self.addresses[address][0]
        try:
            cname = socket.gethostbyaddr(address)[0].lower()
            if cname in self.aliases:
                return self.aliases[cname]
            return cname
        except socket.herror:
            warning = "address resolution error for %s" % address
            self.logger.warning(warning)
            raise MetadataConsistencyError(warning)

    def _merge_groups(self, client, groups, categories=None):
        """ set group membership based on the contents of groups.xml
        and initial group membership of this client. Returns a tuple
        of (allgroups, categories)"""
        numgroups = -1 # force one initial pass
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

    def get_initial_metadata(self, client):
        """Return the metadata for a given client."""
        if False in list(self.states.values()):
            raise MetadataRuntimeError("Metadata has not been read yet")
        client = client.lower()
        if client in self.aliases:
            client = self.aliases[client]
        
        groups = set()
        categories = dict()
        profile = None

        if client not in self.clients:
            pgroup = None
            if client in self.clientgroups:
                pgroup = self.clientgroups[client][0]
            elif self.default:
                pgroup = self.default

            if pgroup:
                self.set_profile(client, pgroup, (None, None), force=True)
                groups.add(pgroup)
                category = self.groups[pgroup].category
                if category:
                    categories[category] = pgroup
                if (pgroup in self.groups and self.groups[pgroup].is_profile):
                    profile = pgroup
            else:
                msg = "Cannot add new client %s; no default group set" % client
                self.logger.error(msg)
                raise MetadataConsistencyError(msg)

        if client in self.clientgroups:
            for cgroup in self.clientgroups[client]:
                if cgroup in groups:
                    continue
                if cgroup not in self.groups:
                    self.groups[cgroup] = MetadataGroup(cgroup)
                category = self.groups[cgroup].category
                if category and category in categories:
                    self.logger.warning("%s: Group %s suppressed by "
                                        "category %s; %s already a member "
                                        "of %s" %
                                        (self.name, cgroup, category,
                                         client, categories[category]))
                    continue
                if category:
                    categories[category] = cgroup
                groups.add(cgroup)
                # favor client groups for setting profile
                if not profile and self.groups[cgroup].is_profile:
                    profile = cgroup

        groups, categories = self._merge_groups(client, groups,
                                                categories=categories)

        bundles = set()
        for group in groups:
            try:
                bundles.update(self.groups[group].bundles)
            except KeyError:
                self.logger.warning("%s: %s is a member of undefined group %s" %
                                    (self.name, client, group))

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

        return ClientMetadata(client, profile, groups, bundles, aliases,
                              addresses, categories, uuid, password, version,
                              self.query)

    def get_all_group_names(self):
        all_groups = set()
        all_groups.update(self.groups.keys())
        all_groups.update([g.name for g in self.group_membership.values()])
        all_groups.update([g.name for g in self.negated_groups.values()])
        for grp in self.clientgroups.values():
            all_groups.update(grp)
        return all_groups

    def get_all_groups_in_category(self, category):
        return set([g.name for g in self.groups.values()
                    if g.category == category])

    def get_client_names_by_profiles(self, profiles):
        rv = []
        for client in list(self.clients):
            mdata = self.get_initial_metadata(client)
            if mdata.profile in profiles:
                rv.append(client)
        return rv

    def get_client_names_by_groups(self, groups):
        mdata = [self.core.build_metadata(client)
                 for client in list(self.clients)]
        return [md.hostname for md in mdata if md.groups.issuperset(groups)]

    def get_client_names_by_bundles(self, bundles):
        mdata = [self.core.build_metadata(client)
                 for client in list(self.clients.keys())]
        return [md.hostname for md in mdata if md.bundles.issuperset(bundles)]

    def merge_additional_groups(self, imd, groups):
        for group in groups:
            if group in imd.groups or group not in self.groups:
                continue
            category = self.groups[group].category
            if category:
                if self.groups[group].category in imd.categories:
                    self.logger.warning("%s: Group %s suppressed by category "
                                        "%s; %s already a member of %s" %
                                        (self.name, group, category,
                                         imd.hostname,
                                         imd.categories[category]))
                    continue
                imd.categories[group] = category
            imd.groups.add(group)

        self._merge_groups(imd.hostname, imd.groups,
                           categories=imd.categories)

        for group in imd.groups:
            if group in self.groups:
                imd.bundles.update(self.groups[group].bundles)

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

    def AuthenticateConnection(self, cert, user, password, address):
        """This function checks auth creds."""
        if cert:
            id_method = 'cert'
            certinfo = dict([x[0] for x in cert['subject']])
            # look at cert.cN
            client = certinfo['commonName']
            self.debug_log("Got cN %s; using as client name" % client)
            auth_type = self.auth.get(client, 'cert+password')
        elif user == 'root':
            id_method = 'address'
            try:
                client = self.resolve_client(address)
            except MetadataConsistencyError:
                self.logger.error("Client %s failed to resolve; metadata problem"
                                  % address[0])
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
        if id_method == 'uuid':
            addr_is_valid = True
        else:
            addr_is_valid = self.validate_client_address(client, address)

        if not addr_is_valid:
            return False

        if id_method == 'cert' and auth_type != 'cert+password':
            # remember the cert-derived client name for this connection
            if client in self.floating:
                self.session_cache[address] = (time.time(), client)
            # we are done if cert+password not required
            return True

        if client not in self.passwords:
            if client in self.secure:
                self.logger.error("Client %s in secure mode but has no password"
                                  % address[0])
                return False
            if password != self.password:
                self.logger.error("Client %s used incorrect global password" %
                                  address[0])
                return False
        if client not in self.secure:
            if client in self.passwords:
                plist = [self.password, self.passwords[client]]
            else:
                plist = [self.password]
            if password not in plist:
                self.logger.error("Client %s failed to use either allowed "
                                  "password" % address[0])
                return False
        else:
            # client in secure mode and has a client password
            if password != self.passwords[client]:
                self.logger.error("Client %s failed to use client password in "
                                  "secure mode" % address[0])
                return False
        # populate the session cache
        if user.decode('utf-8') != 'root':
            self.session_cache[address] = (time.time(), client)
        return True

    def process_statistics(self, meta, _):
        """Hook into statistics interface to toggle clients in bootstrap mode."""
        client = meta.hostname
        if client in self.auth and self.auth[client] == 'bootstrap':
            self.update_client(client, dict(auth='cert'))

    def viz(self, hosts, bundles, key, only_client, colors):
        """Admin mode viz support."""
        if only_client:
            clientmeta = self.core.build_metadata(only_client)

        def include_client(client):
            return not only_client or client != only_client

        def include_bundle(bundle):
            return not only_client or bundle in clientmeta.bundles

        def include_group(group):
            return not only_client or group in clientmeta.groups

        groups_tree = lxml.etree.parse(os.path.join(self.data, "groups.xml"),
                                       parser=Bcfg2.Server.XMLParser)
        try:
            groups_tree.xinclude()
        except lxml.etree.XIncludeError:
            self.logger.error("Failed to process XInclude for file %s: %s" %
                              (dest, sys.exc_info()[1]))
        groups = groups_tree.getroot()
        categories = {'default': 'grey83'}
        viz_str = []
        egroups = groups.findall("Group") + groups.findall('.//Groups/Group')
        for group in egroups:
            if not group.get('category') in categories:
                categories[group.get('category')] = colors.pop()
            group.set('color', categories[group.get('category')])
        if None in categories:
            del categories[None]
        if hosts:
            instances = {}
            for client in list(self.clients):
                if include_client(client):
                    continue
                if client in self.clientgroups:
                    groups = self.clientgroups[client]
                elif self.default:
                    groups = [self.default]
                else:
                    continue
                for group in groups:
                    try:
                        instances[group].append(client)
                    except KeyError:
                        instances[group] = [client]
            for group, clist in list(instances.items()):
                clist.sort()
                viz_str.append('"%s-instances" [ label="%s", shape="record" ];' %
                               (group, '|'.join(clist)))
                viz_str.append('"%s-instances" -> "group-%s";' %
                               (group, group))
        if bundles:
            bundles = []
            [bundles.append(bund.get('name')) \
                 for bund in groups.findall('.//Bundle') \
                 if bund.get('name') not in bundles \
                     and include_bundle(bund.get('name'))]
            bundles.sort()
            for bundle in bundles:
                viz_str.append('"bundle-%s" [ label="%s", shape="septagon"];' %
                               (bundle, bundle))
        gseen = []
        for group in egroups:
            if group.get('profile', 'false') == 'true':
                style = "filled, bold"
            else:
                style = "filled"
            gseen.append(group.get('name'))
            if include_group(group.get('name')):
                viz_str.append('"group-%s" [label="%s", style="%s", fillcolor=%s];' %
                               (group.get('name'), group.get('name'), style,
                                group.get('color')))
                if bundles:
                    for bundle in group.findall('Bundle'):
                        viz_str.append('"group-%s" -> "bundle-%s";' %
                                       (group.get('name'), bundle.get('name')))
        gfmt = '"group-%s" [label="%s", style="filled", fillcolor="grey83"];'
        for group in egroups:
            for parent in group.findall('Group'):
                if parent.get('name') not in gseen and include_group(parent.get('name')):
                    viz_str.append(gfmt % (parent.get('name'),
                                           parent.get('name')))
                    gseen.append(parent.get("name"))
                if include_group(group.get('name')):
                    viz_str.append('"group-%s" -> "group-%s";' %
                                   (group.get('name'), parent.get('name')))
        if key:
            for category in categories:
                viz_str.append('"%s" [label="%s", shape="record", style="filled", fillcolor="%s"];' %
                               (category, category, categories[category]))
        return "\n".join("\t" + s for s in viz_str)


class MetadataLint(Bcfg2.Server.Lint.ServerPlugin):
    def Run(self):
        self.nested_clients()
        self.deprecated_options()

    @classmethod
    def Errors(cls):
        return {"nested-client-tags": "warning",
                "deprecated-clients-options": "warning"}

    def deprecated_options(self):
        groupdata = self.metadata.clients_xml.xdata
        for el in groupdata.xpath("//Client"):
            loc = el.get("location")
            if loc:
                if loc == "floating":
                    floating = True
                else:
                    floating = False
                self.LintError("deprecated-clients-options",
                               "The location='%s' option is deprecated.  "
                               "Please use floating='%s' instead: %s" %
                               (loc, floating, self.RenderXML(el)))        

    def nested_clients(self):
        groupdata = self.metadata.groups_xml.xdata
        for el in groupdata.xpath("//Client//Client"):
            self.LintError("nested-client-tags",
                           "Client %s nested within Client tag: %s" %
                           (el.get("name"), self.RenderXML(el)))
