'''This module manages the crontab file for bcfg2'''
__revision__ = '$Revision: 1887 $'

import binascii, os, socket, Bcfg2.Server.Plugin, random

class Crontab(Bcfg2.Server.Plugin.Plugin):
    '''This Generates a random set of times for the cron.daily entries to run.
     The goal is to ensure that our Configuration Server/network does get crushed
     all in a 5-10 minute period.
'''
    __name__ = 'Crontab'
    __version__ = '$Id: Crontab 1887 2006-06-18 02:35:54Z desai $'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        try:
            self.repository = Bcfg2.Server.Plugin.DirectoryBacked(self.data, self.core.fam)
        except OSError, ioerr:
            self.logger.error("Failed to load Crontab repository from %s" % (self.data))
            self.logger.error(ioerr)
            raise Bcfg2.Server.Plugin.PluginInitError
        try:
            prefix = open("%s/prefix" % (self.data)).read().strip()
        except IOError:
            prefix = ''
        self.Entries = {'ConfigFile':
                             {prefix + '/etc/crontab':self.build_crontab}}


    def build_crontab(self, entry, metadata):
        '''This function builds builds a crontab file with a random time for cron.daily'''
        random.seed(metadata.hostname)
        hour = random.randrange(0,6)
        minute = random.randrange(0,59)
        entry.text = self.repository.entries['crontab.template'].data% (minute, hour)
        permdata = {'owner':'root', 'group':'root', 'perms':'0644'}
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]

