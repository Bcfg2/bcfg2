'''BB Plugin'''

import Bcfg2.Server.Plugin
import lxml.etree
import os, fcntl
from socket import gethostbyname
from Bcfg2.Server.Plugins.Metadata import MetadataConsistencyError

# map of keywords to profiles
# probably need a better way to do this
PROFILE_MAP = {"ubuntu-i386":"compute-node", 
               "ubuntu-amd64":"compute-node-amd64",
               "fc6":"fc6-compute-node",
               "peta":"pvfs-server",
               "bbsto":"fileserver",
               "bblogin":"head-node"}

DOMAIN_SUFFIX = ".mcs.anl.gov" # default is .mcs.anl.gov

PXE_CONFIG = "pxelinux.0" # default is pxelinux.0

class BB(Bcfg2.Server.Plugin.GeneratorPlugin,
         Bcfg2.Server.Plugin.StructurePlugin,
         Bcfg2.Server.Plugins.Metadata.Metadata,
         Bcfg2.Server.Plugin.DirectoryBacked):
    '''BB Plugin handles bb node configuration'''
    
    __name__ = 'BB'
    experimental = True
    write_to_disk = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.GeneratorPlugin.__init__(self, core, datastore)
        try:
            Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data, self.core.fam)
        except OSError, ioerr:
            self.logger.error("Failed to load BB repository from %s" % (self.data))
            self.logger.error(ioerr)
            raise Bcfg2.Server.Plugin.PluginInitError
        Bcfg2.Server.Plugins.Metadata.Metadata.__init__(self, core, datastore, False)
        self.Entries = {'ConfigFile':{'/etc/security/limits.conf':self.gen_limits,
            '/root/.ssh/authorized_keys':self.gen_root_keys,
            '/etc/sudoers':self.gen_sudoers,
            '/etc/dhcp3/dhcpd.conf':self.gen_dhcpd}}
        self.nodes = {}
	self.dhcpd_loaded = False
	self.need_update = False
    
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

    def remove_client(self, client_name):
        '''Remove client from bb.xml'''
        bb_tree = lxml.etree.parse(self.data + "/bb.xml")
        root = bb_tree.getroot()
        if DOMAIN_SUFFIX in client_name:
            client_name = client_name.split('.')[0]
        if len(root.xpath(".//Node[@name='%s']" % client_name)) != 1:
            self.logger.error("Client \"%s\" does not exist" % client_name)
            raise MetadataConsistencyError
        else:
            root.remove(root.xpath(".//Node[@name='%s']" % client_name)[0])
        self.write_metadata(bb_tree)

    def add_client(self, client_name, attribs):
        '''Add a client to bb.xml'''
        bb_tree = lxml.etree.parse(self.data + "/bb.xml")
        root = bb_tree.getroot()
        if DOMAIN_SUFFIX in client_name:
            client_name = client_name.split('.')[0]
        if len(root.xpath(".//Node[@name='%s']" % client_name)) != 0:
            self.logger.error("Client \"%s\" already exists" % client_name)
            raise MetadataConsistencyError
        else:
            element = lxml.etree.Element("Client", name=client_name)
            for key, val in attribs.iteritems():
                element.set(key, val)
            root.append(element)
        self.write_metadata(bb_tree)

    def write_metadata(self, tree):
        '''write metadata back to bb.xml'''
        data_file = open(self.data + "/bb.xml","w")
        fd = data_file.fileno()
        while True:
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                continue
            else:
                break
        tree.write(data_file)
        fcntl.lockf(fd, fcntl.LOCK_UN)
        data_file.close()

    def gen_dhcpd(self, entry, metadata):
        '''Generate dhcpd.conf to serve to dhcp server'''
        entry.text = self.entries["static.dhcpd.conf"].data
        for host, data in self.nodes.iteritems():
            entry.text += "host %s {\n" % (host + DOMAIN_SUFFIX)
            if 'mac' in data and 'ip' in data:
                entry.text += " hardware ethernet %s;\n" % (data['mac'])
                entry.text += " fixed-address %s;\n" % (data['ip'])
                entry.text += " filename \"%s\";\n}\n" % (PXE_CONFIG)
            else:
                self.logger.error("incomplete client data")
        perms = {'owner':'root', 'group':'root', 'perms':'0600'}
        [entry.attrib.__setitem__(key, value) for (key, value)
            in perms.iteritems()]

    def update_dhcpd(self):
        '''Upadte dhcpd.conf if bcfg2 server is also the bcfg2 server'''
        entry = self.entries["static.dhcpd.conf"].data
        for host, data in self.nodes.iteritems():
            entry += "host %s {\n" % (host + DOMAIN_SUFFIX)
            if 'mac' in data and 'ip' in data:
                entry += " hardware ethernet %s;\n" % (data['mac'])
                entry += " fixed-address %s;\n" % (data['ip'])
                entry += " filename \"%s\";\n}\n" % (PXE_CONFIG)
            else:
                self.logger.error("incomplete client data")
        dhcpd = open("/etc/dhcp3/dhcpd.conf",'w')
        dhcpd.write(entry)
        dhcpd.close()
    
    def gen_root_keys(self, entry, metadata):
        '''Build /root/.ssh/authorized_keys entry'''
        users = self.get_users(metadata)
        rdata = self.entries
        entry.text = "".join([rdata["%s.key" % user].data for user
            in users if ("%s.key" % user) in rdata])
        perms = {'owner':'root', 'group':'root', 'perms':'0600'}
        [entry.attrib.__setitem__(key, value) for (key, value)
            in perms.iteritems()]
        
    def gen_sudoers(self, entry, metadata):
        '''Build /etc/sudoers entry'''
        users = self.get_users(metadata)
        entry.text = self.entries['static.sudoers'].data
        entry.text += "".join(["%s ALL=(ALL) ALL\n" % user
            for user in users])
        perms = {'owner':'root', 'group':'root', 'perms':'0440'}
        [entry.attrib.__setitem__(key, value) for (key, value)
            in perms.iteritems()]

    def gen_limits(self, entry, metadata):
        '''Build /etc/security/limits.conf entry'''
        users = self.get_users(metadata)
        entry.text = self.entries["static.limits.conf"].data
        perms = {'owner':'root', 'group':'root', 'perms':'0600'}
        [entry.attrib.__setitem__(key, value) for (key, value) in perms.iteritems()]
        entry.text += "".join(["%s hard maxlogins 1024\n" % uname for uname in users])
        if "*" not in users:
            entry.text += "* hard maxlogins 0\n"
    
    def get_users(self, metadata):
        '''Get users associated with a specific host'''
        users = []
        for host, host_dict in self.nodes.iteritems():
            if host == metadata.hostname.split('.')[0]:
                if 'user' in host_dict:
                    if host_dict['user'] != "none":
                        users.append(host_dict['user'])
        return users

    def BuildStructures(self, metadata):
        '''Update build/boot state and create bundle for server'''
        try:
            host_attr = self.nodes[metadata.hostname.split('.')[0]]
        except KeyError:
            self.logger.error("failed to find metadata for host %s" 
                % metadata.hostname)
            return []
        bundles = []
        # create symlink and dhcp bundle
        bundle = lxml.etree.Element('Bundle', name='boot-server')
        for host, data in self.nodes.iteritems():
            link = lxml.etree.Element('BoundSymLink')
            link.attrib['name'] = "01-%s" % (data['mac'].replace(':','-').lower())
            link.attrib['to'] = data['action']
            bundle.append(link)
        dhcpd = lxml.etree.Element('BoundConfigFile', name='/etc/dhcp3/dhcpd.conf')
        bundle.append(dhcpd)
        bundles.append(bundle)
        # toggle build/boot in bb.xml
        if host_attr['action'].startswith("build"):
            # make new action string
            action = ""
            if host_attr['action'] == "build":
                action = "boot"
            else:
                action = host_attr['action'].replace("build", "boot", 1)
            # write changes to file
            bb_tree = lxml.etree.parse(self.entries["bb.xml"])
            nodes = bb_tree.getroot().findall(".//Node")
            for node in nodes:
                if node.attrib['name'] == metadata.hostname.split('.')[0]:
                    node.attrib['action'] = action
                    break
            self.write_metadata(bb_tree)
        return bundles

    def HandleEvent(self, event=None):
        '''Handle events'''
        Bcfg2.Server.Plugin.DirectoryBacked.HandleEvent(self, event)
	# static.dhcpd.conf hack
	if 'static.dhcpd.conf' in self.entries:
	    self.dhcpd_loaded = True
	if self.need_update and self.dhcpd_loaded:
	    self.update_dhcpd()
	    self.need_update = False	
        # send events to groups.xml back to Metadata plugin
        if event and "groups.xml" == event.filename:
            Bcfg2.Server.Plugins.Metadata.Metadata.HandleEvent(self, event)
        # handle events to bb.xml
        if event and "bb.xml" == event.filename:
            bb_tree = lxml.etree.parse("%s/%s" % (self.data, event.filename))
            root = bb_tree.getroot()
            elements = root.findall(".//Node")
            for node in elements:
                host = node.attrib['name']
                node_dict = node.attrib
                if node.findall("Interface"):
                    iface = node.findall("Interface")[0]
                    node_dict['mac'] = iface.attrib['mac']
                    if 'ip' in iface.attrib:
                        node_dict['ip'] = iface.attrib['ip']
                # populate self.clients dict
                full_hostname = host + DOMAIN_SUFFIX
                profile = ""
                # need to translate image/action into profile name
                if "ubuntu" in node_dict['action']:
                    if "amd64" in node_dict['action']:
                        profile = PROFILE_MAP["ubuntu-amd64"]
                    else:
                        profile = PROFILE_MAP["ubuntu-i386"]
                elif "fc6" in node_dict['action']:
                    profile = PROFILE_MAP["fc6"]
                elif "peta" in host:
                    profile = PROFILE_MAP["peta"]
                elif "bbsto" in host:
                    profile = PROFILE_MAP["bbsto"]
                elif "login" in host:
                    profile = PROFILE_MAP["bblogin"]
                else:
                    profile = "basic"
                self.clients[full_hostname] = profile
                # get ip address from bb.mxl, if available
                if 'ip' in node_dict:
                    ip = node_dict['ip']
                    self.addresses[ip] = [host]
                else:
                    try:
                        node_dict['ip'] = gethostbyname(full_hostname)
                    except:
                        self.logger.error("failed to resolve host %s" % full_hostname)
                self.nodes[host] = node_dict
                # update symlinks and /etc/dhcp3/dhcpd.conf
                if self.write_to_disk:
                    if not 'mac' in node_dict:
                        self.logger.error("no mac address for %s" % host)
                        continue
                    mac = node_dict['mac'].replace(':','-').lower()
                    linkname = "/tftpboot/pxelinux.cfg/01-%s" % (mac)
                    try:
                        if os.readlink(linkname) != node_dict['action']:
                            os.unlink(linkname)
                            os.symlink(node_dict['action'], linkname)
                    except OSError:
                        self.logger.error("failed to find link for mac address %s" % mac)
                    if self.dhcpd_loaded:
		    	self.update_dhcpd()
		    else:
			self.need_update = True			
