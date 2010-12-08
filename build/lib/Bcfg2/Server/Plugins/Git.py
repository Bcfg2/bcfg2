"""The Git plugin provides a revision interface for Bcfg2 repos using git."""

import os
from dulwich.repo import Repo
import Bcfg2.Server.Plugin

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Git')


class Git(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    """Git is a version plugin for dealing with Bcfg2 repos."""
    name = 'Git'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self)
        self.core = core
        self.datastore = datastore

        # path to git directory for bcfg2 repo
        git_dir = "%s/.git" % datastore

        # Read revision from bcfg2 repo
        if os.path.isdir(git_dir):
            self.get_revision()
        else:
            logger.error("%s is not a directory" % git_dir)
            raise Bcfg2.Server.Plugin.PluginInitError

        logger.debug("Initialized git plugin with git directory %s" % git_dir)

    def get_revision(self):
        """Read git revision information for the Bcfg2 repository."""
        try:
            repo = Repo(self.datastore)
            revision = repo.head()
        except:
            logger.error("Failed to read git repository; disabling git support")
            raise Bcfg2.Server.Plugin.PluginInitError
        return revision
