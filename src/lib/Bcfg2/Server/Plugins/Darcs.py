""" Darcs is a version plugin for dealing with Bcfg2 repos stored in the
Darcs VCS. """

from Bcfg2.Utils import Executor
import Bcfg2.Server.Plugin


class Darcs(Bcfg2.Server.Plugin.Version):
    """ Darcs is a version plugin for dealing with Bcfg2 repos stored
    in the Darcs VCS. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = "_darcs"

    def __init__(self, core):
        Bcfg2.Server.Plugin.Version.__init__(self, core)
        self.cmd = Executor()
        self.logger.debug("Initialized Darcs plugin with darcs directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read Darcs changeset information for the Bcfg2 repository."""
        result = self.cmd.run(["env LC_ALL=C", "darcs", "changes"],
                              shell=True, cwd=Bcfg2.Options.setup.vcs_root)
        if result.success:
            return result.stdout.splitlines()[0].strip()
        else:
            msg = "Failed to read revision from darcs: %s" % result.error
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
