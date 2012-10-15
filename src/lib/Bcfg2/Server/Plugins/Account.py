"""This handles authentication setup."""

import Bcfg2.Server.Plugin


class Account(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Generator):
    """This module generates account config files,
    based on an internal data repo:
    static.(passwd|group|limits.conf) -> static entries
    dyn.(passwd|group) -> dynamic entries (usually acquired from yp or somesuch)
    useraccess -> users to be granted login access on some hosts
    superusers -> users to be granted root privs on all hosts
    rootlike -> users to be granted root privs on some hosts

    """
    name = 'Account'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    deprecated = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        self.Entries = {'ConfigFile': {'/etc/passwd': self.from_yp_cb,
                                       '/etc/group': self.from_yp_cb,
                                       '/etc/security/limits.conf': self.gen_limits_cb,
                                       '/root/.ssh/authorized_keys': self.gen_root_keys_cb,
                                       '/etc/sudoers': self.gen_sudoers}}
        try:
            self.repository = Bcfg2.Server.Plugin.DirectoryBacked(self.data,
                                                                  self.core.fam)
        except:
            self.logger.error("Failed to load repos: %s, %s" % \
                              (self.data, "%s/ssh" % (self.data)))
            raise Bcfg2.Server.Plugin.PluginInitError

    def from_yp_cb(self, entry, metadata):
        """Build password file from cached yp data."""
        fname = entry.attrib['name'].split('/')[-1]
        entry.text = self.repository.entries["static.%s" % (fname)].data
        entry.text += self.repository.entries["dyn.%s" % (fname)].data
        perms = {'owner': 'root',
                 'group': 'root',
                 'mode': '0644'}
        [entry.attrib.__setitem__(key, value) for (key, value) in \
         list(perms.items())]

    def gen_limits_cb(self, entry, metadata):
        """Build limits entries based on current ACLs."""
        entry.text = self.repository.entries["static.limits.conf"].data
        superusers = self.repository.entries["superusers"].data.split()
        useraccess = [line.split(':') for line in \
                      self.repository.entries["useraccess"].data.split()]
        users = [user for (user, host) in \
                 useraccess if host == metadata.hostname.split('.')[0]]
        perms = {'owner': 'root',
                 'group': 'root',
                 'mode': '0600'}
        [entry.attrib.__setitem__(key, value) for (key, value) in \
         list(perms.items())]
        entry.text += "".join(["%s hard maxlogins 1024\n" % uname for uname in superusers + users])
        if "*" not in users:
            entry.text += "* hard maxlogins 0\n"

    def gen_root_keys_cb(self, entry, metadata):
        """Build root authorized keys file based on current ACLs."""
        superusers = self.repository.entries['superusers'].data.split()
        try:
            rootlike = [line.split(':', 1) for line in \
                        self.repository.entries['rootlike'].data.split()]
            superusers += [user for (user, host) in rootlike \
                           if host == metadata.hostname.split('.')[0]]
        except:
            pass
        rdata = self.repository.entries
        entry.text = "".join([rdata["%s.key" % user].data for user \
                              in superusers if \
                              ("%s.key" % user) in rdata])
        perms = {'owner': 'root',
                 'group': 'root',
                 'mode': '0600'}
        [entry.attrib.__setitem__(key, value) for (key, value) \
         in list(perms.items())]

    def gen_sudoers(self, entry, metadata):
        """Build root authorized keys file based on current ACLs."""
        superusers = self.repository.entries['superusers'].data.split()
        try:
            rootlike = [line.split(':', 1) for line in \
                        self.repository.entries['rootlike'].data.split()]
            superusers += [user for (user, host) in rootlike \
                           if host == metadata.hostname.split('.')[0]]
        except:
            pass
        entry.text = self.repository.entries['static.sudoers'].data
        entry.text += "".join(["%s ALL=(ALL) ALL\n" % uname \
                               for uname in superusers])
        perms = {'owner': 'root',
                 'group': 'root',
                 'mode': '0440'}
        [entry.attrib.__setitem__(key, value) for (key, value) \
         in list(perms.items())]
