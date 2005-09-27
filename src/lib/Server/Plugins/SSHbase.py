'''This module manages ssh key files for bcfg2'''
__revision__ = '$Revision$'

from binascii import b2a_base64
from os import rename, system, popen
from socket import gethostbyname, gaierror

from Bcfg2.Server.Plugin import Plugin, DirectoryBacked

class SSHbase(Plugin):
    '''The sshbase generator manages ssh host keys (both v1 and v2)
    for hosts.  It also manages the ssh_known_hosts file. It can
    integrate host keys from other management domains and similarly
    export its keys. The repository contains files in the following
    formats:

    ssh_host_key.H_(hostname) -> the v1 host private key for
      (hostname)
    ssh_host_key.pub.H_(hostname) -> the v1 host public key
      for (hostname)
    ssh_host_(dr)sa_key.H_(hostname) -> the v2 ssh host
      private key for (hostname)
    ssh_host_(dr)sa_key.pub.H_(hostname) -> the v2 ssh host
      public key for (hostname)
    ssh_known_hosts -> the current known hosts file. this
      is regenerated each time a new key is generated.
'''
    __name__ = 'SSHbase'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    pubkeys = ["ssh_host_dsa_key.pub.H_%s",
                "ssh_host_rsa_key.pub.H_%s", "ssh_host_key.pub.H_%s"]
    hostkeys = ["ssh_host_dsa_key.H_%s",
                "ssh_host_rsa_key.H_%s", "ssh_host_key.H_%s"]

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        self.repository = DirectoryBacked(self.data, self.core.fam)
        try:
            prefix = open("%s/prefix" % (self.data)).read().strip()
        except IOError:
            prefix = ''
        self.Entries = {'ConfigFile':
                             {prefix + '/etc/ssh/ssh_known_hosts':self.build_skn, 
                              prefix + '/etc/ssh/ssh_host_dsa_key':self.build_hk,
                              prefix + '/etc/ssh/ssh_host_rsa_key':self.build_hk,
                              prefix + '/etc/ssh/ssh_host_dsa_key.pub':self.build_hk,
                              prefix + '/etc/ssh/ssh_host_rsa_key.pub':self.build_hk,
                              prefix + '/etc/ssh/ssh_host_key':self.build_hk,
                              prefix + '/etc/ssh/ssh_host_key.pub':self.build_hk}}
        self.ipcache = {}

    def get_ipcache_entry(self, client):
        '''build a cache of dns results'''
        if self.ipcache.has_key(client):
            return self.ipcache[client]
        else:
            # need to add entry
            try:
                ipaddr = gethostbyname(client)
                self.ipcache[client] = (ipaddr, client)
                return (ipaddr, client)
            except gaierror:
                pass
        ipaddr = popen("getent hosts %s" % client).read().strip().split()
        if ipaddr:
            self.ipcache[client] = (ipaddr, client)
            return (ipaddr, client)
        self.LogError("Failed to find IP address for %s" % client)
        raise gaierror

    def cache_skn(self):
        '''build memory cache of the ssh known hosts file'''
        self.static_skn = ''
        for pubkey in [pubk for pubk in self.repository.entries.keys() if pubk.find('.pub.H_') != -1]:
            hostname = pubkey.split('H_')[1]
            try:
                (ipaddr, fqdn) = self.get_ipcache_entry(hostname)
            except gaierror:
                continue
            shortname = hostname.split('.')[0]
            self.static_skn += "%s,%s,%s %s" % (shortname, fqdn, ipaddr,
                                         self.repository.entries[pubkey].data)

    def build_skn(self, entry, metadata):
        '''This function builds builds a host specific known_hosts file'''
        client = metadata.hostname
        if not hasattr(self, 'static_skn'):
            self.cache_skn()
        entry.text = self.static_skn
        for hostkey in [keytmpl % client for keytmpl in self.pubkeys]:
            entry.text += "localhost,localhost.localdomain,127.0.0.1 %s" % (
                self.repository.entries[hostkey].data)
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})

    def build_hk(self, entry, metadata):
        '''This binds host key data into entries'''
        client = metadata.hostname
        filename = "%s.H_%s" % (entry.get('name').split('/')[-1], client)
        if filename not in self.repository.entries.keys():
            self.GenerateHostKeys(client)
            if hasattr(self, 'static_skn'):
                del self.static_skn
        keydata = self.repository.entries[filename].data
        perms = '0600'
        if entry.get('name')[-4:] == '.pub':
            perms = '0644'
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':perms})
        entry.text = keydata
        if "ssh_host_key.H_" == filename[:15]:
            entry.attrib['encoding'] = 'base64'
            entry.text = b2a_base64(keydata)

    def GenerateHostKeys(self, client):
        '''Generate new host keys for client'''
        keylist = [keytmpl % client for keytmpl in self.hostkeys]
        for hostkey in keylist:
            if 'ssh_host_rsa_key.H_' == hostkey[:19]:
                keytype = 'rsa'
            elif 'ssh_host_dsa_key.H_' == hostkey[:19]:
                keytype = 'dsa'
            else:
                keytype = 'rsa1'

            if hostkey not in self.repository.entries.keys():
                fileloc = "%s/%s" % (self.data, hostkey)
                system('ssh-keygen -q -f %s -N "" -t %s -C root@%s < /dev/null' % (fileloc, keytype, client))
                rename("%s.pub"%(fileloc),"%s/" %
                       (self.data, )+".".join(hostkey.split('.')[:-1]+['pub']+[hostkey.split('.')[-1]]))
                self.repository.AddEntry(hostkey)
                self.repository.AddEntry("%s.pub"%(hostkey))

