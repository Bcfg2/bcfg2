'''This handles authentication setup'''
__revision__ = '$Revision$'

from Bcfg2.Server.Generator import Generator, DirectoryBacked

class Account(Generator):
    '''This module generates account config files,
    based on an internal data repo:
    static.(passwd|group|limits.conf) -> static entries
    dyn.(passwd|group) -> dynamic entries (usually acquired from yp)
    useraccess -> users to be granted login access on some hosts
    superusers -> users to be granted root privs on all hosts
    rootlike -> users to be granted root privs on some hosts
    '''
    __name__ = 'Account'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {'ConfigFile':{}}

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        self.repository = DirectoryBacked(self.data)
        self.ssh = DirectoryBacked("%s/ssh"%(self.data))
        self.__provides__['ConfigFile'] = {'/etc/passwd':self.from_yp,
                                           '/etc/group':self.from_yp,
                                           '/etc/security/limits.conf':self.gen_limits,
                                           '/root/.ssh/authorized_keys':self.gen_root_keys}

    def from_yp(self, entry, metadata):
        '''Build password file from cached yp data'''
        fname = entry.attrib['name'].split('/')[-1]
        entry.text = self.repository.entries["static.%s" % (fname)].data
        entry.text += self.repository.entries["dyn.%s" % (fname)].data
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})

    def gen_limits(self, entry, metadata):
        '''Build limits entries based on current ACLs'''
        static = self.repository.entries["static.limits.conf"].data
        superusers = self.repository.entries["superusers"].data.split()
        useraccess = self.repository.entries["useraccess"].data
        users = [user for (user, host) in useraccess if host == metadata.hostname]
        entry.attrib.upate({'owner':'root', 'group':'root', 'perms':'0600'})
        entry.text = static + "".join(["%s hard maxlogins 1024\n" % x for x in superusers + users])
        if "*" not in users:
            entry.text += "* hard maxlogins 0\n"

    def gen_root_keys(self, entry, metadata):
        '''Build root authorized keys file based on current ACLs'''
        data = ''
        superusers = self.repository.entries['superusers'].data.split()
        rootlike = self.repository.entries['rootlike'].data.split()
        superusers += [x.split(':')[0] for x in rootlike if x.split(':')[1] == metadata.hostname]
        data = ''
        for user in superusers:
            if self.ssh.entries.has_key(user):
                data += self.ssh.entries[user].data
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0600'})
        entry.text = data
