'''This file stores persistent metadata for the BCFG Configuration Repository'''
__revision__ = '$Revision$'

import lxml.etree, re, socket, time, fcntl, copy
import Bcfg2.Server.Plugin

class MetadataConsistencyError(Exception):
    '''This error gets raised when metadata is internally inconsistent'''
    pass

class MetadataRuntimeError(Exception):
    '''This error is raised when the metadata engine is called prior to reading enough data'''
    pass

probe_matcher = re.compile("(?P<basename>\S+).(?P<mode>[GH])_\S+")

class ClientMetadata(object):
    '''This object contains client metadata'''
    def __init__(self, client, groups, bundles, categories, probed, uuid,
                 password, overall):
        self.hostname = client
        self.bundles = bundles
        self.groups = groups
        self.categories = categories
        self.probes = probed
        self.uuid = uuid
        self.password = password
        self.all = overall

    def inGroup(self, group):
        '''Test to see if client is a member of group'''
        return group in self.groups

class ProbeSet(Bcfg2.Server.Plugin.EntrySet):
    def __init__(self, path, fam, encoding):
        fpattern = '[A-Za-z_\-]+'
        Bcfg2.Server.Plugin.EntrySet.__init__(self, fpattern, path, True, 
                                              Bcfg2.Server.Plugin.SpecificData,
                                              encoding)
        fam.AddMonitor(path, self)
        self.bangline = re.compile('^#!(?P<interpreter>(/\w+)+)$')

    def HandleEvent(self, event):
        if event.filename != self.path:
            return self.handle_event(event)

    def get_probe_data(self, metadata):
        ret = []
        candidates = self.get_matching(metadata)
        temp = {}
        for cand in candidates:
            if cand.specific.all:
                if cand.name not in temp:
                    temp[cand.name] = (cand, 0)
                continue
            mdata = probe_matcher.match(cand.name).groupdict()
            if mdata['basename'] in temp:
                if mdata['mode'] > temp[mdata['basename']][1]:
                    temp[mdata['basename']] = (cand, mdata['mode'])
            else:
                temp[mdata['basename']] = (cand, mdata['mode'])
        
        for (name, data) in temp.iteritems():
            entry, prio = data
            probe = lxml.etree.Element('probe')
            probe.set('name', name.split('/')[-1])
            probe.set('source', "Metadata")
            probe.text = entry.data
            match = self.bangline.match(entry.data.split('\n')[0])
            if match:
                probe.set('interpreter', match.group('interpreter'))
            else:
                probe.set('interpreter', '/bin/sh')
            ret.append(probe)
        return ret


class Metadata(Bcfg2.Server.Plugin.MetadataPlugin,
               Bcfg2.Server.Plugin.ProbingPlugin):
    '''This class contains data for bcfg2 server metadata'''
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __name__ = "Metadata"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.__name__ = 'Metadata'
        try:
            core.fam.AddMonitor("%s/%s" % (self.data, "groups.xml"), self)
            core.fam.AddMonitor("%s/%s" % (self.data, "clients.xml"), self)
        except:
            raise Bcfg2.Server.Plugin.PluginInitError
        self.states = {'groups.xml':False, 'clients.xml':False}
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
        try:
            loc = datastore + "/Probes"
            self.probes = ProbeSet(loc, core.fam, core.encoding)
        except:
            self.probes = False
        self.probedata = {}
        self.extra = {'groups.xml':[], 'clients.xml':[]}
        self.password = core.password
	self.load_probedata()
	
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
                    if self.addresses.has_key(caddr):
                        self.addresses[caddr].append(clname)
                    else:
                        self.addresses[caddr] = [clname]
                if 'uuid' in client.attrib:
                    self.uuid[client.get('uuid')] = clname
                if 'secure' in client.attrib:
                    self.secure.append(clname)
                if client.get('location', 'fixed') == 'floating':
                    self.floating.append(clname)
                if 'password' in client.attrib:
                    self.passwords[clname] = client.get('password')
                for alias in [alias for alias in client.findall('Alias')\
                              if 'address' in alias.attrib]:
                    if self.addresses.has_key(alias.get('address')):
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
	if self.clients.has_key(client):
            self.logger.info("Changing %s group from %s to %s" % (client, self.clients[client], profile))
            cli = self.clientdata.xpath('.//Client[@name="%s"]' % (client))
            cli[0].set('profile', profile)
        else:
            if self.session_cache.has_key(addresspair):
                # we are working with a uuid'd client
                lxml.etree.SubElement(self.clientdata.getroot(),
                                      'Client', name=client,
                                      uuid=client, profile=profile,
                                      address=addresspair[0])
            else:
                lxml.etree.SubElement(self.clientdata.getroot(),
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
        datafile.write(lxml.etree.tostring(self.clientdata_original.getroot()))
        fcntl.lockf(fd, fcntl.LOCK_UN)
        datafile.close()
    
    def locked(self, fd):
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            return True
        return False
    
    def write_probedata(self):
        '''write probe data out for use with bcfg2-info'''
        if self.pdirty:
            top = lxml.etree.Element("Probed")
            for client, probed in self.probedata.iteritems():
                cx = lxml.etree.SubElement(top, 'Client', name=client)
                for probe in probed:
                    lxml.etree.SubElement(cx, 'Probe', name=probe,
                                          value=self.probedata[client][probe])
                for group in self.cgroups[client]:
                    lxml.etree.SubElement(cx, "Group", name=group)
            data = lxml.etree.tostring(top, encoding='UTF-8', xml_declaration=True)
            try:
                datafile = open("%s/%s" % (self.data, 'probed.xml'), 'w')
            except IOError:
                self.logger.error("Failed to write probed.xml")
                raise MetadataRuntimeError
            datafile.write(data)
            self.pdirty = False

    def load_probedata(self):
        try:
            data = lxml.etree.parse(self.data + '/probed.xml').getroot()
        except:
            self.logger.error("Failed to read file probed.xml")
            return
        self.probedata = {}
        self.cgroups = {}
        for client in data.getchildren():
            self.probedata[client.get('name')] = {}
            self.cgroups[client.get('name')]=[]
            for pdata in client:
                if (pdata.tag == 'Probe'):
                    self.probedata[client.get('name')][pdata.get('name')] = pdata.get('value')
                elif (pdata.tag == 'Group'):
                    self.cgroups[client.get('name')].append(pdata.get('name'))

    def resolve_client(self, addresspair):
        '''Lookup address locally or in DNS to get a hostname'''
        #print self.session_cache
        if self.session_cache.has_key(addresspair):
            (stamp, uuid) = self.session_cache[addresspair]
            if time.time() - stamp < 60:
                return self.uuid[uuid]
        address = addresspair[0]
        if self.addresses.has_key(address):
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
    
    def get_metadata(self, client):
        '''Return the metadata for a given client'''
        client = client.lower()
        if self.aliases.has_key(client):
            client = self.aliases[client]
        if self.clients.has_key(client):
            (bundles, groups, categories) = self.groups[self.clients[client]]
        else:
            if self.default == None:
                self.logger.error("Cannot set group for client %s; no default group set" % (client))
                raise MetadataConsistencyError
            self.set_profile(client, self.default, (None, None))
            [bundles, groups, categories] = self.groups[self.default]
        probed = self.probedata.get(client, {})
        newgroups = groups[:]
        newbundles = bundles[:]
        newcategories = {}
        newcategories.update(categories)
        if self.passwords.has_key(client):
            password = self.passwords[client]
        else:
            password = None
        uuids = [item for item, value in self.uuid.iteritems() if value == client]
        if uuids:
            uuid = uuids[0]
        else:
            uuid = None
        for group in self.cgroups.get(client, []):
            if self.groups.has_key(group):
                nbundles, ngroups, ncategories = self.groups[group]
            else:
                nbundles, ngroups, ncategories = ([], [group], {})
            [newbundles.append(b) for b in nbundles if b not in newbundles]
            [newgroups.append(g) for g in ngroups if g not in newgroups]
            newcategories.update(ncategories)
        groupscopy = copy.deepcopy(self.groups)
        profilescopy = copy.deepcopy(self.profiles)
        return ClientMetadata(client, newgroups, newbundles, newcategories,
                              probed, uuid, password, (groupscopy, profilescopy))
        
    def GetProbes(self, meta, force=False):
        '''Return a set of probes for execution on client'''
        if self.probes:
            return self.probes.get_probe_data(meta)
        return []

    def ReceiveData(self, client, datalist):
        self.cgroups[client.hostname] = []
        self.probedata[client.hostname] = {}
        for data in datalist:
            self.ReceiveDataItem(client, data)
        self.pdirty = True
        self.write_probedata()

    def ReceiveDataItem(self, client, data):
        '''Receive probe results pertaining to client'''
        if not self.cgroups.has_key(client.hostname):
            self.cgroups[client.hostname] = []
        if data.text == None:
            self.logger.error("Got null response to probe %s from %s" % \
                              (data.get('name'), client.hostname))
            try:
                self.probedata[client.hostname].update({data.get('name'): ''})
            except KeyError:
                self.probedata[client.hostname] = {data.get('name'): ''}
            return
        dlines = data.text.split('\n')
        self.logger.debug("%s:probe:%s:%s" % (client.hostname, 
            data.get('name'), [line.strip() for line in dlines]))
        for line in dlines[:]:
            if line.split(':')[0] == 'group':
                newgroup = line.split(':')[1].strip()
                if newgroup not in self.cgroups[client.hostname]:
                    self.cgroups[client.hostname].append(newgroup)
                dlines.remove(line)
        dtext = "\n".join(dlines)
        try:
            self.probedata[client.hostname].update({ data.get('name'):dtext })
        except KeyError:
            self.probedata[client.hostname] = { data.get('name'):dtext }

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
            if self.passwords.has_key(client):
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
