""" The Git plugin provides a revision interface for Bcfg2 repos using
git. """

import os
import sys
import Bcfg2.Server.Plugin


class GitAPIBase(object):
    """ Base class for the various Git APIs (dulwich, GitPython,
    subprocesses) """
    def __init__(self, path):
        self.path = path

    def revision(self):
        """ Get the current revision of the git repo as a string """
        raise NotImplementedError

    def pull(self):
        """ Pull the latest version of the upstream git repo and
        rebase against it. """
        raise NotImplementedError


try:
    from dulwich.client import get_transport_and_path
    from dulwich.repo import Repo
    from dulwich.file import GitFile, ensure_dir_exists

    class GitAPI(GitAPIBase):
        """ API for :class:`Git` using :mod:`dulwich` """
        def __init__(self, path):
            GitAPIBase.__init__(self, path)
            self.repo = Repo(self.path)
            self.client, self.origin_path = get_transport_and_path(
                self.repo.get_config().get(("remote", "origin"),
                                           "url"))

        def revision(self):
            return self.repo.head()

        def pull(self):
            try:
                remote_refs = self.client.fetch(
                    self.origin_path, self.repo,
                    determine_wants=self.repo.object_store.determine_wants_all)
            except KeyError:
                etype, err = sys.exc_info()[:2]
                # try to work around bug
                # https://bugs.launchpad.net/dulwich/+bug/1025886
                try:
                    # pylint: disable=W0212
                    self.client._fetch_capabilities.remove('thin-pack')
                # pylint: enable=W0212
                except KeyError:
                    raise etype(err)
                remote_refs = self.client.fetch(
                    self.origin_path, self.repo,
                    determine_wants=self.repo.object_store.determine_wants_all)

            tree_id = self.repo[remote_refs['HEAD']].tree
            # iterate over tree content, giving path and blob sha.
            for entry in self.repo.object_store.iter_tree_contents(tree_id):
                entry_in_path = entry.in_path(self.repo.path)
                ensure_dir_exists(os.path.split(entry_in_path.path)[0])
                GitFile(entry_in_path.path,
                        'wb').write(self.repo[entry.sha].data)

except ImportError:
    try:
        import git

        class GitAPI(GitAPIBase):
            """ API for :class:`Git` using :mod:`git` (GitPython) """
            def __init__(self, path):
                GitAPIBase.__init__(self, path)
                self.repo = git.Repo(path)

            def revision(self):
                return self.repo.head.commit.hexsha

            def pull(self):
                self.repo.git.pull("--rebase")

    except ImportError:
        from subprocess import Popen, PIPE

        try:
            Popen(["git"], stdout=PIPE, stderr=PIPE).wait()

            class GitAPI(GitAPIBase):
                """ API for :class:`Git` using subprocess to run git
                commands """
                def revision(self):
                    proc = Popen(["git", "--work-tree",
                                  os.path.join(self.path, ".git"),
                                  "rev-parse", "HEAD"], stdout=PIPE,
                                 stderr=PIPE)
                    rv, err = proc.communicate()
                    if proc.wait():
                        raise Exception("Git: Error getting revision from %s: "
                                        "%s" % (self.path, err))
                    return rv.strip()  # pylint: disable=E1103

                def pull(self):
                    proc = Popen(["git", "--work-tree",
                                  os.path.join(self.path, ".git"),
                                  "pull", "--rebase"], stdout=PIPE,
                                 stderr=PIPE)
                    err = proc.communicate()[1].strip()
                    if proc.wait():
                        raise Exception("Git: Error pulling: %s" % err)

        except OSError:
            raise ImportError("Could not import dulwich or GitPython "
                              "libraries, and no 'git' command found in PATH")


class Git(Bcfg2.Server.Plugin.Version):
    """ The Git plugin provides a revision interface for Bcfg2 repos
    using git. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = ".git"
    __rmi__ = Bcfg2.Server.Plugin.Version.__rmi__ + ['Update']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Version.__init__(self, core, datastore)
        self.repo = GitAPI(self.vcs_root)
        self.logger.debug("Initialized git plugin with git directory %s" %
                          self.vcs_path)

    def get_revision(self):
        """Read git revision information for the Bcfg2 repository."""
        try:
            return self.repo.revision()
        except:
            err = sys.exc_info()[1]
            msg = "Failed to read git repository: %s" % err
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

    def Update(self):
        """ Git.Update() => True|False
        Update the working copy against the upstream repository
        """
        try:
            self.repo.pull()
            self.logger.info("Git repo at %s updated to %s" %
                             (self.vcs_root, self.get_revision()))
            return True
        except:  # pylint: disable=W0702
            err = sys.exc_info()[1]
            msg = "Failed to pull from git repository: %s" % err
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
