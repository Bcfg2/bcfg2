#!/usr/bin/env python

from binascii import b2a_base64
from glob import glob
from os import rename, stat, system
from socket import gethostbyname

from Types import ConfigFile
from Generator import Generator
from GeneratorUtils import DirectoryBacked

class sshbase(Generator):
    __name__ = 'sshbase'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __setup__(self):
        self.repository = DirectoryBacked(self.data, self.core.fam)
        self.__provides__ = {'ConfigFile':{'/etc/ssh/ssh_known_hosts':self.build_skn, 
                                           '/etc/ssh/ssh_host_dsa_key':self.build_hk,
                                           '/etc/ssh/ssh_host_rsa_key':self.build_hk,
                                           '/etc/ssh/ssh_host_dsa_key.pub':self.build_hk,
                                           '/etc/ssh/ssh_host_rsa_key.pub':self.build_hk,
                                           '/etc/ssh/ssh_host_key':self.build_hk,
                                           '/etc/ssh/ssh_host_key.pub':self.build_hk}}

    def build_skn(self,entry,metadata):
        client = metadata.hostname
        filedata = self.repository.entries['ssh_known_hosts'].data
        ip=gethostbyname(client)
        keylist = map(lambda x:x%(client), ["ssh_host_dsa_key.pub.H_%s","ssh_host_rsa_key.pub.H_%s","ssh_host_key.pub.H_%s"])
        for hostkey in keylist:
            filedata += "%s,%s,%s %s"%(client,"%s.mcs.anl.gov"%(client),ip,self.repository.entries[hostkey].data)
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})
        entry.text = filedata

    def build_hk(self,entry,metadata):
        client = metadata.hostname
        filename = "%s.H_%s"%(entry.attrib['name'].split('/')[-1],client)
        if filename not in self.repository.entries.keys():
            self.GenerateHostKeys(client)
            self.GenerateKnownHosts()
        keydata = self.repository.entries[filename].data
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0600'})
        entry.text = keydata
        if "ssh_host_key.H_" in filename:
            entry.attrib['encoding'] = 'base64'
            entry.text = b2a_base64(keydata)

    def GenerateKnownHosts(self):
        output = ''
        for f in self.repository.entries.keys():
            if ".pub.H_" in f:
                h = f.split('_')[-1]
                output += "%s,%s.mcs.anl.gov,%s %s"%(h, h, gethostbyname(h), self.repository.entries[f].data)
        self.repository.entries['ssh_known_hosts'].data = output

    def GenerateHostKeys(self,client):
        keylist = map(lambda x:x%client, ["ssh_host_dsa_key.H_%s","ssh_host_rsa_key.H_%s","ssh_host_key.H_%s"])
        for hostkey in keylist:
            if 'ssh_host_rsa_key.H_' in hostkey:
                keytype = 'rsa'
            elif 'ssh_host_dsa_key.H_' in hostkey:
                keytype = 'dsa'
            else:
                keytype = 'rsa1'

            if hostkey not in self.repository.entries.keys():
                system('ssh-keygen -f %s/%s -N "" -t %s -C root@%s'%(self.data,hostkey,keytype,client))
                rename("%s/%s.pub"%(self.data,hostkey),"%s/"%(self.data)+".".join(hostkey.split('.')[:-1]+['pub']+hostkey.split('.')[-1]))
        # call the notifier for global

