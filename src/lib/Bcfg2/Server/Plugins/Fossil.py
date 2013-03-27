""" The Fossil plugin provides a revision interface for Bcfg2 repos
using fossil."""

from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin


class Fossil(Bcfg2.Server.Plugin.Version):
    """ The Fossil plugin provides a revision interface for Bcfg2
    repos using fossil. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = "_FOSSIL_"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Version.__init__(self, core, datastore)
        self.logger.debug("Initialized Fossil plugin with fossil directory %s"
                          % self.vcs_path)

    def get_revision(self):
        """Read fossil revision information for the Bcfg2 repository."""
        try:
            data = Popen("env LC_ALL=C fossil info",
                         shell=True,
                         cwd=self.vcs_root,
                         stdout=PIPE).stdout.readlines()
            revline = [line.split(': ')[1].strip() for line in data
                       if line.split(': ')[0].strip() == 'checkout'][-1]
            return revline.split(' ')[0]
        except IndexError:
            msg = "Failed to read fossil info"
            self.logger.error(msg)
            self.logger.error('Ran command "fossil info" from directory "%s"' %
                              self.vcs_root)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
