'''This module configures files in a Chiba City specific way'''
__revision__ = '$Revision$'

from socket import gethostbyname, gaierror
from syslog import syslog, LOG_ERR
from Bcfg2.Server.Plugin import Plugin, DirectoryBacked, SingleXMLFileBacked, PluginExecutionError

class ChibaConf(SingleXMLFileBacked):
    '''This class encapsulates all information needed for all Chiba config ops'''
    pass

class Chiba(Plugin):
    '''the Chiba generator builds the following files:
      -> /etc/fstab
      -> /etc/network/interfaces
      -> /etc/dhcpd.conf
      -> /tftpboot/<node>.lst'''

    __name__ = 'Chiba'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        self.repo = DirectoryBacked(self.data, self.core.fam)
        self.Entries = {'ConfigFile': {'/etc/network/interfaces':self.build_interfaces}}

    def build_interfaces(self, entry, metadata):
        '''build network configs for clients'''
        entry.attrib['owner'] = 'root'
        entry.attrib['group'] = 'root'
        entry.attrib['perms'] = '0644'
        try:
            myriaddr = gethostbyname("%s-myr" % metadata.hostname)
        except gaierror:
            syslog(LOG_ERR, "Failed to resolve %s-myr"% metadata.hostname)
            raise PluginExecutionError, ("%s-myr" % metadata.hostname, 'lookup')
        entry.text = self.repo.entries['interfaces-template'].data % myriaddr

