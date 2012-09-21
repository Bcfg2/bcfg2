""" The Cvs plugin provides a revision interface for Bcfg2 repos using
cvs. """

from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin


class Cvs(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    """ The Cvs plugin provides a revision interface for Bcfg2 repos
    using cvs."""
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = "CVSROOT"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self, datastore)
        self.logger.debug("Initialized cvs plugin with cvs directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read cvs revision information for the Bcfg2 repository."""
        try:
            data = Popen("env LC_ALL=C cvs log",
                        shell=True,
                        cwd=self.datastore,
                        stdout=PIPE).stdout.readlines()
            return data[3].strip('\n')
        except IndexError:
            msg = "Failed to read cvs log"
            self.logger.error(msg)
            self.logger.error('Ran command "cvs log %s"' % self.datastore)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
