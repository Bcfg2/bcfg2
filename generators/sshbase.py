#!/usr/bin/env python

from glob import glob
from os import rename, stat
from socket import gethostbyname

from Types import ConfigFile
from Generator import Generator

class sshbase(Generator):
    __name__ = 'sshbase'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __build__ = { '/etc/ssh/ssh_known_hosts':'build_skn',
                  '/etc/ssh/ssh_host_dsa_key':'build_hk',
                  '/etc/ssh/ssh_host_rsa_key':'build_hk',
                  '/etc/ssh/ssh_host_dsa_key.pub':'build_hk',
                  '/etc/ssh/ssh_host_rsa_key.pub':'build_hk'}

    def build_skn(self,name,client):
        data=file("%s/ssh_known_hosts"%(self.data)).read()
        ip=gethostbyname(client)
        for hostkey in ["ssh_host_dsa_key.pub.H_%s","ssh_host_rsa_key.pub.H_%s","ssh_host_key.pub.H_%s"]:
            filename="%s/%s"%(self.data,hostkey)%(client)
            hdata=file(filename).read()
            data+="%s,%s,%s %s"%(client,"%s.mcs.anl.gov"%(client),ip,hdata)
        return ConfigFile(name,'root','root','0644',data)

    def build_hk(self,name,client):
        reponame="%s/%s.H_%s"%(self.data,name.split('/')[-1],client)
        try:
            stat(reponame)
        except IOError:
            self.GenerateHostKeys(client)
            self.GenerateKnownHosts()
        # then we read the data file
        keydata=file(reponame).read()
        if "ssh_host_key.H_" in reponame:
            return ConfigFile(name,'root','root','0600',keydata,'base64')
        return ConfigFile(name,'root','root','0600',keydata)

    def GenerateKnownHosts(self):
        output=file("%s/ssh_known_hosts"%(self.__data__),'w')
        for f in glob("%s/ssh_host_key.pub.H_*"%(self.__data__)) + glob("%s/ssh_host_*sa_key.pub.H_*"%(self.__data__)):
            host=f.split('_')[-1]
            data=file(f).read()
            output.write("%s,%s.mcs.anl.gov,%s %s"%(host,host,gethostbyname(host),data))
        output.close()

    def GenerateHostKeys(self,client):
        for hostkey in ["ssh_host_dsa_key.H_%s","ssh_host_rsa_key.H_%s","ssh_host_key.H_%s"]:
            filename="%s/%s"%(self.data,hostkey)%(client)
            if "ssh_host_rsa_key.H_" in filename:
                keytype='rsa'
            elif "ssh_host_dsa_key.H_" in filename:
                keytype='dsa'
            else:
                keytype='rsa1'
                
            try:
                stat(filename)
            except:
                system('ssh-keygen -f %s -N "" -t %s -C root@%s'%(filename,keytype,client))
                rename("%s.pub"%(filename),".".join(filename.split('.')[:-1]+['pub']+filename.split('.')[-1]))
        # call the notifier for global

