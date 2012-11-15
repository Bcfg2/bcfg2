""" The Git plugin provides a revision interface for Bcfg2 repos using
git. """

import sys
import Bcfg2.Server.Plugin
from subprocess import Popen, PIPE

try:
    import git
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False


class Git(Bcfg2.Server.Plugin.Version):
    """ The Git plugin provides a revision interface for Bcfg2 repos
    using git. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = ".git"
    if HAS_GITPYTHON:
        __rmi__ = Bcfg2.Server.Plugin.Version.__rmi__ + ['Update']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Version.__init__(self, core, datastore)
        if HAS_GITPYTHON:
            self.repo = git.Repo(self.vcs_root)
        else:
            self.logger.debug("Git: GitPython not found, using CLI interface "
                              "to Git")
            self.repo = None
        self.logger.debug("Initialized git plugin with git directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read git revision information for the Bcfg2 repository."""
        try:
            if HAS_GITPYTHON:
                return self.repo.head.commit.hexsha
            else:
                cmd = ["git", "--git-dir", self.vcs_path,
                       "--work-tree", self.vcs_root, "rev-parse", "HEAD"]
                self.debug_log("Git: Running cmd")
                proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
                rv, err = proc.communicate()
                if proc.wait():
                    raise Exception(err)
                return rv
        except:
            err = sys.exc_info()[1]
            msg = "Git: Error getting revision from %s: %s" % (self.vcs_root,
                                                               err)
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

    def Update(self, ref=None):
        """ Git.Update() => True|False
        Update the working copy against the upstream repository
        """
        self.logger.info("Git: Git.Update(ref='%s')" % ref)
        self.debug_log("Git: Performing garbage collection on repo at %s" %
                       self.vcs_root)
        try:
            self.repo.git.gc('--auto')
        except git.GitCommandError:
            self.logger.warning("Git: Failed to perform garbage collection: %s"
                                % sys.exc_info()[1])

        if ref:
            self.debug_log("Git: Checking out %s" % ref)
            try:
                self.repo.git.checkout('-f', ref)
            except git.GitCommandError:
                err = sys.exc_info()[1]
                msg = "Git: Failed to checkout %s: %s" % (ref, err)
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

        # determine if we should try to pull to get the latest commit
        # on this head
        tracking = None
        if not self.repo.head.is_detached:
            self.debug_log("Git: Determining if %s is a tracking branch" %
                           self.repo.head.ref.name)
            tracking = self.repo.head.ref.tracking_branch()

        if tracking is not None:
            self.debug_log("Git: %s is a tracking branch, pulling from %s" %
                           (self.repo.head.ref.name, tracking))
            try:
                self.repo.git.pull("--rebase")
            except:  # pylint: disable=W0702
                err = sys.exc_info()[1]
                msg = "Git: Failed to pull from upstream: %s" % err
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

        self.logger.info("Git: Repo at %s updated to %s" %
                         (self.vcs_root, self.get_revision()))
        return True
