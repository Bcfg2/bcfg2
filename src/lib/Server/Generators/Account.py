'''This handles authentication setup'''
__revision__ = '$Revision$'

from Bcfg2.Server.Generator import Generator, GeneratorInitError, DirectoryBacked

class Account(Generator):
    '''This module generates account config files,
    based on an internal data repo:
    static.(passwd|group|limits.conf) -> static entries
    dyn.(passwd|group) -> dynamic entries (usually acquired from yp or somesuch)
    useraccess -> users to be granted login access on some hosts
    superusers -> users to be granted root privs on all hosts
    rootlike -> users to be granted root privs on some hosts
    '''
    __name__ = 'Account'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        self.__provides__ = {'ConfigFile':{'/etc/passwd':self.from_yp_cb,
                                           '/etc/group':self.from_yp_cb,
                                           '/etc/security/limits.conf':self.gen_limits_cb,
                                           '/root/.ssh/authorized_keys':self.gen_root_keys_cb}}
        try:
            self.repository = DirectoryBacked(self.data, self.core.fam)
        except:
            self.LogError("Failed to load repos: %s, %s" % (self.data, "%s/ssh" % (self.data)))
            raise GeneratorInitError

    def from_yp_cb(self, entry, metadata):
        '''Build password file from cached yp data'''
        fname = entry.attrib['name'].split('/')[-1]
        entry.text = self.repository.entries["static.%s" % (fname)].data
        entry.text += self.repository.entries["dyn.%s" % (fname)].data
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})

    def gen_limits_cb(self, entry, metadata):
        '''Build limits entries based on current ACLs'''
        entry.text = self.repository.entries["static.limits.conf"].data
        superusers = self.repository.entries["superusers"].data.split()
        useraccess = [line.split(':') for line in self.repository.entries["useraccess"].data.split()]
        users = [user for (user, host) in useraccess if host == metadata.hostname]
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0600'})
        entry.text += "".join(["%s hard maxlogins 1024\n" % uname for uname in superusers + users])
        if "*" not in users:
            entry.text += "* hard maxlogins 0\n"

    def gen_root_keys_cb(self, entry, metadata):
        '''Build root authorized keys file based on current ACLs'''
        entry.text = ''
        superusers = self.repository.entries['superusers'].data.split()
        rootlike = [line.split(':', 1) for line in self.repository.entries['rootlike'].data.split()]
        superusers += [user for (user, host) in rootlike if host == metadata.hostname]
        for user in superusers:
            if self.repository.entries.has_key("%s.key" % user):
                entry.text += self.repository.entries["%s.key" % user].data
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0600'})
