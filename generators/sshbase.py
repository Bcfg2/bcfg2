#!/usr/bin/env python

from glob import glob
from os import rename, stat
from socket import gethostbyname

from Types import ConfigFile
from Generator import Generator
from GeneratorUtils import DirectoryBacked

class sshbase(Generator):
    __name__ = 'sshbase'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {'ConfigFile':{'/etc/ssh/ssh_known_hosts':'build_skn',
                                  '/etc/ssh/ssh_host_dsa_key':'build_hk',
                                  '/etc/ssh/ssh_host_rsa_key':'build_hk',
                                  '/etc/ssh/ssh_host_dsa_key.pub':'build_hk',
                                  '/etc/ssh/ssh_host_rsa_key.pub':'build_hk'}}

    def __setup__(self):
        self.repository = DirectoryBacked(self.data)

    def build_skn(self,name,client):
        filedata = self.repository.entries['ssh_known_hosts'].data
        ip=gethostbyname(client)
        keylist = map(lambda x:x%client, ["ssh_host_dsa_key.pub.H_%s","ssh_host_rsa_key.pub.H_%s","ssh_host_key.pub.H_%s"])
        for hostkey in keylist:
            filedata += "%s,%s,%s %s"%(client,"%s.mcs.anl.gov"%(client),ip,self.repository.entries[hostkey].data)
        return ConfigFile(name,'root','root','0644',filedata)

    def build_hk(self,name,client):
        filename = "%s.H_%s"%(name.split('/')[-1],client)
        if filename not in self.repository.entries.keys():
            self.GenerateHostKeys(client)
            self.GenerateKnownHosts()
        keydata = self.repository.entries[filename].data
        if "ssh_host_key.H_" in filename:
            return ConfigFile(name,'root','root','0600',keydata,'base64')
        return ConfigFile(name,'root','root','0600',keydata)

    def GenerateKnownHosts(self):
        output = ''
        for f in self.repository.entries.keys():
            if ".pub.H_" in f:
                hostname = f.split('_')[-1]
                output += "%s,%s.mcs.anl.gov,%s %s"%(host,host,gethostbyname(host),data)
        self.repository.entries['ssh_known_hosts'].data = output

    def GenerateHostKeys(self,client):
        keylist = map(lambda x:x%client, ["ssh_host_dsa_key.H_%s","ssh_host_rsa_key.H_%s","ssh_host_key.H_%s"])
        for hostkey in keylist:
            if 'ssh_host_rsa_key.H_' in filename:
                keytype = 'rsa'
            elif 'ssh_host_dsa_key.H_' in filename:
                keytype = 'dsa'
            else:
                keytype = 'rsa1'

            if hostkey not in self.repository.entries.keys():
                system('ssh-keygen -f %s/%s -N "" -t %s -C root@%s'%(self.data,hostkey,keytype,client))
                rename("%s/%s.pub"%(self.data,hostkey),"%s/"%(self.data)+".".join(hostkey.split('.')[:-1]+['pub']+hostkey.split('.')[-1]))
        # call the notifier for global

