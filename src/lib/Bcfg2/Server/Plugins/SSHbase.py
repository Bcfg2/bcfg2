"""This module manages ssh key files for bcfg2"""

import re
import os
import sys
import socket
import shutil
import logging
import tempfile
from itertools import chain
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Compat import any, u_str, b64encode  # pylint: disable=W0622

LOGGER = logging.getLogger(__name__)


class KeyData(Bcfg2.Server.Plugin.SpecificData):
    """ class to handle key data for HostKeyEntrySet """

    def __init__(self, name, specific, encoding):
        Bcfg2.Server.Plugin.SpecificData.__init__(self,
                                                  name,
                                                  specific,
                                                  encoding)
        self.encoding = encoding

    def __lt__(self, other):
        return self.name < other.name

    def bind_entry(self, entry, _):
        """ Bind the entry with the data of this key

        :param entry: The abstract entry to bind.  This will be
                      modified in place.
        :type entry: lxml.etree._Element
        :returns: None
        """
        entry.set('type', 'file')
        if entry.get('encoding') == 'base64':
            entry.text = b64encode(self.data)
        else:
            try:
                entry.text = u_str(self.data, self.encoding)
            except UnicodeDecodeError:
                msg = "Failed to decode %s: %s" % (entry.get('name'),
                                                   sys.exc_info()[1])
                LOGGER.error(msg)
                LOGGER.error("Please verify you are using the proper encoding")
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            except ValueError:
                msg = "Error in specification for %s: %s" % (entry.get('name'),
                                                             sys.exc_info()[1])
                LOGGER.error(msg)
                LOGGER.error("You need to specify base64 encoding for %s" %
                             entry.get('name'))
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        if entry.text in ['', None]:
            entry.set('empty', 'true')


class HostKeyEntrySet(Bcfg2.Server.Plugin.EntrySet):
    """ EntrySet to handle all kinds of host keys """
    def __init__(self, basename, path):
        if basename.startswith("ssh_host_key"):
            encoding = "base64"
        else:
            encoding = None
        Bcfg2.Server.Plugin.EntrySet.__init__(self, basename, path, KeyData,
                                              encoding)
        self.metadata = {'owner': 'root',
                         'group': 'root',
                         'type': 'file'}
        if encoding is not None:
            self.metadata['encoding'] = encoding
        if basename.endswith('.pub'):
            self.metadata['mode'] = '0644'
        else:
            self.metadata['mode'] = '0600'


class KnownHostsEntrySet(Bcfg2.Server.Plugin.EntrySet):
    """ EntrySet to handle the ssh_known_hosts file """
    def __init__(self, path):
        Bcfg2.Server.Plugin.EntrySet.__init__(self, "ssh_known_hosts", path,
                                              KeyData, None)
        self.metadata = {'owner': 'root',
                         'group': 'root',
                         'type': 'file',
                         'mode': '0644'}


class SSHbase(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Generator,
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
       ssh_host_(ec)(dr)sa_key.H_(hostname) -> the v2 ssh host
         private key for (hostname)
       ssh_host_(ec)(dr)sa_key.pub.H_(hostname) -> the v2 ssh host
         public key for (hostname)
       ssh_known_hosts -> the current known hosts file. this
         is regenerated each time a new key is generated.

    """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    keypatterns = ["ssh_host_dsa_key",
                   "ssh_host_ecdsa_key",
                   "ssh_host_rsa_key",
                   "ssh_host_key",
                   "ssh_host_dsa_key.pub",
                   "ssh_host_ecdsa_key.pub",
                   "ssh_host_rsa_key.pub",
                   "ssh_host_key.pub"]

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        Bcfg2.Server.Plugin.PullTarget.__init__(self)
        self.ipcache = {}
        self.namecache = {}
        self.__skn = False

        # keep track of which bogus keys we've warned about, and only
        # do so once
        self.badnames = dict()

        core.fam.AddMonitor(self.data, self)

        self.static = dict()
        self.entries = dict()
        self.Entries['Path'] = dict()

        self.entries['/etc/ssh/ssh_known_hosts'] = \
            KnownHostsEntrySet(self.data)
        self.Entries['Path']['/etc/ssh/ssh_known_hosts'] = self.build_skn
        for keypattern in self.keypatterns:
            self.entries["/etc/ssh/" + keypattern] = \
                HostKeyEntrySet(keypattern, self.data)
            self.Entries['Path']["/etc/ssh/" + keypattern] = self.build_hk

    def get_skn(self):
        """Build memory cache of the ssh known hosts file."""
        if not self.__skn:
            # if no metadata is registered yet, defer
            if len(self.core.metadata.query.all()) == 0:
                self.__skn = False
                return self.__skn

            skn = [s.data.rstrip()
                   for s in list(self.static.values())]

            mquery = self.core.metadata.query

            # build hostname cache
            names = dict()
            for cmeta in mquery.all():
                names[cmeta.hostname] = set([cmeta.hostname])
                names[cmeta.hostname].update(cmeta.aliases)
                newnames = set()
                newips = set()
                for name in names[cmeta.hostname]:
                    newnames.add(name.split('.')[0])
                    try:
                        newips.update(self.get_ipcache_entry(name)[0])
                    except:  # pylint: disable=W0702
                        continue
                names[cmeta.hostname].update(newnames)
                names[cmeta.hostname].update(cmeta.addresses)
                names[cmeta.hostname].update(newips)
                # TODO: Only perform reverse lookups on IPs if an
                # option is set.
                if True:
                    for ip in newips:
                        try:
                            names[cmeta.hostname].update(
                                self.get_namecache_entry(ip))
                        except:  # pylint: disable=W0702
                            continue
                names[cmeta.hostname] = sorted(names[cmeta.hostname])

            pubkeys = [pubk for pubk in list(self.entries.keys())
                       if pubk.endswith('.pub')]
            pubkeys.sort()
            for pubkey in pubkeys:
                for entry in sorted(self.entries[pubkey].entries.values(),
                                    key=lambda e: (e.specific.hostname or
                                                   e.specific.group)):
                    specific = entry.specific
                    hostnames = []
                    if specific.hostname and specific.hostname in names:
                        hostnames = names[specific.hostname]
                    elif specific.group:
                        hostnames = list(
                            chain(
                                *[names[cmeta.hostname]
                                  for cmeta in
                                  mquery.by_groups([specific.group])]))
                    elif specific.all:
                        # a generic key for all hosts?  really?
                        hostnames = list(chain(*list(names.values())))
                    if not hostnames:
                        if specific.hostname:
                            key = specific.hostname
                            ktype = "host"
                        elif specific.group:
                            key = specific.group
                            ktype = "group"
                        else:
                            # user has added a global SSH key, but
                            # have no clients yet.  don't warn about
                            # this.
                            continue

                        if key not in self.badnames:
                            self.badnames[key] = True
                            self.logger.info("Ignoring key for unknown %s %s" %
                                             (ktype, key))
                        continue

                    skn.append("%s %s" % (','.join(hostnames),
                                          entry.data.rstrip()))

            self.__skn = "\n".join(skn) + "\n"
        return self.__skn

    def set_skn(self, value):
        """Set backing data for skn."""
        self.__skn = value
    skn = property(get_skn, set_skn)

    def HandleEvent(self, event=None):
        """Local event handler that does skn regen on pubkey change."""
        # skip events we don't care about
        action = event.code2str()
        if action == "endExist" or event.filename == self.data:
            return

        for entry in list(self.entries.values()):
            if entry.specific.match(event.filename):
                entry.handle_event(event)
                if any(event.filename.startswith(kp)
                       for kp in self.keypatterns
                       if kp.endswith(".pub")):
                    self.debug_log("New public key %s; invalidating "
                                   "ssh_known_hosts cache" % event.filename)
                    self.skn = False
                return

        if event.filename in ['info', 'info.xml', ':info']:
            for entry in list(self.entries.values()):
                entry.handle_event(event)
            return

        if event.filename.endswith('.static'):
            self.logger.info("Static key %s %s; invalidating ssh_known_hosts "
                             "cache" % (event.filename, action))
            if action == "deleted" and event.filename in self.static:
                del self.static[event.filename]
                self.skn = False
            else:
                self.static[event.filename] = Bcfg2.Server.Plugin.FileBacked(
                    os.path.join(self.data, event.filename))
                self.static[event.filename].HandleEvent(event)
                self.skn = False
            return

        self.logger.warn("SSHbase: Got unknown event %s %s" %
                         (event.filename, action))

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
                ipaddr = set([info[4][0]
                              for info in socket.getaddrinfo(client, None)])
                self.ipcache[client] = (ipaddr, client)
                return (ipaddr, client)
            except socket.gaierror:
                ipaddr = Popen(["getent", "hosts", client],
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
                self.logger.error("Failed to find any names associated with "
                                  "IP address %s" % cip)
                raise

    def build_skn(self, entry, metadata):
        """This function builds builds a host specific known_hosts file."""
        try:
            self.entries[entry.get('name')].bind_entry(entry, metadata)
        except Bcfg2.Server.Plugin.PluginExecutionError:
            entry.text = self.skn
            hostkeys = []
            for key in self.keypatterns:
                if key.endswith(".pub"):
                    try:
                        hostkeys.append(
                            self.entries["/etc/ssh/" +
                                         key].best_matching(metadata))
                    except Bcfg2.Server.Plugin.PluginExecutionError:
                        pass
            hostkeys.sort()
            for hostkey in hostkeys:
                entry.text += "localhost,localhost.localdomain,127.0.0.1 %s" \
                    % hostkey.data
            self.entries[entry.get('name')].bind_info_to_entry(entry, metadata)

    def build_hk(self, entry, metadata):
        """This binds host key data into entries."""
        try:
            self.entries[entry.get('name')].bind_entry(entry, metadata)
        except Bcfg2.Server.Plugin.PluginExecutionError:
            filename = entry.get('name').split('/')[-1]
            self.GenerateHostKeyPair(metadata.hostname, filename)
            # Service the FAM events queued up by the key generation
            # so the data structure entries will be available for
            # binding.
            #
            # NOTE: We wait for up to ten seconds. There is some
            # potential for race condition, because if the file
            # monitor doesn't get notified about the new key files in
            # time, those entries won't be available for binding. In
            # practice, this seems "good enough".
            tries = 0
            is_bound = False
            while not is_bound:
                if tries >= 10:
                    msg = "%s still not registered" % filename
                    self.logger.error(msg)
                    raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
                self.core.fam.handle_events_in_interval(1)
                tries += 1
                try:
                    self.entries[entry.get('name')].bind_entry(entry, metadata)
                    is_bound = True
                except Bcfg2.Server.Plugin.PluginExecutionError:
                    pass

    def GenerateHostKeyPair(self, client, filename):
        """Generate new host key pair for client."""
        match = re.search(r'(ssh_host_(?:((?:ecd|d|r)sa)_)?key)', filename)
        if match:
            hostkey = "%s.H_%s" % (match.group(1), client)
            if match.group(2):
                keytype = match.group(2)
            else:
                keytype = 'rsa1'
        else:
            raise PluginExecutionError("Unknown key filename: %s" % filename)

        fileloc = os.path.join(self.data, hostkey)
        publoc = os.path.join(self.data,
                              ".".join([hostkey.split('.')[0], 'pub',
                                        "H_%s" % client]))
        tempdir = tempfile.mkdtemp()
        temploc = os.path.join(tempdir, hostkey)
        cmd = ["ssh-keygen", "-q", "-f", temploc, "-N", "",
               "-t", keytype, "-C", "root@%s" % client]
        self.debug_log("SSHbase: Running: %s" % " ".join(cmd))
        proc = Popen(cmd, stdout=PIPE, stdin=PIPE)
        err = proc.communicate()[1]
        if proc.wait():
            raise PluginExecutionError("SSHbase: Error running ssh-keygen: %s"
                                       % err)

        try:
            shutil.copy(temploc, fileloc)
            shutil.copy("%s.pub" % temploc, publoc)
        except IOError:
            err = sys.exc_info()[1]
            raise PluginExecutionError("Temporary SSH keys not found: %s" %
                                       err)

        try:
            os.unlink(temploc)
            os.unlink("%s.pub" % temploc)
            os.rmdir(tempdir)
        except OSError:
            err = sys.exc_info()[1]
            raise PluginExecutionError("Failed to unlink temporary ssh keys: "
                                       "%s" % err)

    def AcceptChoices(self, _, metadata):
        return [Bcfg2.Server.Plugin.Specificity(hostname=metadata.hostname)]

    def AcceptPullData(self, specific, entry, log):
        """Per-plugin bcfg2-admin pull support."""
        # specific will always be host specific
        filename = os.path.join(self.data,
                                "%s.H_%s" % (entry['name'].split('/')[-1],
                                             specific.hostname))
        try:
            open(filename, 'w').write(entry['text'])
            if log:
                print("Wrote file %s" % filename)
        except KeyError:
            self.logger.error("Failed to pull %s. This file does not "
                              "currently exist on the client" %
                              entry.get('name'))
