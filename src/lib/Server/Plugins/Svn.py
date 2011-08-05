import os
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Svn')


class Svn(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    """Svn is a version plugin for dealing with Bcfg2 repos."""
    name = 'Svn'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.core = core
        self.datastore = datastore

        # path to svn directory for bcfg2 repo
        svn_dir = "%s/.svn" % datastore

        # Read revision from bcfg2 repo
        if os.path.isdir(svn_dir):
            self.get_revision()
        else:
            logger.error("%s is not a directory" % svn_dir)
            raise Bcfg2.Server.Plugin.PluginInitError

        logger.debug("Initialized svn plugin with svn directory = %s" % svn_dir)

    def get_revision(self):
        """Read svn revision information for the Bcfg2 repository."""
        try:
            data = Popen(("env LC_ALL=C svn info %s" %
                         pipes.quote(self.datastore)), shell=True,
                         stdout=PIPE).communicate()[0].split('\n')
            return [line.split(': ')[1] for line in data \
                    if line[:9] == 'Revision:'][-1]
        except IndexError:
            logger.error("Failed to read svn info; disabling svn support")
            logger.error('''Ran command "svn info %s"''' % (self.datastore))
            logger.error("Got output: %s" % data)
            raise Bcfg2.Server.Plugin.PluginInitError
