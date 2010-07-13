import os
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Cvs')

class Cvs(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    """CVS is a version plugin for dealing with Bcfg2 repository."""
    name = 'Cvs'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    experimental = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.core = core
        self.datastore = datastore

        # path to cvs directory for Bcfg2 repo
        cvs_dir = "%s/CVSROOT" % datastore

        # Read revision from Bcfg2 repo
        if os.path.isdir(cvs_dir):
            self.get_revision()
        else:
            logger.error("%s is not a directory" % cvs_dir)
            raise Bcfg2.Server.Plugin.PluginInitError

        logger.debug("Initialized cvs plugin with cvs directory = %s" % cvs_dir)

    def get_revision(self):
        """Read cvs revision information for the Bcfg2 repository."""
        try:
            data = Popen("env LC_ALL=C cvs log",
                        shell=True,
                        cwd=self.datastore,
                        stdout=PIPE).stdout.readlines()
            revision = data[3].strip('\n')
        except IndexError:
            logger.error("Failed to read cvs log; disabling cvs support")
            logger.error('''Ran command "cvs log %s"''' % (self.datastore))
            logger.error("Got output: %s" % data)
            raise Bcfg2.Server.Plugin.PluginInitError

