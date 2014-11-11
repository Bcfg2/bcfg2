""" The Svn plugin provides a revision interface for Bcfg2 repos using
Subversion. If PySvn libraries are installed, then it exposes two
additional XML-RPC methods for committing data to the repository and
updating the repository. """

import sys
import Bcfg2.Options
import Bcfg2.Server.Plugin
try:
    import pysvn
    HAS_SVN = True
except ImportError:
    from Bcfg2.Utils import Executor
    HAS_SVN = False


class Svn(Bcfg2.Server.Plugin.Version):
    """Svn is a version plugin for dealing with Bcfg2 repos."""
    options = Bcfg2.Server.Plugin.Version.options + [
        Bcfg2.Options.Option(
            cf=("svn", "user"), dest="svn_user", help="SVN username"),
        Bcfg2.Options.Option(
            cf=("svn", "password"), dest="svn_password", help="SVN password"),
        Bcfg2.Options.BooleanOption(
            cf=("svn", "always_trust"), dest="svn_trust_ssl",
            help="Always trust SSL certs from SVN server")]

    if HAS_SVN:
        options.append(
            Bcfg2.Options.Option(
                cf=("svn", "conflict_resolution"),
                dest="svn_conflict_resolution",
                type=lambda v: v.replace("-", "_"),
                # pylint: disable=E1101
                choices=dir(pysvn.wc_conflict_choice),
                default=pysvn.wc_conflict_choice.postpone,
                # pylint: enable=E1101
                help="SVN conflict resolution method"))

    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = ".svn"
    if HAS_SVN:
        __rmi__ = Bcfg2.Server.Plugin.Version.__rmi__ + ['Update', 'Commit']
    else:
        __vcs_metadata_path__ = ".svn"

    def __init__(self, core):
        Bcfg2.Server.Plugin.Version.__init__(self, core)

        self.revision = None
        self.svn_root = None
        self.client = None
        self.cmd = None
        if not HAS_SVN:
            self.logger.debug("Svn: PySvn not found, using CLI interface to "
                              "SVN")
            self.cmd = Executor()
        else:
            self.client = pysvn.Client()
            self.debug_log("Svn: Conflicts will be resolved with %s" %
                           Bcfg2.Options.setup.svn_conflict_resolution)
            self.client.callback_conflict_resolver = self.conflict_resolver

            if Bcfg2.Options.setup.svn_trust_ssl:
                self.client.callback_ssl_server_trust_prompt = \
                    self.ssl_server_trust_prompt

            if (Bcfg2.Options.setup.svn_user and
                    Bcfg2.Options.setup.svn_password):
                self.client.callback_get_login = self.get_login

        self.logger.debug("Svn: Initialized svn plugin with SVN directory %s" %
                          self.vcs_path)

    def get_login(self, realm, username, may_save):  # pylint: disable=W0613
        """ PySvn callback to get credentials for HTTP basic authentication """
        self.logger.debug("Svn: Logging in with username: %s" %
                          Bcfg2.Options.setup.svn_user)
        return (True,
                Bcfg2.Options.setup.svn_user,
                Bcfg2.Options.setup.svn_password,
                False)

    def ssl_server_trust_prompt(self, trust_dict):
        """ PySvn callback to always trust SSL certificates from SVN server """
        self.logger.debug("Svn: Trusting SSL certificate from %s, "
                          "issued by %s for realm %s" %
                          (trust_dict['hostname'],
                           trust_dict['issuer_dname'],
                           trust_dict['realm']))
        return True, trust_dict['failures'], False

    def conflict_resolver(self, conflict_description):
        """ PySvn callback function to resolve conflicts """
        self.logger.info("Svn: Resolving conflict for %s with %s" %
                         (conflict_description['path'],
                          Bcfg2.Options.setup.svn_conflict_resolution))
        return Bcfg2.Options.setup.svn_conflict_resolution, None, False

    def get_revision(self):
        """Read svn revision information for the Bcfg2 repository."""
        msg = None
        if HAS_SVN:
            try:
                info = self.client.info(Bcfg2.Options.setup.vcs_root)
                self.revision = info.revision
                self.svn_root = info.url
                return str(self.revision.number)
            except pysvn.ClientError:  # pylint: disable=E1101
                msg = "Svn: Failed to get revision: %s" % sys.exc_info()[1]
        else:
            result = self.cmd.run(["env LC_ALL=C", "svn", "info",
                                   Bcfg2.Options.setup.vcs_root],
                                  shell=True)
            if result.success:
                self.revision = [line.split(': ')[1]
                                 for line in result.stdout.splitlines()
                                 if line.startswith('Revision:')][-1]
                return self.revision
            else:
                msg = "Failed to read svn info: %s" % result.error
        self.revision = None
        raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

    def Update(self):
        '''Svn.Update() => True|False\nUpdate svn working copy\n'''
        try:
            old_revision = self.revision.number
            self.revision = self.client.update(Bcfg2.Options.setup.vcs_root,
                                               recurse=True)[0]
        except pysvn.ClientError:  # pylint: disable=E1101
            err = sys.exc_info()[1]
            # try to be smart about the error we got back
            details = None
            if "callback_ssl_server_trust_prompt" in str(err):
                details = "SVN server certificate is not trusted"
            elif "callback_get_login" in str(err):
                details = "SVN credentials not cached"

            if details is None:
                self.logger.error("Svn: Failed to update server repository",
                                  exc_info=1)
            else:
                self.logger.error("Svn: Failed to update server repository: "
                                  "%s" % details)
            return False

        if old_revision == self.revision.number:
            self.logger.debug("repository is current")
        else:
            self.logger.info("Updated %s from revision %s to %s" %
                             (Bcfg2.Options.setup.vcs_root, old_revision,
                              self.revision.number))
        return True

    def Commit(self):
        """Svn.Commit() => True|False\nCommit svn repository\n"""
        # First try to update
        if not self.Update():
            self.logger.error("Failed to update svn repository, refusing to "
                              "commit changes")
            return False

        try:
            self.revision = self.client.checkin([Bcfg2.Options.setup.vcs_root],
                                                'Svn: autocommit',
                                                recurse=True)
            self.revision = self.client.update(Bcfg2.Options.setup.vcs_root,
                                               recurse=True)[0]
            self.logger.info("Svn: Commited changes. At %s" %
                             self.revision.number)
            return True
        except pysvn.ClientError:  # pylint: disable=E1101
            err = sys.exc_info()[1]
            # try to be smart about the error we got back
            details = None
            if "callback_ssl_server_trust_prompt" in str(err):
                details = "SVN server certificate is not trusted"
            elif "callback_get_login" in str(err):
                details = "SVN credentials not cached"

            if details is None:
                self.logger.error("Svn: Failed to commit changes",
                                  exc_info=1)
            else:
                self.logger.error("Svn: Failed to commit changes: %s" %
                                  details)
            return False
