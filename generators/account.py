#!/usr/bin/env python

from Generator from Generator
from GeneratorUtils import DirectoryBacked
from Types import ConfigFile

class account(Generator):
    __name__ = 'account'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __doc__ = '''This module generates account config files, based on an internal data repo:
    static.(passwd|group|limits.conf) -> static entries
    dyn.(passwd|group) -> dynamic entries (usually acquired from yp)
    useraccess -> users to be granted login access on some hosts
    superusers -> users to be granted root privs on all hosts
    rootlike -> users to be granted root privs on some hosts
    '''

    def __setup__(self):
        self.repository = DirectoryBacked(self.data)
        self.ssh = DirectoryBacked("%s/ssh"%(self.data))
        self.__provides__ = {'ConfigFile':{'/etc/passwd':self.GenFromYP,
                                           '/etc/group':self.GenFromYP,
                                           '/etc/security/limits.conf':self.GenLimits,
                                           '/root/.ssh/authorized_keys':self.GenRootKeys}}

    def GenFromYP(self,filename,client):
        fname = filename.split('/')[-1]
        static = self.repository.entries["static.%s"%(fname)].data
        yp = self.repository.entries["dyn.%s"%(fname)].data
        return ConfigFile(filename,"root","root",'0644',static+yp)

    def GenLimits(self,filename,client):
        fname = 'limits.conf'
        static = self.repository.entries["static.limits.conf"].data
        superusers = self.repository.entries["superusers"].data.split()
        useraccess = self.repository.entries["useraccess"].data
        users = [x[0] for x in useraccess if x[1] == client]

        data = static + join(map(lambda x:"%s hard maxlogins 1024\n"%x, superusers + users), ""),

        if "*" not in users:
            data += "* hard maxlogins 0\n"
        
        return ConfigFile(filename,"root","root",'0644',data)

    def GenRootKeys(self,filename,client):
        su = self.repository.entries['superusers'].data.split()
        rl = self.repository.entries['rootlike'].data.split()
        su += [split(x,':')[0] for x in rl if split(x,':')[1] == client]
        data = ''
        for user in su:
            if self.ssh.entries.has_key(user):
                data += self.ssh.entries[user].data
        return ConfigFile(filename,'root','root','0600',data)
