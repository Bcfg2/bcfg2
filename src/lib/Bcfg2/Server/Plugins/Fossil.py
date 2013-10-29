""" The Fossil plugin provides a revision interface for Bcfg2 repos
using fossil."""

from Bcfg2.Utils import Executor
import Bcfg2.Server.Plugin


class Fossil(Bcfg2.Server.Plugin.Version):
    """ The Fossil plugin provides a revision interface for Bcfg2
    repos using fossil. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = "_FOSSIL_"

    def __init__(self, core):
        Bcfg2.Server.Plugin.Version.__init__(self, core)
        self.cmd = Executor()
        self.logger.debug("Initialized Fossil plugin with fossil directory %s"
                          % self.vcs_path)

    def get_revision(self):
        """Read fossil revision information for the Bcfg2 repository."""
        result = self.cmd.run(["env LC_ALL=C", "fossil", "info"],
                              shell=True, cwd=Bcfg2.Options.setup.vcs_root)
        try:
            revision = None
            for line in result.stdout.splitlines():
                ldata = line.split(': ')
                if ldata[0].strip() == 'checkout':
                    revision = line[1].strip().split(' ')[0]
            return revision
        except (IndexError, AttributeError):
            msg = "Failed to read revision from Fossil: %s" % result.error
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
