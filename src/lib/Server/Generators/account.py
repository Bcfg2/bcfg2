'''This handles authentication setup'''
__revision__ = '$Revision$'

from Bcfg2.Server.Generator import Generator, DirectoryBacked

class account(Generator):
    '''This module generates account config files,
    based on an internal data repo:
    static.(passwd|group|limits.conf) -> static entries
    dyn.(passwd|group) -> dynamic entries (usually acquired from yp)
    useraccess -> users to be granted login access on some hosts
    superusers -> users to be granted root privs on all hosts
    rootlike -> users to be granted root privs on some hosts
    '''
    __name__ = 'account'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {'ConfigFile':{}}

    def __setup__(self):
        self.repository = DirectoryBacked(self.data)
        self.ssh = DirectoryBacked("%s/ssh"%(self.data))
        self.__provides__['ConfigFile'] = {'/etc/passwd':self.from_yp,
                                           '/etc/group':self.from_yp,
                                           '/etc/security/limits.conf':self.gen_limits,
                                           '/root/.ssh/authorized_keys':self.gen_root_keys}

    def from_yp(self, entry, metadata):
        fname = entry.attrib['name'].split('/')[-1]
        entry.text = self.repository.entries["static.%s" % (fname)].data
        entry.text += self.repository.entries["dyn.%s" % (fname)].data
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})

    def gen_limits(self, entry, metadata):
        static = self.repository.entries["static.limits.conf"].data
        superusers = self.repository.entries["superusers"].data.split()
        useraccess = self.repository.entries["useraccess"].data
        users = [x[0] for x in useraccess if x[1] == metadata.hostname]
        entry.attrib.upate({'owner':'root', 'group':'root', 'perms':'0600'})
        entry.text = static + "".join(["%s hard maxlogins 1024\n" % x for x in superusers + users])
        if "*" not in users:
            entry.text += "* hard maxlogins 0\n"

    def gen_root_keys(self, entry, metadata):
        data = ''
        su = self.repository.entries['superusers'].data.split()
        rl = self.repository.entries['rootlike'].data.split()
        su += [x.split(':')[0] for x in rl if x.split(':')[1] == metadata.hostname]
        data = ''
        for user in su:
            if self.ssh.entries.has_key(user):
                data += self.ssh.entries[user].data
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0600'})
        entry.text = data
