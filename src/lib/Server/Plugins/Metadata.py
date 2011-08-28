"""
This file stores persistent metadata for the Bcfg2 Configuration Repository.
"""

__revision__ = '$Revision$'

import copy
import fcntl
import lxml.etree
import os
import os.path
import socket
import sys
import time

import Bcfg2.Server.FileMonitor
import Bcfg2.Server.Plugin


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


class XMLMetadataConfig(object):
    """Handles xml config files and all XInclude statements"""
    def __init__(self, metadata, watch_clients, basefile):
        self.metadata = metadata
        self.basefile = basefile
        self.should_monitor = watch_clients
        self.extras = []
        self.data = None
        self.basedata = None
        self.basedir = metadata.data
        self.logger = metadata.logger
        self.pseudo_monitor = isinstance(metadata.core.fam,
                                         Bcfg2.Server.FileMonitor.Pseudo)

    @property
    def xdata(self):
        if not self.data:
            raise MetadataRuntimeError
        return self.data

    @property
    def base_xdata(self):
        if not self.basedata:
            raise MetadataRuntimeError
        return self.basedata

    def add_monitor(self, fname):
        """Add a fam monitor for an included file"""
        if self.should_monitor:
            self.metadata.core.fam.AddMonitor("%s/%s" % (self.basedir, fname),
                                              self.metadata)
            self.extras.append(fname)

    def load_xml(self):
        """Load changes from XML"""
        try:
            xdata = lxml.etree.parse("%s/%s" % (self.basedir, self.basefile))
        except lxml.etree.XMLSyntaxError:
            self.logger.error('Failed to parse %s' % (self.basefile))
            return
        self.basedata = copy.deepcopy(xdata)
        included = [ent.get('href') for ent in \
                    xdata.findall('./{http://www.w3.org/2001/XInclude}include')]
        if included:
            for name in included:
                if name not in self.extras:
                    self.add_monitor(name)
            try:
                xdata.xinclude()
            except lxml.etree.XIncludeError:
                self.logger.error("Failed to process XInclude for file %s" % self.basefile)
        self.data = xdata

    def write(self):
        """Write changes to xml back to disk."""
        self.write_xml("%s/%s" % (self.basedir, self.basefile),
                       self.basedata)

    def write_xml(self, fname, xmltree):
        """Write changes to xml back to disk."""
        tmpfile = "%s.new" % fname
        try:
            datafile = open("%s" % tmpfile, 'w')
        except IOError:
            e = sys.exc_info()[1]
            self.logger.error("Failed to write %s: %s" % (tmpfile, e))
            raise MetadataRuntimeError
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
            self.logger.error("Metadata: Failed to write new xml data to %s" % tmpfile, exc_info=1)
            os.unlink("%s" % tmpfile)
            raise MetadataRuntimeError
        datafile.close()

        # check if clients.xml is a symlink
        xmlfile = "%s" % fname
        if os.path.islink(xmlfile):
            xmlfile = os.readlink(xmlfile)

        try:
            os.rename("%s" % tmpfile, xmlfile)
        except:
            self.logger.error("Metadata: Failed to rename %s" % tmpfile)
            raise MetadataRuntimeError

    def find_xml_for_xpath(self, xpath):
        """Find and load xml data containing the xpath query"""
        if self.pseudo_monitor:
            # Reload xml if we don't have a real monitor
            self.load_xml()
        cli = self.basedata.xpath(xpath)
        if len(cli) > 0:
            return {'filename': "%s/%s" % (self.basedir, self.basefile),
                    'xmltree': self.basedata,
                    'xquery': cli}
        else:
            """Try to find the data in included files"""
            for included in self.extras:
                try:
                    xdata = lxml.etree.parse("%s/%s" % (self.basedir, included))
                    cli = xdata.xpath(xpath)
                    if len(cli) > 0:
                        return {'filename': "%s/%s" % (self.basedir, included),
                                'xmltree': xdata,
                                'xquery': cli}
                except lxml.etree.XMLSyntaxError:
                    self.logger.error('Failed to parse %s' % (included))
        return {}

    def HandleEvent(self, event):
        """Handle fam events"""
        filename = event.filename.split('/')[-1]
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
    def __init__(self, client, profile, groups, bundles,
                 aliases, addresses, categories, uuid, password, query):
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
    def __init__(self, by_name, get_clients, by_groups, by_profiles, all_groups, all_groups_in_category):
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


class Metadata(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.Metadata,
               Bcfg2.Server.Plugin.Statistics):
    """This class contains data for bcfg2 server metadata."""
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    name = "Metadata"
    sort_order = 500

    def __init__(self, core, datastore, watch_clients=True):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Metadata.__init__(self)
        Bcfg2.Server.Plugin.Statistics.__init__(self)
        if watch_clients:
            try:
                core.fam.AddMonitor("%s/%s" % (self.data, "groups.xml"), self)
                core.fam.AddMonitor("%s/%s" % (self.data, "clients.xml"), self)
            except:
                print("Unable to add file monitor for groups.xml or clients.xml")
                raise Bcfg2.Server.Plugin.PluginInitError

        self.clients_xml = XMLMetadataConfig(self, watch_clients, 'clients.xml')
        self.groups_xml = XMLMetadataConfig(self, watch_clients, 'groups.xml')
        self.states = {}
        if watch_clients:
            self.states = {"groups.xml": False,
                           "clients.xml": False}
        self.addresses = {}
        self.auth = dict()
        self.clients = {}
        self.aliases = {}
        self.groups = {}
        self.cgroups = {}
        self.public = []
        self.private = []
        self.profiles = []
        self.categories = {}
        self.bad_clients = {}
        self.uuid = {}
        self.secure = []
        self.floating = []
        self.passwords = {}
        self.session_cache = {}
        self.default = None
        self.pdirty = False
        self.extra = {'groups.xml': [],
                      'clients.xml': []}
        self.password = core.password
        self.query = MetadataQuery(core.build_metadata,
                                   lambda: list(self.clients.keys()),
                                   self.get_client_names_by_groups,
                                   self.get_client_names_by_profiles,
                                   self.get_all_group_names,
                                   self.get_all_groups_in_category)

    @classmethod
    def init_repo(cls, repo, groups, os_selection, clients):
        path = '%s/%s' % (repo, cls.name)
        os.makedirs(path)
        open("%s/Metadata/groups.xml" %
             repo, "w").write(groups % os_selection)
        open("%s/Metadata/clients.xml" %
             repo, "w").write(clients % socket.getfqdn())

    def get_groups(self):
        '''return groups xml tree'''
        groups_tree = lxml.etree.parse(self.data + "/groups.xml")
        root = groups_tree.getroot()
        return root

    def search_group(self, group_name, tree):
        """Find a group."""
        for node in tree.findall("//Group"):
            if node.get("name") == group_name:
                return node
            for child in node:
                if child.tag == "Alias" and child.attrib["name"] == group_name:
                    return node
        return None

    def add_group(self, group_name, attribs):
        """Add group to groups.xml."""

        node = self.search_group(group_name, self.groups_xml.xdata)
        if node != None:
            self.logger.error("Group \"%s\" already exists" % (group_name))
            raise MetadataConsistencyError

        element = lxml.etree.SubElement(self.groups_xml.base_xdata.getroot(),
                                      "Group", name=group_name)
        for key, val in list(attribs.items()):
            element.set(key, val)
        self.groups_xml.write()

    def update_group(self, group_name, attribs):
        """Update a groups attributes."""
        node = self.search_group(group_name, self.groups_xml.xdata)
        if node == None:
            self.logger.error("Group \"%s\" does not exist" % (group_name))
            raise MetadataConsistencyError
        xdict = self.groups_xml.find_xml_for_xpath('.//Group[@name="%s"]' % (node.get('name')))
        if not xdict:
            self.logger.error("Unexpected error finding group")
            raise MetadataConsistencyError

        for key, val in list(attribs.items()):
            xdict['xquery'][0].set(key, val)
        self.groups_xml.write_xml(xdict['filename'], xdict['xmltree'])

    def remove_group(self, group_name):
        """Remove a group."""
        node = self.search_group(group_name, self.groups_xml.xdata)
        if node == None:
            self.logger.error("Group \"%s\" does not exist" % (group_name))
            raise MetadataConsistencyError
        xdict = self.groups_xml.find_xml_for_xpath('.//Group[@name="%s"]' % (node.get('name')))
        if not xdict:
            self.logger.error("Unexpected error finding group")
            raise MetadataConsistencyError
        xdict['xquery'][0].getparent().remove(xdict['xquery'][0])
        self.groups_xml.write_xml(xdict['filename'], xdict['xmltree'])

    def add_bundle(self, bundle_name):
        """Add bundle to groups.xml."""
        tree = lxml.etree.parse(self.data + "/groups.xml")
        root = tree.getroot()
        element = lxml.etree.Element("Bundle", name=bundle_name)
        node = self.search_group(bundle_name, tree)
        if node != None:
            self.logger.error("Bundle \"%s\" already exists" % (bundle_name))
            raise MetadataConsistencyError
        root.append(element)
        group_tree = open(self.data + "/groups.xml", "w")
        fd = group_tree.fileno()
        while True:
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                continue
            else:
                break
        tree.write(group_tree)
        fcntl.lockf(fd, fcntl.LOCK_UN)
        group_tree.close()

    def remove_bundle(self, bundle_name):
        """Remove a bundle."""
        tree = lxml.etree.parse(self.data + "/groups.xml")
        root = tree.getroot()
        node = self.search_group(bundle_name, tree)
        if node == None:
            self.logger.error("Bundle \"%s\" not found" % (bundle_name))
            raise MetadataConsistencyError
        root.remove(node)
        group_tree = open(self.data + "/groups.xml", "w")
        fd = group_tree.fileno()
        while True:
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                continue
            else:
                break
        tree.write(group_tree)
        fcntl.lockf(fd, fcntl.LOCK_UN)
        group_tree.close()

    def search_client(self, client_name, tree):
        """Find a client."""
        for node in tree.findall("//Client"):
            if node.get("name") == client_name:
                return node
            for child in node:
                if child.tag == "Alias" and child.attrib["name"] == client_name:
                    return node
        return None

    def add_client(self, client_name, attribs):
        """Add client to clients.xml."""
        node = self.search_client(client_name, self.clients_xml.xdata)
        if node != None:
            self.logger.error("Client \"%s\" already exists" % (client_name))
            raise MetadataConsistencyError

        element = lxml.etree.SubElement(self.clients_xml.base_xdata.getroot(),
                                      "Client", name=client_name)
        for key, val in list(attribs.items()):
            element.set(key, val)
        self.clients_xml.write()

    def update_client(self, client_name, attribs):
        """Update a clients attributes."""
        node = self.search_client(client_name, self.clients_xml.xdata)
        if node == None:
            self.logger.error("Client \"%s\" does not exist" % (client_name))
            raise MetadataConsistencyError

        xdict = self.clients_xml.find_xml_for_xpath('.//Client[@name="%s"]' % (node.get('name')))
        if not xdict:
            self.logger.error("Unexpected error finding client")
            raise MetadataConsistencyError

        node = xdict['xquery'][0]
        [node.set(key, value) for key, value in list(attribs.items())]
        self.clients_xml.write_xml(xdict['filename'], xdict['xmltree'])

    def HandleEvent(self, event):
        """Handle update events for data files."""
        if self.clients_xml.HandleEvent(event):
            xdata = self.clients_xml.xdata
            self.clients = {}
            self.aliases = {}
            self.raliases = {}
            self.bad_clients = {}
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
                if client.get('secure', 'false') == 'true':
                    self.secure.append(clname)
                if client.get('location', 'fixed') == 'floating':
                    self.floating.append(clname)
                if 'password' in client.attrib:
                    self.passwords[clname] = client.get('password')
                for alias in [alias for alias in client.findall('Alias')\
                              if 'address' in alias.attrib]:
                    if alias.get('address') in self.addresses:
                        self.addresses[alias.get('address')].append(clname)
                    else:
                        self.addresses[alias.get('address')] = [clname]
                    if clname not in self.raddresses:
                        self.raddresses[clname] = set()
                    self.raddresses[clname].add(alias.get('address'))
                self.clients.update({clname: client.get('profile')})
                [self.aliases.update({alias.get('name'): clname}) \
                 for alias in client.findall('Alias')]
                self.raliases[clname] = set()
                [self.raliases[clname].add(alias.get('name')) for alias \
                 in client.findall('Alias')]
            self.states['clients.xml'] = True
        elif self.groups_xml.HandleEvent(event):
            xdata = self.groups_xml.xdata
            self.public = []
            self.private = []
            self.profiles = []
            self.groups = {}
            grouptmp = {}
            self.categories = {}
            groupseen = list()
            for group in xdata.xpath('//Groups/Group'):
                if group.get('name') not in groupseen:
                    groupseen.append(group.get('name'))
                else:
                    self.logger.error("Metadata: Group %s defined multiply" % (group.get('name')))
                grouptmp[group.get('name')] = tuple([[item.get('name') for item in group.findall(spec)]
                                                     for spec in ['./Bundle', './Group']])
                grouptmp[group.get('name')][1].append(group.get('name'))
                if group.get('default', 'false') == 'true':
                    self.default = group.get('name')
                if group.get('profile', 'false') == 'true':
                    self.profiles.append(group.get('name'))
                if group.get('public', 'false') == 'true':
                    self.public.append(group.get('name'))
                elif group.get('public', 'true') == 'false':
                    self.private.append(group.get('name'))
                if 'category' in group.attrib:
                    self.categories[group.get('name')] = group.get('category')
            for group in grouptmp:
                # self.groups[group] => (bundles, groups, categories)
                self.groups[group] = (set(), set(), {})
                tocheck = [group]
                group_cat = self.groups[group][2]
                while tocheck:
                    now = tocheck.pop()
                    self.groups[group][1].add(now)
                    if now in grouptmp:
                        (bundles, groups) = grouptmp[now]
                        for ggg in [ggg for ggg in groups if ggg not in self.groups[group][1]]:
                            if ggg not in self.categories or \
                                   self.categories[ggg] not in self.groups[group][2]:
                                self.groups[group][1].add(ggg)
                                tocheck.append(ggg)
                                if ggg in self.categories:
                                    group_cat[self.categories[ggg]] = ggg
                            elif ggg in self.categories:
                                self.logger.info("Group %s: %s cat-suppressed %s" % \
                                                 (group,
                                                  group_cat[self.categories[ggg]],
                                                  ggg))
                        [self.groups[group][0].add(bund) for bund in bundles]
            self.states['groups.xml'] = True
        if False not in list(self.states.values()):
            # check that all client groups are real and complete
            real = list(self.groups.keys())
            for client in list(self.clients.keys()):
                if self.clients[client] not in self.profiles:
                    self.logger.error("Client %s set as nonexistent or incomplete group %s" \
                                      % (client, self.clients[client]))
                    self.logger.error("Removing client mapping for %s" % (client))
                    self.bad_clients[client] = self.clients[client]
                    del self.clients[client]
            for bclient in list(self.bad_clients.keys()):
                if self.bad_clients[bclient] in self.profiles:
                    self.logger.info("Restored profile mapping for client %s" % bclient)
                    self.clients[bclient] = self.bad_clients[bclient]
                    del self.bad_clients[bclient]

    def set_profile(self, client, profile, addresspair):
        """Set group parameter for provided client."""
        self.logger.info("Asserting client %s profile to %s" % (client, profile))
        if False in list(self.states.values()):
            raise MetadataRuntimeError
        if profile not in self.public:
            self.logger.error("Failed to set client %s to private group %s" % (client, profile))
            raise MetadataConsistencyError
        if client in self.clients:
            self.logger.info("Changing %s group from %s to %s" % (client, self.clients[client], profile))
            xdict = self.clients_xml.find_xml_for_xpath('.//Client[@name="%s"]' % (client))
            if not xdict:
                self.logger.error("Metadata: Unable to update profile for client %s.  Use of Xinclude?" % client)
                raise MetadataConsistencyError
            xdict['xquery'][0].set('profile', profile)
            self.clients_xml.write_xml(xdict['filename'], xdict['xmltree'])
        else:
            self.logger.info("Creating new client: %s, profile %s" % \
                             (client, profile))
            if addresspair in self.session_cache:
                # we are working with a uuid'd client
                lxml.etree.SubElement(self.clients_xml.base_xdata.getroot(),
                                      'Client',
                                      name=self.session_cache[addresspair][1],
                                      uuid=client, profile=profile,
                                      address=addresspair[0])
            else:
                lxml.etree.SubElement(self.clients_xml.base_xdata.getroot(),
                                      'Client', name=client,
                                      profile=profile)
        self.clients[client] = profile
        self.clients_xml.write()

    def resolve_client(self, addresspair, cleanup_cache=False):
        """Lookup address locally or in DNS to get a hostname."""
        if addresspair in self.session_cache:
            # client _was_ cached, so there can be some expired entries
            # we need to clean them up to avoid potentially infinite memory swell
            cache_ttl = 90
            if cleanup_cache:
                # remove entries for this client's IP address with _any_ port numbers
                # - perhaps a priority queue could be faster?
                curtime = time.time()
                for addrpair in self.session_cache.keys():
                     if addresspair[0] == addrpair[0]:
                         (stamp, _) = self.session_cache[addrpair]
                         if curtime - stamp > cache_ttl:
                             del self.session_cache[addrpair]
            # return the cached data
            (stamp, uuid) = self.session_cache[addresspair]
            if time.time() - stamp < cache_ttl:
                return self.session_cache[addresspair][1]
        address = addresspair[0]
        if address in self.addresses:
            if len(self.addresses[address]) != 1:
                self.logger.error("Address %s has multiple reverse assignments; a uuid must be used" % (address))
                raise MetadataConsistencyError
            return self.addresses[address][0]
        try:
            cname = socket.gethostbyaddr(address)[0].lower()
            if cname in self.aliases:
                return self.aliases[cname]
            return cname
        except socket.herror:
            warning = "address resolution error for %s" % (address)
            self.logger.warning(warning)
            raise MetadataConsistencyError

    def get_initial_metadata(self, client):
        """Return the metadata for a given client."""
        if False in list(self.states.values()):
            raise MetadataRuntimeError
        client = client.lower()
        if client in self.aliases:
            client = self.aliases[client]
        if client in self.clients:
            profile = self.clients[client]
            (bundles, groups, categories) = self.groups[profile]
        else:
            if self.default == None:
                self.logger.error("Cannot set group for client %s; no default group set" % (client))
                raise MetadataConsistencyError
            self.set_profile(client, self.default, (None, None))
            profile = self.default
            [bundles, groups, categories] = self.groups[self.default]
        aliases = self.raliases.get(client, set())
        addresses = self.raddresses.get(client, set())
        newgroups = set(groups)
        newbundles = set(bundles)
        newcategories = {}
        newcategories.update(categories)
        if client in self.passwords:
            password = self.passwords[client]
        else:
            password = None
        uuids = [item for item, value in list(self.uuid.items()) if value == client]
        if uuids:
            uuid = uuids[0]
        else:
            uuid = None
        for group in self.cgroups.get(client, []):
            if group in self.groups:
                nbundles, ngroups, ncategories = self.groups[group]
            else:
                nbundles, ngroups, ncategories = ([], [group], {})
            [newbundles.add(b) for b in nbundles if b not in newbundles]
            [newgroups.add(g) for g in ngroups if g not in newgroups]
            newcategories.update(ncategories)
        return ClientMetadata(client, profile, newgroups, newbundles, aliases,
                              addresses, newcategories, uuid, password, self.query)

    def get_all_group_names(self):
        all_groups = set()
        [all_groups.update(g[1]) for g in list(self.groups.values())]
        return all_groups

    def get_all_groups_in_category(self, category):
        all_groups = set()
        [all_groups.add(g) for g in self.categories \
                if self.categories[g] == category]
        return all_groups

    def get_client_names_by_profiles(self, profiles):
        return [client for client, profile in list(self.clients.items()) \
                if profile in profiles]

    def get_client_names_by_groups(self, groups):
        mdata = [self.core.build_metadata(client)
                 for client in list(self.clients.keys())]
        return [md.hostname for md in mdata if md.groups.issuperset(groups)]

    def merge_additional_groups(self, imd, groups):
        for group in groups:
            if group in self.categories and \
                   self.categories[group] in imd.categories:
                continue
            nb, ng, _ = self.groups.get(group, (list(), [group], dict()))
            for b in nb:
                if b not in imd.bundles:
                    imd.bundles.add(b)
            for g in ng:
                if g not in imd.groups:
                    if g in self.categories and \
                       self.categories[g] in imd.categories:
                        continue
                    if g in self.private:
                        self.logger.error("Refusing to add dynamic membership in private group %s for client %s" % (g, imd.hostname))
                        continue
                    imd.groups.add(g)

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
                self.debug_log("Client %s matches address %s" % (client, address))
                return True
            else:
                self.logger.error("Got request for non-float client %s from %s" \
                                  % (client, address))
                return False
        resolved = self.resolve_client(addresspair)
        if resolved.lower() == client.lower():
            return True
        else:
            self.logger.error("Got request for %s from incorrect address %s" \
                              % (client, address))
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
                self.logger.error("Client %s failed to resolve; metadata problem" % (address[0]))
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
                self.logger.error("Client %s in secure mode but has no password" % (address[0]))
                return False
            if password != self.password:
                self.logger.error("Client %s used incorrect global password" % (address[0]))
                return False
        if client not in self.secure:
            if client in self.passwords:
                plist = [self.password, self.passwords[client]]
            else:
                plist = [self.password]
            if password not in plist:
                self.logger.error("Client %s failed to use either allowed password" % \
                                  (address[0]))
                return False
        else:
            # client in secure mode and has a client password
            if password != self.passwords[client]:
                self.logger.error("Client %s failed to use client password in secure mode" % \
                                  (address[0]))
                return False
        # populate the session cache
        if user.decode('utf-8') != 'root':
            self.session_cache[address] = (time.time(), client)
        return True

    def process_statistics(self, meta, _):
        """Hook into statistics interface to toggle clients in bootstrap mode."""
        client = meta.hostname
        if client in self.auth and self.auth[client] == 'bootstrap':
            self.logger.info("Asserting client %s auth mode to cert" % client)
            xdict = self.clients_xml.find_xml_for_xpath('.//Client[@name="%s"]' % (client))
            if not xdict:
                self.logger.error("Metadata: Unable to update profile for client %s.  Use of Xinclude?" % client)
                raise MetadataConsistencyError
            xdict['xquery'][0].set('auth', 'cert')
            self.clients_xml.write_xml(xdict['filename'], xdict['xmltree'])

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
        
        groups_tree = lxml.etree.parse(self.data + "/groups.xml")
        try:
            groups_tree.xinclude()
        except lxml.etree.XIncludeError:
            self.logger.error("Failed to process XInclude for file %s" % dest)
        groups = groups_tree.getroot()
        categories = {'default': 'grey83'}
        viz_str = ""
        egroups = groups.findall("Group") + groups.findall('.//Groups/Group')
        for group in egroups:
            if not group.get('category') in categories:
                categories[group.get('category')] = colors.pop()
            group.set('color', categories[group.get('category')])
        if None in categories:
            del categories[None]
        if hosts:
            instances = {}
            clients = self.clients
            for client, profile in list(clients.items()):
                if include_client(client):
                    continue
                if profile in instances:
                    instances[profile].append(client)
                else:
                    instances[profile] = [client]
            for profile, clist in list(instances.items()):
                clist.sort()
                viz_str += '''\t"%s-instances" [ label="%s", shape="record" ];\n''' \
                    % (profile, '|'.join(clist))
                viz_str += '''\t"%s-instances" -> "group-%s";\n''' \
                    % (profile, profile)
        if bundles:
            bundles = []
            [bundles.append(bund.get('name')) \
                 for bund in groups.findall('.//Bundle') \
                 if bund.get('name') not in bundles \
                     and include_bundle(bund.get('name'))]
            bundles.sort()
            for bundle in bundles:
                viz_str += '''\t"bundle-%s" [ label="%s", shape="septagon"];\n''' \
                    % (bundle, bundle)
        gseen = []
        for group in egroups:
            if group.get('profile', 'false') == 'true':
                style = "filled, bold"
            else:
                style = "filled"
            gseen.append(group.get('name'))
            if include_group(group.get('name')):
                viz_str += '\t"group-%s" [label="%s", style="%s", fillcolor=%s];\n' % \
                           (group.get('name'), group.get('name'), style, group.get('color'))
                if bundles:
                    for bundle in group.findall('Bundle'):
                        viz_str += '\t"group-%s" -> "bundle-%s";\n' % \
                                   (group.get('name'), bundle.get('name'))
        gfmt = '\t"group-%s" [label="%s", style="filled", fillcolor="grey83"];\n'
        for group in egroups:
            for parent in group.findall('Group'):
                if parent.get('name') not in gseen and include_group(parent.get('name')):
                    viz_str += gfmt % (parent.get('name'), parent.get('name'))
                    gseen.append(parent.get("name"))
                if include_group(group.get('name')):
                    viz_str += '\t"group-%s" -> "group-%s" ;\n' % \
                               (group.get('name'), parent.get('name'))
        if key:
            for category in categories:
                viz_str += '''\t"''' + category + '''" [label="''' + category + \
                    '''", shape="record", style="filled", fillcolor=''' + \
                    categories[category] + '''];\n'''
        return viz_str
