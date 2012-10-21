""" The Git plugin provides a revision interface for Bcfg2 repos using
git. """

try:
    from dulwich.repo import Repo
except ImportError:
    # fallback to shell commands when dulwich unavailable
    from subprocess import Popen, PIPE

import Bcfg2.Server.Plugin


class Git(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    """ The Git plugin provides a revision interface for Bcfg2 repos
    using git. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = ".git"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self, datastore)
        self.logger.debug("Initialized git plugin with git directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read git revision information for the Bcfg2 repository."""
        try:
            return Repo(self.datastore).head()
        except NameError:
            return Popen("env LC_ALL=C git log -1 --pretty=format:%H",
                         shell=True,
                         cwd=self.datastore,
                         stdout=PIPE).stdout.readline()
        except:
            msg = "Failed to read git repository"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
