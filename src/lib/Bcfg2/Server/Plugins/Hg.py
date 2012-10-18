""" The Hg plugin provides a revision interface for Bcfg2 repos using
mercurial. """

import sys
from mercurial import ui, hg
import Bcfg2.Server.Plugin


class Hg(Bcfg2.Server.Plugin.Version):
    """ The Hg plugin provides a revision interface for Bcfg2 repos
    using mercurial. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = ".hg"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Version.__init__(self, core, datastore)
        self.logger.debug("Initialized hg plugin with hg directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read hg revision information for the Bcfg2 repository."""
        try:
            repo_path = self.vcs_root + "/"
            repo = hg.repository(ui.ui(), repo_path)
            tip = repo.changelog.tip()
            return repo.changelog.rev(tip)
        except:
            err = sys.exc_info()[1]
            msg = "Failed to read hg repository: %s" % err
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
