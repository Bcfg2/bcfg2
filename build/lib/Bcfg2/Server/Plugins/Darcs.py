import os
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Darcs')

class Darcs(Bcfg2.Server.Plugin.Plugin,
             Bcfg2.Server.Plugin.Version):
    """Darcs is a version plugin for dealing with Bcfg2 repos."""
    name = 'Darcs'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    experimental = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self)
        self.core = core
        self.datastore = datastore

        # path to darcs directory for bcfg2 repo
        darcs_dir = "%s/_darcs" % datastore

        # Read changeset from bcfg2 repo
        if os.path.isdir(darcs_dir):
            self.get_revision()
        else:
            logger.error("%s is not present." % darcs_dir)
            raise Bcfg2.Server.Plugin.PluginInitError

        logger.debug("Initialized Darcs plugin with darcs directory = %s" % darcs_dir)

    def get_revision(self):
        """Read Darcs changeset information for the Bcfg2 repository."""
        try:
            data = Popen("env LC_ALL=C darcs changes",
                        shell=True,
                        cwd=self.datastore,
                        stdout=PIPE).stdout.readlines()
            revision = data[0].strip('\n')
        except:
            logger.error("Failed to read darcs repository; disabling Darcs support")
            logger.error('''Ran command "darcs changes" from directory "%s"''' % (self.datastore))
            logger.error("Got output: %s" % data)
            raise Bcfg2.Server.Plugin.PluginInitError
        return revision

