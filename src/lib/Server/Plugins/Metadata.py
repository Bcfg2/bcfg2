'''This file stores persistent metadata for the Bcfg2 Configuration Repository'''
__revision__ = '$Revision$'

import lxml.etree, re, socket, time, fcntl, copy
import Bcfg2.Server.Plugin

class MetadataConsistencyError(Exception):
    '''This error gets raised when metadata is internally inconsistent'''
    pass

class MetadataRuntimeError(Exception):
    '''This error is raised when the metadata engine is called prior to reading enough data'''
    pass

class ClientMetadata(object):
    '''This object contains client metadata'''
    def __init__(self, client, groups, bundles, categories, uuid,
                 password, overall):
        self.hostname = client
        self.bundles = bundles
        self.groups = groups
        self.categories = categories
        self.uuid = uuid
        self.password = password
        self.all = overall

    def inGroup(self, group):
        '''Test to see if client is a member of group'''
        return group in self.groups

    def get_clients_by_group(self, group):
        """
        return a list of clients that are members of a group
        Arguments:
        - `group`: group name
        """
        profiles = [key for key, value in self.all[0].iteritems() \
                    if group in value[1]]
        return [key for key, value in self.all[1].iteritems() \
                if value in profiles]

    def get_clients_by_profile(self, profile):
        """
        return clients with a given profile
        Arguments:
        - `profile`: profile name
        """
        return [key for key, value in self.all[1].iteritems() \
                if value == profile]


class Metadata(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.Metadata):
    '''This class contains data for bcfg2 server metadata'''
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    name = "Metadata"

    def __init__(self, core, datastore, watch_clients=True):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Metadata.__init__(self)
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
        self.clients = {}
        self.aliases = {}
        self.groups = {}
        self.cgroups = {}
        self.public = []
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

    def get_groups(self):
        '''return groups xml tree'''
        groups_tree = lxml.etree.parse(self.data + "/groups.xml")
        root = groups_tree.getroot()
        return root

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

    def remove_client(self, client_name):
        '''Remove a client'''
        tree = lxml.etree.parse(self.data + "/clients.xml")
        root = tree.getroot()
        node = self.search_client(client_name, tree)
        if node == None:
            self.logger.error("Client \"%s\" not found" % (client_name))
            raise MetadataConsistencyError
        root.remove(node)
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
        elif filename in reduce(lambda x,y:x+y, self.extra.values()):
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
            self.bad_clients = {}
            self.secure = []
            self.floating = []
            self.addresses = {}
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
                if 'uuid' in client.attrib:
                    self.uuid[client.get('uuid')] = clname
                if client.get('secure', 'false') == 'true' :
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
                    
                self.clients.update({clname: client.get('profile')})
                [self.aliases.update({alias.get('name'): clname}) \
                 for alias in client.findall('Alias')]
        elif dest == 'groups.xml':
            self.public = []
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
                if 'category' in group.attrib:
                    self.categories[group.get('name')] = group.get('category')
            for group in grouptmp:
                # self.groups[group] => (bundles, groups, categories)
                self.groups[group] = ([], [], {})
                tocheck = [group]
                group_cat = self.groups[group][2]
                while tocheck:
                    now = tocheck.pop()
                    if now not in self.groups[group][1]:
                        self.groups[group][1].append(now)
                    if now in grouptmp:
                        (bundles, groups) = grouptmp[now]
                        for ggg in [ggg for ggg in groups if ggg not in self.groups[group][1]]:
                            if ggg not in self.categories or \
                                   self.categories[ggg] not in self.groups[group][2]:
                                self.groups[group][1].append(ggg)
                                tocheck.append(ggg)
                                if ggg in self.categories:
                                    group_cat[self.categories[ggg]] = ggg
                            elif ggg in self.categories:
                                self.logger.info("Group %s: %s cat-suppressed %s" % \
                                                 (group,
                                                  group_cat[self.categories[ggg]],
                                                  ggg))
                        [self.groups[group][0].append(bund) for bund in bundles
                         if bund not in self.groups[group][0]]
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
                                      'Client', name=client,
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
            datafile = open("%s/%s" % (self.data, 'clients.xml'), 'w')
        except IOError:
            self.logger.error("Failed to write clients.xml")
            raise MetadataRuntimeError
        fd = datafile.fileno()
        while self.locked(fd) == True:
            pass
        datafile.write(lxml.etree.tostring(self.clientdata_original.getroot(),
                                           pretty_print='true'))
        fcntl.lockf(fd, fcntl.LOCK_UN)
        datafile.close()
    
    def locked(self, fd):
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            return True
        return False
    
    def resolve_client(self, addresspair):
        '''Lookup address locally or in DNS to get a hostname'''
        #print self.session_cache
        if addresspair in self.session_cache:
            (stamp, uuid) = self.session_cache[addresspair]
            if time.time() - stamp < 60:
                return self.uuid[uuid]
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
            (bundles, groups, categories) = self.groups[self.clients[client]]
        else:
            if self.default == None:
                self.logger.error("Cannot set group for client %s; no default group set" % (client))
                raise MetadataConsistencyError
            self.set_profile(client, self.default, (None, None))
            [bundles, groups, categories] = self.groups[self.default]
        newgroups = groups[:]
        newbundles = bundles[:]
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
            [newbundles.append(b) for b in nbundles if b not in newbundles]
            [newgroups.append(g) for g in ngroups if g not in newgroups]
            newcategories.update(ncategories)
        groupscopy = copy.deepcopy(self.groups)
        clientscopy = copy.deepcopy(self.clients)
        return ClientMetadata(client, newgroups, newbundles, newcategories,
                              uuid, password, (groupscopy, clientscopy))
        
    def merge_additional_metadata(self, imd, source, groups, data):
        for group in groups:
            if group in self.categories and \
                   self.categories[group] in imd.categories:
                continue
            nb, ng, _ = self.groups.get(group, (list(), [group], dict()))
            for b in nb:
                if b not in imd.bundles:
                    imd.bundles.append(b)
            for g in ng:
                if g not in imd.groups:
                    if g in self.categories and \
                       self.categories[g] in imd.categories:
                        continue
                    imd.groups.append(g)
        if not hasattr(imd, source.lower()):
            setattr(imd, source.lower(), data)
    
    def AuthenticateConnection(self, user, password, address):
        '''This function checks user and password'''
        if user == 'root':
            # we aren't using per-client keys
            try:
                client = self.resolve_client(address)
            except MetadataConsistencyError:
                self.logger.error("Client %s failed to authenticate due to metadata problem" % (address[0]))
                return False
        else:
            # user maps to client
            if user not in self.uuid:
                client = user
                self.uuid[user] = user
            else:
                client = self.uuid[user]

        # we have the client
        if client not in self.floating and user != 'root':
            if address[0] in self.addresses:
                # we are using manual resolution
                if client not in self.addresses[address[0]]:
                    self.logger.error("Got request for non-floating UUID %s from %s" % (user, address[0]))
                    return False
            elif client != self.resolve_client(address):
                self.logger.error("Got request for non-floating UUID %s from %s" \
                                  % (user, address[0]))
                return False
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
            self.session_cache[address] = (time.time(), user)
        return True

    def GetClientByGroup(self, group):
        '''Return a list of clients that are in a given group'''
        return [client for client in self.clients \
                if group in self.groups[self.clients[client]][1]]

    def GetClientByProfile(self, profile):
        '''Return a list of clients that are members of a given profile'''
        return [client for client in self.clients \
                if self.clients[client] == profile]
    
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
                viz_str +=  '''\t"bundle-%s" [ label="%s", shape="septagon"];\n''' \
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
