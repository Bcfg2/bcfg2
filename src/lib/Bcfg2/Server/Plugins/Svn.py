""" The Svn plugin provides a revision interface for Bcfg2 repos using
svn. """

import pipes
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin


class Svn(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    """ The Svn plugin provides a revision interface for Bcfg2 repos
    using svn. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = ".svn"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self, datastore)
        self.logger.debug("Initialized svn plugin with svn directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read svn revision information for the Bcfg2 repository."""
        try:
            data = Popen(("env LC_ALL=C svn info %s" %
                         pipes.quote(self.datastore)), shell=True,
                         stdout=PIPE).communicate()[0].split('\n')
            return [line.split(': ')[1] for line in data \
                    if line[:9] == 'Revision:'][-1]
        except IndexError:
            msg = "Failed to read svn info"
            self.logger.error(msg)
            self.logger.error('Ran command "svn info %s"' % self.datastore)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
