'''This module manages ssh key files for bcfg2'''
__revision__ = '$Revision$'

import binascii, os, socket, tempfile
import Bcfg2.Server.Plugin

class SSHbase(Bcfg2.Server.Plugin.GeneratorPlugin,  Bcfg2.Server.Plugin.DirectoryBacked):
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
    keypatterns = ['ssh_host_dsa_key', 'ssh_host_rsa_key', 'ssh_host_key',
                   'ssh_host_dsa_key.pub', 'ssh_host_rsa_key.pub', 'ssh_host_key.pub']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        try:
            Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data, self.core.fam)
        except OSError, ioerr:
            self.logger.error("Failed to load SSHbase repository from %s" % (self.data))
            self.logger.error(ioerr)
            raise Bcfg2.Server.Plugin.PluginInitError
        self.Entries = {'ConfigFile':
                        {'/etc/ssh/ssh_known_hosts':self.build_skn, 
                         '/etc/ssh/ssh_host_dsa_key':self.build_hk,
                         '/etc/ssh/ssh_host_rsa_key':self.build_hk,
                         '/etc/ssh/ssh_host_dsa_key.pub':self.build_hk,
                         '/etc/ssh/ssh_host_rsa_key.pub':self.build_hk,
                         '/etc/ssh/ssh_host_key':self.build_hk,
                         '/etc/ssh/ssh_host_key.pub':self.build_hk}}
        self.ipcache = {}
        self.__skn = False

    def get_skn(self):
        '''build memory cache of the ssh known hosts file'''
        if not self.__skn:
            static_entries = [key for key in self.entries \
                              if key.endswith('.static')]
            if static_entries:
                self.__skn = "\n".join([self.entries[key].data for \
                                        key in static_entries])
            else:
                self.__skn = ''
            pubkeys = [pubk for pubk in self.entries.keys() \
                       if pubk.find('.pub.H_') != -1]
            pubkeys.sort()
            for pubkey in pubkeys:
                hostname = pubkey.split('H_')[1]
                try:
                    (ipaddr, fqdn) = self.get_ipcache_entry(hostname)
                except socket.gaierror:
                    continue
                shortname = hostname.split('.')[0]
                self.__skn += "%s,%s,%s %s" % (shortname, fqdn, ipaddr,
                                               self.entries[pubkey].data)
        return self.__skn

    def set_skn(self, value):
        '''Set backing data for skn'''
        self.__skn = value
    skn = property(get_skn, set_skn)

    def HandleEvent(self, event=None):
        '''Local event handler that does skn regen on pubkey change'''
        Bcfg2.Server.Plugin.DirectoryBacked.HandleEvent(self, event)
        if event and '_key.pub.H_' in event.filename:
            self.skn = False
        if event and event.filename.endswith('.static'):
            self.skn = False
        if not self.skn:
            if (len(self.entries.keys())) > (0.95 * len(os.listdir(self.data))):
                a = self.skn

    def HandlesEntry(self, entry):
        '''Handle key entries dynamically'''
        return entry.tag == 'ConfigFile' and \
               ([fpat for fpat in self.keypatterns
                 if entry.get('name').endswith(fpat)]
                or entry.get('name').endswith('ssh_known_hosts'))

    def HandleEntry(self, entry, metadata):
        '''Bind data'''
        if entry.get('name').endswith('ssh_known_hosts'):
            return self.build_skn(entry, metadata)
        else:
            return self.build_hk(entry, metadata)

    def get_ipcache_entry(self, client):
        '''build a cache of dns results'''
        if client in self.ipcache:
            if self.ipcache[client]:
                return self.ipcache[client]
            else:
                raise socket.gaierror
        else:
            # need to add entry
            try:
                ipaddr = socket.gethostbyname(client)
                self.ipcache[client] = (ipaddr, client)
                return (ipaddr, client)
            except socket.gaierror:
                ipaddr = os.popen("getent hosts %s" % client).read().strip().split()
                if ipaddr:
                    self.ipcache[client] = (ipaddr, client)
                    return (ipaddr, client)
                self.ipcache[client] = False
                self.logger.error("Failed to find IP address for %s" % client)
                raise socket.gaierror

    def build_skn(self, entry, metadata):
        '''This function builds builds a host specific known_hosts file'''
        client = metadata.hostname
        entry.text = self.skn
        hostkeys = [keytmpl % client for keytmpl in self.pubkeys \
                        if (keytmpl % client) in self.entries]
        hostkeys.sort()
        for hostkey in hostkeys:
            entry.text += "localhost,localhost.localdomain,127.0.0.1 %s" % (
                self.entries[hostkey].data)
        permdata = {'owner':'root', 'group':'root', 'perms':'0644'}
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]

    def build_hk(self, entry, metadata):
        '''This binds host key data into entries'''
        client = metadata.hostname
        filename = "%s.H_%s" % (entry.get('name').split('/')[-1], client)
        if filename not in self.entries.keys():
            self.GenerateHostKeys(client)
        if not filename in self.entries:
            self.logger.error("%s still not registered" % filename)
            raise Bcfg2.Server.Plugin.PluginExecutionError
        keydata = self.entries[filename].data
        permdata = {'owner':'root', 'group':'root'}
        permdata['perms'] = '0600'
        if entry.get('name')[-4:] == '.pub':
            permdata['perms'] = '0644'
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]
        if "ssh_host_key.H_" == filename[:15]:
            entry.attrib['encoding'] = 'base64'
            entry.text = binascii.b2a_base64(keydata)
        else:
            entry.text = keydata

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

            if hostkey not in self.entries.keys():
                fileloc = "%s/%s" % (self.data, hostkey)
                publoc = self.data + '/' + ".".join([hostkey.split('.')[0]]+['pub', "H_%s" % client])
                tempdir = tempfile.mkdtemp()
                temploc = "%s/%s" % (tempdir, hostkey)
                os.system('ssh-keygen -q -f %s -N "" -t %s -C root@%s < /dev/null' %
                          (temploc, keytype, client))
                open(fileloc, 'w').write(open(temploc).read())
                open(publoc, 'w').write(open("%s.pub" % temploc).read())
                self.AddEntry(hostkey)
                self.AddEntry(".".join([hostkey.split('.')[0]]+['pub', "H_%s" % client]))
                try:
                    os.unlink(temploc)
                    os.unlink("%s.pub" % temploc)
                    os.rmdir(tempdir)
                except OSError:
                    self.logger.error("Failed to unlink temporary ssh keys")

    def AcceptChoices(self, _, metadata):
        return [Bcfg2.Server.Plugin.Specificity(hostname=metadata.hostname)]

    def AcceptPullData(self, specific, entry, log):
        '''per-plugin bcfg2-admin pull support'''
        # specific will always be host specific
        filename = "%s/%s.H_%s" % (self.data, entry['name'].split('/')[-1],
                                   specific.hostname)
        open(filename, 'w').write(entry['text'])
        if log:
            print "Wrote file %s" % filename
