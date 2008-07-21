'''BB Plugin'''

import Bcfg2.Server.Plugin
import lxml.etree
import sys, os
from socket import gethostbyname

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

    def gen_dhcpd(self, entry, metadata):
        '''Generate dhcpd.conf to serve to dhcp server'''
        entry.text = self.entries["static.dhcpd.conf"].data
        for host, data in self.nodes.iteritems():
            entry.text += "host %s {\n" % (host + DOMAIN_SUFFIX)
            if data.has_key('mac') and data.has_key('ip'):
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
            if data.has_key('mac') and data.has_key('ip'):
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
            in users if rdata.has_key("%s.key" % user)])
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
                if host_dict.has_key('user'):
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
        bundles.add(bundle)
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
            bb_tree.write("%s/%s" % (self.data, 'bb.xml'))
        return bundles

    def HandleEvent(self, event=None):
        '''Handle events'''
        Bcfg2.Server.Plugin.DirectoryBacked.HandleEvent(self, event)
        # send events to groups.xml back to Metadata plugin
        if event and "groups.xml" == event.filename:
            Bcfg2.Server.Plugins.Metadata.Metadata.HandleEvent(self, event)
        # handle events to bb.xml
        if event and "bb.xml" == event.filename:
            bb_tree = lxml.etree.parse(self.entries["bb.xml"])
            root = bb_tree.getroot()
            elements = root.findall(".//Node")
            for node in elements:
                host = node.attrib['name']
                node_dict = node.attrib
                if node.findall("Interface"):
                    iface = node.findall("Interface")[0]
                    node_dict['mac'] = iface.attrib['mac']
                    if iface.attrib.has_key('ip'):
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
                elif "bblogin" in host:
                    profile = PROFILE_MAP["bblogin"]
                else:
                    profile = "basic"
                self.clients[full_hostname] = profile
                # get ip address from bb.mxl, if available
                if node_dict.has_key('ip'):
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
                    mac = node_dict['mac'].replace(':','-').lower()
                    linkname = "/tftpboot/pxelinux.cfg/01-%s" % (mac)
                    try:
                        if os.readlink(linkname) != node_dict['action']:
                            os.unlink(linkname)
                            os.symlink(node_dict['action'], linkname)
                    except OSError:
                        self.logger.error("failed to find link for mac address %s" % mac)
                    self.update_dhcpd()
