'''This file stores persistent metadata for the BCFG Configuration Repository'''
__revision__ = '$Revision$'

import lxml.etree, re, socket
import Bcfg2.Server.Plugin

class MetadataConsistencyError(Exception):
    '''This error gets raised when metadata is internally inconsistent'''
    pass

class MetadataRuntimeError(Exception):
    '''This error is raised when the metadata engine is called prior to reading enough data'''
    pass

class ClientMetadata(object):
    '''This object contains client metadata'''
    def __init__(self, client, groups, bundles, toolset, categories, probed):
        self.hostname = client
        self.bundles = bundles
        self.groups = groups
        self.toolset = toolset
        self.categories = categories
        self.probes = probed

class Metadata(Bcfg2.Server.Plugin.Plugin):
    '''This class contains data for bcfg2 server metadata'''
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __name__ = "Metadata"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.__name__ = 'Metadata'
        core.fam.AddMonitor("%s/%s" % (self.data, "groups.xml"), self)
        core.fam.AddMonitor("%s/%s" % (self.data, "clients.xml"), self)
        self.states = {'groups.xml':False, 'clients.xml':False}
        self.addresses = {}
        self.clients = {}
        self.aliases = {}
        self.groups = {}
        self.public = []
        self.profiles = []
        self.toolsets = {}
        self.categories = {}
        self.clientdata = None
        self.default = None
        try:
            self.probes = Bcfg2.Server.Plugin.DirectoryBacked(datastore + "/Probes",
                                                              core.fam)
        except:
            self.probes = False
        self.probedata = {}

    def HandleEvent(self, event):
        '''Handle update events for data files'''
        filename = event.filename.split('/')[-1]
        if filename not in ['groups.xml', 'clients.xml']:
            return
        if event.code2str() == 'endExist':
            return
        try:
            xdata = lxml.etree.parse("%s/%s" % (self.data, filename))
        except lxml.etree.XMLSyntaxError:
            self.logger.error('Failed to parse %s' % (filename))
            return
        if filename == 'clients.xml':
            self.clients = {}
            self.aliases = {}
            self.clientdata = xdata
            for client in xdata.findall('./Client'):
                if 'address' in client.attrib:
                    self.addresses[client.get('address')] = client.get('name')
                for alias in [alias for alias in client.findall('Alias') if 'address' in alias.attrib]:
                    self.addresses[alias.get('address')] = client.get('name')
                    
                self.clients.update({client.get('name'): client.get('profile')})
                [self.aliases.update({alias.get('name'): client.get('name')}) for alias in client.findall('Alias')]
        elif filename == 'groups.xml':
            self.public = []
            self.profiles = []
            self.toolsets = {}
            self.groups = {}
            grouptmp = {}
            self.categories = {}
            for group in xdata.findall('./Group'):
                grouptmp[group.get('name')] = tuple([[item.get('name') for item in group.findall(spec)]
                                                     for spec in ['./Bundle', './Group']])
                grouptmp[group.get('name')][1].append(group.get('name'))
                if group.get('default', 'false') == 'true':
                    self.default = group.get('name')
                if group.get('profile', 'false') == 'true':
                    self.profiles.append(group.get('name'))
                if group.get('public', 'false') == 'true':
                    self.public.append(group.get('name'))
                if group.attrib.has_key('toolset'):
                    self.toolsets[group.get('name')] = group.get('toolset')
                if group.attrib.has_key('category'):
                    self.categories[group.get('name')] = group.get('category')
            for group in grouptmp:
                # self.groups[group] => (bundles, groups, categories)
                self.groups[group] = ([], [], {})
                tocheck = [group]
                while tocheck:
                    now = tocheck.pop()
                    if now not in self.groups[group][1]:
                        self.groups[group][1].append(now)
                    if grouptmp.has_key(now):
                        (bundles, groups) = grouptmp[now]
                        for ggg in [ggg for ggg in groups if ggg not in self.groups[group][1]]:
                            if not self.categories.has_key(ggg) or not self.groups[group][2].has_key(self.categories[ggg]):
                                self.groups[group][1].append(ggg)
                                tocheck.append(ggg)
                            if self.categories.has_key(ggg):
                                self.groups[group][2][self.categories[ggg]] = ggg
                        [self.groups[group][0].append(bund) for bund in bundles
                         if bund not in self.groups[group][0]]
        self.states[filename] = True
        if False not in self.states.values():
            # check that all client groups are real and complete
            real = self.groups.keys()
            for client in self.clients.keys():
                if self.clients[client] not in real or self.clients[client] not in self.profiles:
                    self.logger.error("Client %s set as nonexistant or incomplete group %s" \
                                      % (client, self.clients[client]))
                    self.logger.error("Removing client mapping for %s" % (client))
                    del self.clients[client]

    def set_profile(self, client, profile):
        '''Set group parameter for provided client'''
        self.logger.info("Asserting client %s profile to %s" % (client, profile))
        if False in self.states.values():
            raise MetadataRuntimeError
        if profile not in self.public:
            self.logger.error("Failed to set client %s to private group %s" % (client, profile))
            raise MetadataConsistencyError
        if self.clients.has_key(client):
            self.logger.info("Changing %s group from %s to %s" % (client, self.clients[client], profile))
            cli = self.clientdata.xpath('/Clients/Client[@name="%s"]' % (client))
            cli[0].set('profile', profile)
        else:
            lxml.etree.SubElement(self.clientdata.getroot(), 'Client', name=client, profile=profile)
        self.clients[client] = profile
        self.write_back_clients()

    def write_back_clients(self):
        '''Write changes to client.xml back to disk'''
        try:
            datafile = open("%s/%s" % (self.data, 'clients.xml'), 'w')
        except IOError:
            self.logger.error("Failed to write clients.xml")
            raise MetadataRuntimeError
        datafile.write(lxml.etree.tostring(self.clientdata.getroot()))
        datafile.close()

    def find_toolset(self, client):
        '''Find the toolset for a given client'''
        tgroups = [self.toolsets[group] for group in self.groups[client][1] if self.toolsets.has_key(group)]
        if len(tgroups) == 1:
            return tgroups[0]
        elif len(tgroups) == 0:
            self.logger.error("Couldn't find toolset for client %s" % (client))
            raise MetadataConsistencyError
        else:
            self.logger.error("Got goofy toolset result for client %s" % (client))
            raise MetadataConsistencyError

    def get_config_template(self, client):
        '''Build the configuration header for a client configuration'''
        return lxml.etree.Element("Configuration", version='2.0', toolset=self.find_toolset(client))

    def resolve_client(self, address):
        '''Lookup address locally or in DNS to get a hostname'''
        if self.addresses.has_key(address):
            return self.addresses[address]
        try:
            return socket.gethostbyaddr(address)[0]
        except socket.herror:
            warning = "address resolution error for %s" % (address)
            self.logger.warning(warning)
            raise MetadataConsistencyError
    
    def get_metadata(self, client):
        '''Return the metadata for a given client'''
        if self.aliases.has_key(client):
            client = self.aliases[client]
        if self.clients.has_key(client):
            (bundles, groups, categories) = self.groups[self.clients[client]]
        else:
            if self.default == None:
                self.logger.error("Cannot set group for client %s; no default group set" % (client))
                raise MetadataConsistencyError
            [bundles, groups] = self.groups[self.default]
        toolinfo = [self.toolsets[group] for group in groups if self.toolsets.has_key(group)]
        if len(toolinfo) > 1:
            self.logger.error("Found multiple toolsets for client %s; choosing one" % (client))
        elif len(toolinfo) == 0:
            self.logger.error("Cannot determine toolset for client %s" % (client))
            raise MetadataConsistencyError
        toolset = toolinfo[0]
        probed = self.probedata.get(client, {})
        return ClientMetadata(client, groups, bundles, toolset, categories, probed)
        
    def GetProbes(self, _):
        '''Return a set of probes for execution on client'''
        ret = []
        if self.probes:
            bangline = re.compile('^#!(?P<interpreter>(/\w+)+)$')
            for name, entry in [x for x in self.probes.entries.iteritems() if x.data]:
                probe = lxml.etree.Element('probe')
                probe.set('name', name )
                probe.set('source', self.__name__)
                probe.text = entry.data
                match = bangline.match(entry.data.split('\n')[0])
                if match:
                    probe.set('interpreter', match.group('interpreter'))
                else:
                    probe.set('interpreter', '/bin/sh')
                    ret.append(probe)
        return ret

    def ReceiveData(self, client, data):
        '''Receive probe results pertaining to client'''
        try:
            self.probedata[client.hostname].update({ data.get('name'):data.text })
        except KeyError:
            self.probedata[client.hostname] = { data.get('name'):data.text }
