import os
from mercurial import ui, hg
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Mercurial')

class Hg(Bcfg2.Server.Plugin.Plugin,
             Bcfg2.Server.Plugin.Version):
    """Mercurial is a version plugin for dealing with Bcfg2 repository."""
    name = 'Mercurial'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    experimental = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self)
        self.core = core
        self.datastore = datastore

        # path to hg directory for Bcfg2 repo
        hg_dir = "%s/.hg" % datastore

        # Read changeset from bcfg2 repo
        if os.path.isdir(hg_dir):
            self.get_revision()
        else:
            logger.error("%s is not present." % hg_dir)
            raise Bcfg2.Server.Plugin.PluginInitError

        logger.debug("Initialized hg plugin with hg directory = %s" % hg_dir)

    def get_revision(self):
        """Read hg revision information for the Bcfg2 repository."""
        try:
            repo_path = "%s/" % self.datastore
            repo = hg.repository(ui.ui(), repo_path)
            tip = repo.changelog.tip()
            revision = repo.changelog.rev(tip)
        except:
            logger.error("Failed to read hg repository; disabling mercurial support")
            raise Bcfg2.Server.Plugin.PluginInitError
        return revision

