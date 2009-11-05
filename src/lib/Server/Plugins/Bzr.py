import os
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Bzr')

class Bzr(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    name = 'Bzr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.core = core
        self.datastore = datastore

        # path to bzr directory for bcfg2 repo
        bzr_dir = "%s/.bzr" % datastore

        # Read revision from bcfg2 repo
        if os.path.isdir(bzr_dir):
            revision = self.get_revision()
        else:
            logger.error("%s is not a directory" % bzr_dir)
            raise Bcfg2.Server.Plugin.PluginInitError

        logger.debug("Initialized Bazaar plugin with directory = %(dir)s at revision = %(rev)s" % {'dir': bzr_dir, 'rev': revision})

    def get_revision(self):
        '''Read Bazaar revision information for the bcfg2 repository'''
        try:
            data = Popen(("env LC_ALL=C bzr revno %s" %
                         (self.datastore)), shell=True,
                         stdout=PIPE).stdout.readlines()
            revision = data[0].rstrip('\n')
        except IndexError:
            logger.error("Failed to read bzr revno; disabling Bazaar support")
            logger.error('''Ran command "bzr revno %s"''' % \
                            (self.datastore))
            logger.error("Got output: %s" % data)
            raise Bcfg2.Server.Plugin.PluginInitError
        return revision
