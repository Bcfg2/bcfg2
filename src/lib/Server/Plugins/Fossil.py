import os
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Fossil')

class Fossil(Bcfg2.Server.Plugin.Plugin,
             Bcfg2.Server.Plugin.Version):
    """Fossil is a version plugin for dealing with Bcfg2 repos."""
    name = 'Fossil'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.core = core
        self.datastore = datastore

        # path to fossil file for bcfg2 repo
        fossil_file = "%s/_FOSSIL_" % datastore

        # Read revision from bcfg2 repo
        if os.path.isfile(fossil_file):
            revision = self.get_revision()
        elif not os.path.isdir(datastore):
            logger.error("%s is not a directory" % datastore)
            raise Bcfg2.Server.Plugin.PluginInitError
        else:
            logger.error("%s is not a file" % fossil_file)
            raise Bcfg2.Server.Plugin.PluginInitError

        logger.debug("Initialized Fossil.py plugin with %(ffile)s at revision %(frev)s" \
                    % {'ffile': fossil_file, 'frev': revision})

    def get_revision(self):
        """Read fossil revision information for the Bcfg2 repository."""
        try:
            data = Popen("env LC_ALL=C fossil info",
                        shell=True,
                        cwd=self.datastore,
                        stdout=PIPE).stdout.readlines()
            revline = [line.split(': ')[1].strip() for line in data if \
                       line.split(': ')[0].strip() == 'checkout'][-1]
            revision = revline.split(' ')[0]
        except IndexError:
            logger.error("Failed to read fossil info; disabling fossil support")
            logger.error('''Ran command "fossil info" from directory "%s"''' % (self.datastore))
            logger.error("Got output: %s" % data)
            raise Bcfg2.Server.Plugin.PluginInitError
        return revision
