'''This module manages ssh key files for bcfg2'''
__revision__ = '$Revision$'

from binascii import b2a_base64
from os import rename, system
from socket import gethostbyname, gaierror

from Bcfg2.Server.Generator import Generator, DirectoryBacked

class SSHbase(Generator):
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
        Generator.__init__(self, core, datastore)
        self.repository = DirectoryBacked(self.data, self.core.fam)
        self.__provides__ = {'ConfigFile':
                             {'/etc/ssh/ssh_known_hosts':self.build_skn, 
                              '/etc/ssh/ssh_host_dsa_key':self.build_hk,
                              '/etc/ssh/ssh_host_rsa_key':self.build_hk,
                              '/etc/ssh/ssh_host_dsa_key.pub':self.build_hk,
                              '/etc/ssh/ssh_host_rsa_key.pub':self.build_hk,
                              '/etc/ssh/ssh_host_key':self.build_hk,
                              '/etc/ssh/ssh_host_key.pub':self.build_hk}}

    def build_skn(self, entry, metadata):
        '''This function builds builds a host specific known_hosts file'''
        client = metadata.hostname
        filedata = self.repository.entries['ssh_known_hosts'].data
        try:
            ipaddr = gethostbyname(client)
            # add client-specific key lines
            for hostkey in [keytmpl % client for keytmpl in self.pubkeys]:
                filedata += "%s,%s,%s %s" % (client, "%s.mcs.anl.gov"%(client),
                                             ipaddr, self.repository.entries[hostkey].data)
        except gaierror:
            self.LogError("DNS lookup failed for client %s" % client)
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})
        entry.text = filedata

    def build_hk(self, entry, metadata):
        '''This binds host key data into entries'''
        client = metadata.hostname
        filename = "%s.H_%s" % (entry.attrib['name'].split('/')[-1], client)
        if filename not in self.repository.entries.keys():
            self.GenerateHostKeys(client)
            self.GenerateKnownHosts()
        keydata = self.repository.entries[filename].data
        perms = '0600'
        if filename[-4:] == '.pub':
            perms = '0644'
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':perms})
        entry.text = keydata
        if "ssh_host_key.H_" in filename:
            entry.attrib['encoding'] = 'base64'
            entry.text = b2a_base64(keydata)

    def GenerateKnownHosts(self):
        '''Build the static portion of known_hosts (for all hosts)'''
        output = ''
        for filename, entry in self.repository.entries.iteritems():
            if ".pub.H_" in filename:
                hname = filename.split('_')[-1]
                try:
                    ipaddr = gethostbyname(hname)
                    output += "%s,%s.mcs.anl.gov,%s %s" % (hname, hname, ipaddr, entry.data)
                except gaierror:
                    continue
        self.repository.entries['ssh_known_hosts'].data = output

    def GenerateHostKeys(self, client):
        '''Generate new host keys for client'''
        keylist = [keytmpl % client for keytmpl in self.hostkeys]
        for hostkey in keylist:
            if 'ssh_host_rsa_key.H_' in hostkey:
                keytype = 'rsa'
            elif 'ssh_host_dsa_key.H_' in hostkey:
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

