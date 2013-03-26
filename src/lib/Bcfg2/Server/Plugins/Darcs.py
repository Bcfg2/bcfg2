""" Darcs is a version plugin for dealing with Bcfg2 repos stored in the
Darcs VCS. """

from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin


class Darcs(Bcfg2.Server.Plugin.Version):
    """ Darcs is a version plugin for dealing with Bcfg2 repos stored
    in the Darcs VCS. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = "_darcs"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Version.__init__(self, core, datastore)
        self.logger.debug("Initialized Darcs plugin with darcs directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read Darcs changeset information for the Bcfg2 repository."""
        try:
            data = Popen("env LC_ALL=C darcs changes",
                         shell=True,
                         cwd=self.vcs_root,
                         stdout=PIPE).stdout.readlines()
            revision = data[0].strip('\n')
        except:
            msg = "Failed to read darcs repository"
            self.logger.error(msg)
            self.logger.error('Ran command "darcs changes" from directory %s' %
                              self.vcs_root)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        return revision
