""" The Cvs plugin provides a revision interface for Bcfg2 repos using
cvs. """

from Bcfg2.Utils import Executor
import Bcfg2.Server.Plugin


class Cvs(Bcfg2.Server.Plugin.Version):
    """ The Cvs plugin provides a revision interface for Bcfg2 repos
    using cvs."""
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = "CVSROOT"

    def __init__(self, core):
        Bcfg2.Server.Plugin.Version.__init__(self, core)
        self.cmd = Executor()
        self.logger.debug("Initialized cvs plugin with CVS directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read cvs revision information for the Bcfg2 repository."""
        result = self.cmd.run(["env LC_ALL=C", "cvs", "log"],
                              shell=True, cwd=Bcfg2.Options.setup.vcs_root)
        try:
            return result.stdout.splitlines()[0].strip()
        except (IndexError, AttributeError):
            msg = "Failed to read revision from CVS: %s" % result.error
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
