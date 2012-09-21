""" The Hg plugin provides a revision interface for Bcfg2 repos using
mercurial. """

from mercurial import ui, hg
import Bcfg2.Server.Plugin


class Hg(Bcfg2.Server.Plugin.Plugin,
         Bcfg2.Server.Plugin.Version):
    """ The Hg plugin provides a revision interface for Bcfg2 repos
    using mercurial. """

    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = ".hg"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self, datastore)
        self.logger.debug("Initialized hg plugin with hg directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read hg revision information for the Bcfg2 repository."""
        try:
            repo_path = self.datastore + "/"
            repo = hg.repository(ui.ui(), repo_path)
            tip = repo.changelog.tip()
            return repo.changelog.rev(tip)
        except:
            msg = "Failed to read hg repository"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
