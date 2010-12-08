'''This module manages ssh key files for bcfg2'''
__revision__ = '$Revision$'

import binascii
import os
import socket
import shutil
import tempfile
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin


class SSHbase(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Generator,
              Bcfg2.Server.Plugin.DirectoryBacked,
              Bcfg2.Server.Plugin.PullTarget):
    """
       The sshbase generator manages ssh host keys (both v1 and v2)
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

    """
    name = 'SSHbase'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    pubkeys = ["ssh_host_dsa_key.pub.H_%s",
                "ssh_host_rsa_key.pub.H_%s", "ssh_host_key.pub.H_%s"]
    hostkeys = ["ssh_host_dsa_key.H_%s",
                "ssh_host_rsa_key.H_%s", "ssh_host_key.H_%s"]
    keypatterns = ['ssh_host_dsa_key', 'ssh_host_rsa_key', 'ssh_host_key',
                   'ssh_host_dsa_key.pub', 'ssh_host_rsa_key.pub',
                   'ssh_host_key.pub']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        Bcfg2.Server.Plugin.PullTarget.__init__(self)
        try:
            Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data,
                                                         self.core.fam)
        except OSError, ioerr:
            self.logger.error("Failed to load SSHbase repository from %s" \
                              % (self.data))
            self.logger.error(ioerr)
            raise Bcfg2.Server.Plugin.PluginInitError
        self.Entries = {'Path':
                        {'/etc/ssh/ssh_known_hosts': self.build_skn,
                         '/etc/ssh/ssh_host_dsa_key': self.build_hk,
                         '/etc/ssh/ssh_host_rsa_key': self.build_hk,
                         '/etc/ssh/ssh_host_dsa_key.pub': self.build_hk,
                         '/etc/ssh/ssh_host_rsa_key.pub': self.build_hk,
                         '/etc/ssh/ssh_host_key': self.build_hk,
                         '/etc/ssh/ssh_host_key.pub': self.build_hk}}
        self.ipcache = {}
        self.namecache = {}
        self.__skn = False

    def get_skn(self):
        """Build memory cache of the ssh known hosts file."""
        if not self.__skn:
            self.__skn = "\n".join([value.data for key, value in \
                                    self.entries.iteritems() if \
                                    key.endswith('.static')])
            names = dict()
            # if no metadata is registered yet, defer
            if len(self.core.metadata.query.all()) == 0:
                self.__skn = False
                return self.__skn
            for cmeta in self.core.metadata.query.all():
                names[cmeta.hostname] = set([cmeta.hostname])
                names[cmeta.hostname].update(cmeta.aliases)
                newnames = set()
                newips = set()
                for name in names[cmeta.hostname]:
                    newnames.add(name.split('.')[0])
                    try:
                        newips.add(self.get_ipcache_entry(name)[0])
                    except:
                        continue
                names[cmeta.hostname].update(newnames)
                names[cmeta.hostname].update(cmeta.addresses)
                names[cmeta.hostname].update(newips)
                # TODO: Only perform reverse lookups on IPs if an option is set.
                if True:
                    for ip in newips:
                        try:
                            names[cmeta.hostname].update(self.get_namecache_entry(ip))
                        except:
                            continue
                names[cmeta.hostname] = sorted(names[cmeta.hostname])
            # now we have our name cache
            pubkeys = [pubk for pubk in self.entries.keys() \
                       if pubk.find('.pub.H_') != -1]
            pubkeys.sort()
            badnames = set()
            for pubkey in pubkeys:
                hostname = pubkey.split('H_')[1]
                if hostname not in names:
                    if hostname not in badnames:
                        badnames.add(hostname)
                        self.logger.error("SSHbase: Unknown host %s; ignoring public keys" % hostname)
                    continue
                self.__skn += "%s %s" % (','.join(names[hostname]),
                                         self.entries[pubkey].data)
        return self.__skn

    def set_skn(self, value):
        """Set backing data for skn."""
        self.__skn = value
    skn = property(get_skn, set_skn)

    def HandleEvent(self, event=None):
        """Local event handler that does skn regen on pubkey change."""
        Bcfg2.Server.Plugin.DirectoryBacked.HandleEvent(self, event)
        if event and '_key.pub.H_' in event.filename:
            self.skn = False
        if event and event.filename.endswith('.static'):
            self.skn = False
        if not self.__skn:
            if (len(self.entries.keys())) >= (len(os.listdir(self.data))-1):
                _ = self.skn

    def HandlesEntry(self, entry, _):
        """Handle key entries dynamically."""
        return entry.tag == 'Path' and \
               ([fpat for fpat in self.keypatterns
                 if entry.get('name').endswith(fpat)]
                or entry.get('name').endswith('ssh_known_hosts'))

    def HandleEntry(self, entry, metadata):
        """Bind data."""
        if entry.get('name').endswith('ssh_known_hosts'):
            return self.build_skn(entry, metadata)
        else:
            return self.build_hk(entry, metadata)

    def get_ipcache_entry(self, client):
        """Build a cache of dns results."""
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
                cmd = "getent hosts %s" % client
                ipaddr = Popen(cmd, shell=True, \
                               stdout=PIPE).stdout.read().strip().split()
                if ipaddr:
                    self.ipcache[client] = (ipaddr, client)
                    return (ipaddr, client)
                self.ipcache[client] = False
                self.logger.error("Failed to find IP address for %s" % client)
                raise socket.gaierror

    def get_namecache_entry(self, cip):
        """Build a cache of name lookups from client IP addresses."""
        if cip in self.namecache:
            # lookup cached name from IP
            if self.namecache[cip]:
                return self.namecache[cip]
            else:
                raise socket.gaierror
        else:
            # add an entry that has not been cached
            try:
                rvlookup = socket.gethostbyaddr(cip)
                if rvlookup[0]:
                    self.namecache[cip] = [rvlookup[0]]
                else:
                    self.namecache[cip] = []
                self.namecache[cip].extend(rvlookup[1])
                return self.namecache[cip]
            except socket.gaierror:
                self.namecache[cip] = False
                self.logger.error("Failed to find any names associated with IP address %s" % cip)
                raise

    def build_skn(self, entry, metadata):
        """This function builds builds a host specific known_hosts file."""
        client = metadata.hostname
        entry.text = self.skn
        hostkeys = [keytmpl % client for keytmpl in self.pubkeys \
                        if (keytmpl % client) in self.entries]
        hostkeys.sort()
        for hostkey in hostkeys:
            entry.text += "localhost,localhost.localdomain,127.0.0.1 %s" % (
                self.entries[hostkey].data)
        permdata = {'owner':'root',
                    'group':'root',
                    'type':'file',
                    'perms':'0644'}
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]

    def build_hk(self, entry, metadata):
        """This binds host key data into entries."""
        client = metadata.hostname
        filename = "%s.H_%s" % (entry.get('name').split('/')[-1], client)
        if filename not in self.entries.keys():
            self.GenerateHostKeys(client)
        if not filename in self.entries:
            self.logger.error("%s still not registered" % filename)
            raise Bcfg2.Server.Plugin.PluginExecutionError
        keydata = self.entries[filename].data
        permdata = {'owner':'root',
                    'group':'root',
                    'type':'file',
                    'perms':'0600'}
        if entry.get('name')[-4:] == '.pub':
            permdata['perms'] = '0644'
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]
        if "ssh_host_key.H_" == filename[:15]:
            entry.attrib['encoding'] = 'base64'
            entry.text = binascii.b2a_base64(keydata)
        else:
            entry.text = keydata

    def GenerateHostKeys(self, client):
        """Generate new host keys for client."""
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
                publoc = self.data + '/' + ".".join([hostkey.split('.')[0],
                                                     'pub',
                                                     "H_%s" % client])
                tempdir = tempfile.mkdtemp()
                temploc = "%s/%s" % (tempdir, hostkey)
                cmd = 'ssh-keygen -q -f %s -N "" -t %s -C root@%s < /dev/null'
                os.system(cmd % (temploc, keytype, client))
                shutil.copy(temploc, fileloc)
                shutil.copy("%s.pub" % temploc, publoc)
                self.AddEntry(hostkey)
                self.AddEntry(".".join([hostkey.split('.')[0]]+['pub', "H_%s" \
                                                                % client]))
                try:
                    os.unlink(temploc)
                    os.unlink("%s.pub" % temploc)
                    os.rmdir(tempdir)
                except OSError:
                    self.logger.error("Failed to unlink temporary ssh keys")

    def AcceptChoices(self, _, metadata):
        return [Bcfg2.Server.Plugin.Specificity(hostname=metadata.hostname)]

    def AcceptPullData(self, specific, entry, log):
        """Per-plugin bcfg2-admin pull support."""
        # specific will always be host specific
        filename = "%s/%s.H_%s" % (self.data, entry['name'].split('/')[-1],
                                   specific.hostname)
        open(filename, 'w').write(entry['text'])
        if log:
            print "Wrote file %s" % filename
