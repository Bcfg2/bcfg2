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

    def get_mayor(self, node):
        if 'ccn' in node:
            return 'cct%sm.mcs.anl.gov' % ((int(node[3:]) / 32) + 1)
        elif 'ccviz' in node:
            return 'cct10m.mcs.anl.gov'
        elif 'ccsto' in node:
            return 'cct9m.mcs.anl.gov'
        else:
            return 'ccprez.mcs.anl.gov'

    def __setup__(self):
        self.repo = DirectoryBacked(self.data, self.core.fam)
        self.__provides__['ConfigFile']['/etc/fstab'] = self.build_fstab

    def build_fstab(self, entry, metadata):
        '''build fstab for chiba nodes'''
        node = metadata.hostname.split('.')[0]
        mayor = self.get_mayor(node)
        
        if 'ccn' in node:
            nodeclass = 'compute'
        elif 'ccviz' in node:
            nodeclass = 'compute'
        elif 'ccsto' in node:
            nodeclass = 'storage'
        elif 'cct' in node:
            nodeclass = 'mayor'
        elif 'ccfs' in node:
            nodeclass = 'fs'
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
        mayor = self.get_mayor(metadata.hostname.split('.')[0])
        kvers = '2.4.26'
        root = '/dev/sda2'
        data = self.repo.entries['tftp-template']
        entry.text = data % ( kvers, root, mayor, kvers, kvers, root, mayor, kvers) 
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0600'})
