#!/usr/bin/env python

from re import compile

from Bcfg2.Server.Generator import Generator, DirectoryBacked
from Bcfg2.Server.Types import ConfigFile

class fstab(Generator):
    __name__ = 'fstab'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    mayor = compile("\$MAYOR")

    def __setup__(self):
        self.repo = DirectoryBacked(self.data, self.core.fam)
        self.__provides__ = {'ConfigFile':{'/etc/fstab':self.build_fstab}}

    def build_fstab(self,name,metadata):
        node = metadata.hostname.split('.')[0]
        if 'ccn' in node:
            nodeclass = 'compute'
            mayor = 'cct%sm.mcs.anl.gov'%((int(node[3:]) / 32) + 1)
        elif 'ccviz' in node:
            nodeclass = 'compute'
            mayor = 'cct10m.mcs.anl.gov'
        elif 'ccsto' in node:
            nodeclass = 'storage'
            mayor = 'cct9m.mcs.anl.gov'
        elif 'cct' in node:
            nodeclass = 'mayor'
            mayor = 'ccprez.mcs.anl.gov'
        elif 'ccfs' in node:
            nodeclass = 'fs'
            mayor = 'ccprez.mcs.anl.gov'
        else:
            raise KeyError,client

        fsname = "fstab_%s"%(nodeclass)
        fsdata = self.repo.entries[fsname].data

        return ConfigFile('/etc/fstab','root','root','0644',self.mayor.sub(mayor,fsdata))
        
        
