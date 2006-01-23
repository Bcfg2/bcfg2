'''This file stores persistent metadata for the BCFG Configuration Repository'''
__revision__ = '$Revision$'

from syslog import syslog, LOG_ERR, LOG_INFO

import lxml.etree, os, time, threading

class MetadataConsistencyError(Exception):
    '''This error gets raised when metadata is internally inconsistent'''
    pass

class MetadataRuntimeError(Exception):
    '''This error is raised when the metadata engine is called prior to reading enough data'''
    pass

class ClientMetadata(object):
    '''This object contains client metadata'''
    def __init__(self, client, groups, bundles, toolset):
        self.hostname = client
        self.bundles = bundles
        self.groups = groups
        self.toolset = toolset

class Metadata:
    '''This class contains data for bcfg2 server metadata'''
    __name__ = 'Metadata'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, fam, datastore):
        self.data = "%s/%s" % (datastore, self.__name__)
        fam.AddMonitor("%s/%s" % (self.data, "groups.xml"), self)
        fam.AddMonitor("%s/%s" % (self.data, "clients.xml"), self)
        self.states = {'groups.xml':False, 'clients.xml':False}
        self.clients = {}
        self.aliases = {}
        self.groups = {}
        self.public = []
        self.profiles = []
        self.toolsets = {}
        self.categories = {}
        self.clientdata = None
        self.default = None

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
            syslog(LOG_ERR, 'Metadata: Failed to parse %s' % (filename))
            return
        if filename == 'clients.xml':
            self.clients = {}
            self.aliases = {}
            self.clientdata = xdata
            for client in xdata.findall('./Client'):
                self.clients.update({client.get('name'): client.get('profile')})
                [self.aliases.update({alias.get('name'): client.get('name')}) for alias in client.findall('Alias')]
        else:
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
                self.groups[group] = ([], [])
                gcategories = []
                tocheck = [group]
                while tocheck:
                    now = tocheck.pop()
                    if now not in self.groups[group][1]:
                        self.groups[group][1].append(now)
                    if grouptmp.has_key(now):
                        (bundles, groups) = grouptmp[now]
                        for ggg in [ggg for ggg in groups if ggg not in self.groups[group][1]]:
                            if not self.categories.has_key(ggg) or (self.categories[ggg] not in gcategories):
                                self.groups[group][1].append(ggg)
                                tocheck.append(ggg)
                            if self.categories.has_key(ggg):
                                gcategories.append(self.categories[ggg])
                        [self.groups[group][0].append(bund) for bund in bundles
                         if bund not in self.groups[group][0]]
        self.states[filename] = True
        if False not in self.states.values():
            # check that all client groups are real and complete
            real = self.groups.keys()
            for client in self.clients.keys():
                if self.clients[client] not in real or self.clients[client] not in self.profiles:
                    syslog(LOG_ERR, "Metadata: Client %s set as nonexistant or incomplete group %s" \
                           % (client, self.clients[client]))
                    syslog(LOG_ERR, "Metadata: Removing client mapping for %s" % (client))
                    del self.clients[client]

    def set_group(self, client, group):
        '''Set group parameter for provided client'''
        if False in self.states.values():
            raise MetadataRuntimeError
        if group not in self.public:
            syslog(LOG_ERR, "Metadata: Failed to set client %s to private group %s" % (client,
                                                                                           group))
            raise MetadataConsistencyError
        if self.clients.has_key(client):
            syslog(LOG_INFO, "Metadata: Changing %s group from %s to %s" % (client,
                                                                                self.clients[client], group))
            cli = self.clientdata.xpath('/Clients/Client[@name="%s"]' % (client))
            cli[0].set('group', group)
        else:
            lxml.etree.SubElement(self.clientdata.getroot(), 'Client', name=client, group=group)
        self.clients[client] = group
        self.write_back_clients()

    def write_back_clients(self):
        '''Write changes to client.xml back to disk'''
        try:
            datafile = open("%s/%s" % (self.data, 'clients.xml'), 'w')
        except IOError:
            syslog(LOG_ERR, "Metadata: Failed to write clients.xml")
            raise MetadataRuntimeError
        datafile.write(lxml.etree.tostring(self.clientdata))
        datafile.close()

    def find_toolset(self, client):
        '''Find the toolset for a given client'''
        tgroups = [self.toolsets[group] for group in self.groups[client][1] if self.toolsets.has_key(group)]
        if len(tgroups) == 1:
            return tgroups[0]
        elif len(tgroups) == 0:
            syslog(LOG_ERR, "Metadata: Couldn't find toolset for client %s" % (client))
            raise MetadataConsistencyError
        else:
            syslog(LOG_ERR, "Metadata: Got goofy toolset result for client %s" % (client))
            raise MetadataConsistencyError

    def get_config_template(self, client):
        '''Build the configuration header for a client configuration'''
        return lxml.etree.Element("Configuration", version='2.0', toolset=self.find_toolset(client))

    def get_metadata(self, client):
        '''Return the metadata for a given client'''
        if self.aliases.has_key(client):
            client = self.aliases[client]
        if self.clients.has_key(client):
            [bundles, groups] = self.groups[self.clients[client]]
        else:
            if self.default == None:
                syslog(LOG_ERR, "Cannot set group for client %s; no default group set" % (client))
                raise MetadataConsistencyError
            [bundles, groups] = self.groups[self.default]
        toolinfo = [self.toolsets[group] for group in groups if self.toolsets.has_key(group)]
        if len(toolinfo) > 1:
            syslog(LOG_ERR, "Metadata: Found multiple toolsets for client %s; choosing one" % (client))
        elif len(toolinfo) == 0:
            syslog(LOG_ERR, "Metadata: Cannot determine toolset for client %s" % (client))
            raise MetadataConsistencyError
        toolset = toolinfo[0]
        return ClientMetadata(client, groups, bundles, toolset)
        
    def ping_sweep_clients(self):
        '''Find live and dead clients'''
        live = {}
        dead = {}
        work = self.clients.keys()
        while work:
            client = work.pop()
            rc = os.system("/bin/ping -w 5 -c 1 %s > /dev/null 2>&1" % client)
            if not rc:
                live[client] = time.time()
            else:
                dead[client] = time.time()
        
