#!/usr/bin/env python

from re import compile as regcompile
from Bcfg2.Server.Generator import Generator, DirectoryBacked, SingleXMLFileBacked

'''This module configures files in a Chiba City specific way'''
__revision__ = '$Revision$'

class ChibaConf(SingleXMLFileBacked):
    '''This class encapsulates all information needed for all Chiba config ops'''
    def Index(self):
        pass

class Chiba(Generator):
    '''the Chiba generator builds the following files:
      -> /etc/fstab
      -> /etc/network/interfaces
      -> /etc/dhcpd.conf
      -> /tftpboot/<node>.lst'''

    __name__ = 'Chiba'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {'ConfigFile':{}}

    mayor = regcompile("\$MAYOR")

    def __setup__(self):
        self.repo = DirectoryBacked(self.data, self.core.fam)
        self.__provides__['ConfigFile']['/etc/fstab'] = self.build_fstab

    def build_fstab(self, entry, metadata):
        '''build fstab for chiba nodes'''
        node = metadata.hostname.split('.')[0]
        if 'ccn' in node:
            nodeclass = 'compute'
            mayor = 'cct%sm.mcs.anl.gov' % ((int(node[3:]) / 32) + 1)
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
            raise KeyError, node

        entry.attrib['owner'] = 'root'
        entry.attrib['group'] = 'root'
        entry.attrib['perms'] = '0644'
        fsdata = self.repo.entries["fstab_%s" % (nodeclass)]
        entry.text = self.mayor.sub(mayor, fsdata)

    def build_interfaces(self, entry, metadata):
        '''build network configs for clients'''
        entry.attrib['owner'] = 'root'
        entry.attrib['group'] = 'root'
        entry.attrib['perms'] = '0644'
        entry.text = self.repo.entries['iface-template']
        # add more here later

    def build_dhcpd(self, entry, metadata):
        '''build dhcpd.conf for server(s)'''
        pass

    def build_tftp(self, entry, metadata):
        '''build tftp files for client netboot'''
        data = self.repo.entries['tftp-template']

    
