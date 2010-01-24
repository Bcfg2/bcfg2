'''This file stores persistent metadata for the Bcfg2 Configuration Repository'''
__revision__ = '$Revision$'

import copy
import fcntl
import lxml.etree
import os
import os.path
import socket
import time
import Bcfg2.Server.Plugin

class MetadataConsistencyError(Exception):
    '''This error gets raised when metadata is internally inconsistent'''
    pass

class MetadataRuntimeError(Exception):
    '''This error is raised when the metadata engine is called prior to reading enough data'''
    pass

class ClientMetadata(object):
    '''This object contains client metadata'''
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
        '''Test to see if client is a member of group'''
        return group in self.groups

class MetadataQuery(object):
    def __init__(self, by_name, get_clients, by_groups, by_profiles, all_groups):
        # resolver is set later
        self.by_name = by_name
        self.names_by_groups = by_groups
        self.names_by_profiles = by_profiles
        self.all_clients = get_clients
        self.all_groups = all_groups

    def by_groups(self, groups):
        return [self.by_name(name) for name in self.names_by_groups(groups)]

    def by_profiles(self, profiles):
        return [self.by_name(name) for name in self.names_by_profiles(profiles)]

    def all(self):
        return [self.by_name(name) for name in self.all_clients()]

class Metadata(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.Metadata,
               Bcfg2.Server.Plugin.Statistics):
    '''This class contains data for bcfg2 server metadata'''
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    name = "Metadata"

    def __init__(self, core, datastore, watch_clients=True):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Metadata.__init__(self)
        Bcfg2.Server.Plugin.Statistics.__init__(self)
        if watch_clients:
            try:
                core.fam.AddMonitor("%s/%s" % (self.data, "groups.xml"), self)
                core.fam.AddMonitor("%s/%s" % (self.data, "clients.xml"), self)
            except:
                raise Bcfg2.Server.Plugin.PluginInitError
        self.states = {}
        if watch_clients:
            self.states = {"groups.xml":False, "clients.xml":False}
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
        self.clientdata = None
        self.clientdata_original = None
        self.default = None
        self.pdirty = False
        self.extra = {'groups.xml':[], 'clients.xml':[]}
        self.password = core.password
        self.query = MetadataQuery(core.build_metadata,
                                   lambda:self.clients.keys(),
                                   self.get_client_names_by_groups,
                                   self.get_client_names_by_profiles,
                                   self.get_all_group_names)

    @classmethod
    def init_repo(cls, repo, groups, os_selection, clients):
        path = '%s/%s' % (repo, cls.name)
        cls.make_path(path)
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
        '''find a group'''
        for node in tree.findall("//Group"):
            if node.get("name") == group_name:
                return node
            for child in node:
                if child.tag == "Alias" and child.attrib["name"] == group_name:
                    return node
        return None

    def add_group(self, group_name, attribs):
        '''add group to groups.xml'''
        tree = lxml.etree.parse(self.data + "/groups.xml")
        root = tree.getroot()
        element = lxml.etree.Element("Group", name=group_name)
        for key, val in attribs.iteritems():
            element.set(key, val)
        node = self.search_group(group_name, tree)
        if node != None:
            self.logger.error("Group \"%s\" already exists" % (group_name))
            raise MetadataConsistencyError
        root.append(element)
        group_tree = open(self.data + "/groups.xml","w")
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

    def update_group(self, group_name, attribs):
        '''Update a groups attributes'''
        tree = lxml.etree.parse(self.data + "/groups.xml")
        root = tree.getroot()
        node = self.search_group(group_name, tree)
        if node == None:
            self.logger.error("Group \"%s\" not found" % (group_name))
            raise MetadataConsistencyError
        node.attrib.update(attribs)
        group_tree = open(self.data + "/groups.xml","w")
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

    def remove_group(self, group_name):
        '''Remove a group'''
        tree = lxml.etree.parse(self.data + "/groups.xml")
        root = tree.getroot()
        node = self.search_group(group_name, tree)
        if node == None:
            self.logger.error("Client \"%s\" not found" % (group_name))
            raise MetadataConsistencyError
        root.remove(node)
        group_tree = open(self.data + "/groups.xml","w")
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

    def add_bundle(self, bundle_name):
        '''add bundle to groups.xml'''
        tree = lxml.etree.parse(self.data + "/groups.xml")
        root = tree.getroot()
        element = lxml.etree.Element("Bundle", name=bundle_name)
        node = self.search_group(bundle_name, tree)
        if node != None:
            self.logger.error("Bundle \"%s\" already exists" % (bundle_name))
            raise MetadataConsistencyError
        root.append(element)
        group_tree = open(self.data + "/groups.xml","w")
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
        '''Remove a bundle'''
        tree = lxml.etree.parse(self.data + "/groups.xml")
        root = tree.getroot()
        node = self.search_group(bundle_name, tree)
        if node == None:
            self.logger.error("Bundle \"%s\" not found" % (bundle_name))
            raise MetadataConsistencyError
        root.remove(node)
        group_tree = open(self.data + "/groups.xml","w")
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
        '''find a client'''
        for node in tree.findall("//Client"):
            if node.get("name") == client_name:
                return node
            for child in node:
                if child.tag == "Alias" and child.attrib["name"] == client_name:
                    return node
        return None

    def add_client(self, client_name, attribs):
        '''add client to clients.xml'''
        tree = lxml.etree.parse(self.data + "/clients.xml")
        root = tree.getroot()
        element = lxml.etree.Element("Client", name=client_name)
        for key, val in attribs.iteritems():
            element.set(key, val)
        node = self.search_client(client_name, tree)
        if node != None:
            self.logger.error("Client \"%s\" already exists" % (client_name))
            raise MetadataConsistencyError
        root.append(element)
        client_tree = open(self.data + "/clients.xml","w")
        fd = client_tree.fileno()
        while True:
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                continue
            else:
                break
        tree.write(client_tree)
        fcntl.lockf(fd, fcntl.LOCK_UN)
        client_tree.close()

    def update_client(self, client_name, attribs):
        '''Update a clients attributes'''
        tree = lxml.etree.parse(self.data + "/clients.xml")
        root = tree.getroot()
        node = self.search_client(client_name, tree)
        if node == None:
            self.logger.error("Client \"%s\" not found" % (client_name))
            raise MetadataConsistencyError
        node.attrib.update(attribs)
        client_tree = open(self.data + "/clients.xml","w")
        fd = client_tree.fileno()
        while True:
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                continue
            else:
                break
        tree.write(client_tree)
        fcntl.lockf(fd, fcntl.LOCK_UN)
        client_tree.close()

    def HandleEvent(self, event):
        '''Handle update events for data files'''
        filename = event.filename.split('/')[-1]
        if filename in ['groups.xml', 'clients.xml']:
            dest = filename
        elif filename in reduce(lambda x, y:x+y, self.extra.values()):
            if event.code2str() == 'exists':
                return
            dest = [key for key, value in self.extra.iteritems() if filename in value][0]
        else:
            return
        if event.code2str() == 'endExist':
            return
        try:
            xdata = lxml.etree.parse("%s/%s" % (self.data, dest))
        except lxml.etree.XMLSyntaxError:
            self.logger.error('Failed to parse %s' % (dest))
            return
        included = [ent.get('href') for ent in \
                    xdata.findall('./{http://www.w3.org/2001/XInclude}include')]
        xdata_original = copy.deepcopy(xdata)
        if included:
            for name in included:
                if name not in self.extra[dest]:
                    self.core.fam.AddMonitor("%s/%s" % (self.data, name), self)
                    self.extra[dest].append(name)
            try:
                xdata.xinclude()
            except lxml.etree.XIncludeError:
                self.logger.error("Failed to process XInclude for file %s" % dest)

        if dest == 'clients.xml':
            self.clients = {}
            self.aliases = {}
            self.raliases = {}
            self.bad_clients = {}
            self.secure = []
            self.floating = []
            self.addresses = {}
            self.raddresses = {}
            self.clientdata_original = xdata_original
            self.clientdata = xdata
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
        elif dest == 'groups.xml':
            self.public = []
            self.private = []
            self.profiles = []
            self.groups = {}
            grouptmp = {}
            self.categories = {}
            for group in xdata.xpath('//Groups/Group') \
                    + xdata.xpath('Group'):
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
        self.states[dest] = True
        if False not in self.states.values():
            # check that all client groups are real and complete
            real = self.groups.keys()
            for client in self.clients.keys():
                if self.clients[client] not in self.profiles:
                    self.logger.error("Client %s set as nonexistent or incomplete group %s" \
                                      % (client, self.clients[client]))
                    self.logger.error("Removing client mapping for %s" % (client))
                    self.bad_clients[client] = self.clients[client]
                    del self.clients[client]
            for bclient in self.bad_clients.keys():
                if self.bad_clients[bclient] in self.profiles:
                    self.logger.info("Restored profile mapping for client %s" % bclient)
                    self.clients[bclient] = self.bad_clients[bclient]
                    del self.bad_clients[bclient]

    def set_profile(self, client, profile, addresspair):
        '''Set group parameter for provided client'''
        self.logger.info("Asserting client %s profile to %s" % (client, profile))
        if False in self.states.values():
            raise MetadataRuntimeError
        if profile not in self.public:
            self.logger.error("Failed to set client %s to private group %s" % (client, profile))
            raise MetadataConsistencyError
        if client in self.clients:
            self.logger.info("Changing %s group from %s to %s" % (client, self.clients[client], profile))
            cli = self.clientdata_original.xpath('.//Client[@name="%s"]' % (client))
            cli[0].set('profile', profile)
        else:
            self.logger.info("Creating new client: %s, profile %s" % \
                             (client, profile))
            if addresspair in self.session_cache:
                # we are working with a uuid'd client
                lxml.etree.SubElement(self.clientdata_original.getroot(),
                                      'Client',
                                      name=self.session_cache[addresspair][1],
                                      uuid=client, profile=profile,
                                      address=addresspair[0])
            else:
                lxml.etree.SubElement(self.clientdata_original.getroot(),
                                      'Client', name=client,
                                      profile=profile)
        self.clients[client] = profile
        self.write_back_clients()

    def write_back_clients(self):
        '''Write changes to client.xml back to disk'''
        try:
            datafile = open("%s/%s" % (self.data, 'clients.xml.new'), 'w')
        except IOError:
            self.logger.error("Failed to write clients.xml.new")
            raise MetadataRuntimeError
        # prep data
        dataroot = self.clientdata_original.getroot()
        if hasattr(dataroot, 'iter'):
            items = dataroot.iter()
        else:
            items = dataroot.getchildren()
        for item in items:
            # no items have text data of any sort
            item.tail = None
            item.text = None
        newcontents = lxml.etree.tostring(dataroot, pretty_print=True)

        fd = datafile.fileno()
        while self.locked(fd) == True:
            pass
        try:
            datafile.write(newcontents)
        except:
            fcntl.lockf(fd, fcntl.LOCK_UN)
            self.logger.error("Metadata: Failed to write new clients data to clients.xml.new", exc_info=1)
            os.unlink("%s/%s" % (self.data, "clients.xml.new"))
            raise MetadataRuntimeError
        datafile.close()

        # check if clients.xml is a symlink
        clientsxml = "%s/%s" % (self.data, 'clients.xml')
        if os.path.islink(clientsxml):
            clientsxml = os.readlink(clientsxml)

        try:
            os.rename("%s/%s" % (self.data, 'clients.xml.new'), clientsxml)
        except:
            self.logger.error("Metadata: Failed to rename clients.xml.new")
            raise MetadataRuntimeError

    def locked(self, fd):
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            return True
        return False

    def resolve_client(self, addresspair):
        '''Lookup address locally or in DNS to get a hostname'''
        if addresspair in self.session_cache:
            (stamp, uuid) = self.session_cache[addresspair]
            if time.time() - stamp < 90:
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
        '''Return the metadata for a given client'''
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
        uuids = [item for item, value in self.uuid.iteritems() if value == client]
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
        [all_groups.update(g[1]) for g in self.groups.values()]
        return all_groups

    def get_client_names_by_profiles(self, profiles):
        return [client for client, profile in self.clients.iteritems() \
                if profile in profiles]

    def get_client_names_by_groups(self, groups):
        gprofiles = [profile for profile in self.profiles if \
                     self.groups[profile][1].issuperset(groups)]
        return self.get_client_names_by_profiles(gprofiles)

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
        '''Check address against client'''
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
        '''This function checks auth creds'''
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
        if user != 'root':
            self.session_cache[address] = (time.time(), client)
        return True

    def process_statistics(self, meta, _):
        '''Hook into statistics interface to toggle clients in bootstrap mode'''
        client = meta.hostname
        if client in self.auth and self.auth[client] == 'bootstrap':
            self.logger.info("Asserting client %s auth mode to cert" % client)
            cli = self.clientdata_original.xpath('.//Client[@name="%s"]' \
                                                 % (client))
            cli[0].set('auth', 'cert')
            self.write_back_clients()

    def viz(self, hosts, bundles, key, colors):
        '''admin mode viz support'''
        groups_tree = lxml.etree.parse(self.data + "/groups.xml")
        groups = groups_tree.getroot()
        categories = {'default':'grey83'}
        instances = {}
        viz_str = ""
        egroups = groups.findall("Group") + groups.findall('.//Groups/Group')
        for group in egroups:
            if not group.get('category') in categories:
                categories[group.get('category')] = colors.pop()
            group.set('color', categories[group.get('category')])
        if None in categories:
            del categories[None]
        if hosts:
            clients = self.clients
            for client, profile in clients.iteritems():
                if profile in instances:
                    instances[profile].append(client)
                else:
                    instances[profile] = [client]
            for profile, clist in instances.iteritems():
                clist.sort()
                viz_str += '''\t"%s-instances" [ label="%s", shape="record" ];\n''' \
                    % (profile, '|'.join(clist))
                viz_str += '''\t"%s-instances" -> "group-%s";\n''' \
                    % (profile, profile)
        if bundles:
            bundles = []
            [bundles.append(bund.get('name')) \
                 for bund in groups.findall('.//Bundle') \
                 if bund.get('name') not in bundles]
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
            viz_str += '\t"group-%s" [label="%s", style="%s", fillcolor=%s];\n' % \
                (group.get('name'), group.get('name'), style, group.get('color'))
            if bundles:
                for bundle in group.findall('Bundle'):
                    viz_str += '\t"group-%s" -> "bundle-%s";\n' % \
                        (group.get('name'), bundle.get('name'))
        gfmt = '\t"group-%s" [label="%s", style="filled", fillcolor="grey83"];\n'
        for group in egroups:
            for parent in group.findall('Group'):
                if parent.get('name') not in gseen:
                    viz_str += gfmt % (parent.get('name'), parent.get('name'))
                    gseen.append(parent.get("name"))
                viz_str += '\t"group-%s" -> "group-%s" ;\n' % \
                    (group.get('name'), parent.get('name'))
        if key:
            for category in categories:
                viz_str += '''\t"''' + category + '''" [label="''' + category + \
                    '''", shape="record", style="filled", fillcolor=''' + \
                    categories[category] + '''];\n'''
        return viz_str
