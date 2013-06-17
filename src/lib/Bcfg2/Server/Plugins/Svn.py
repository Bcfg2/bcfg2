""" The Svn plugin provides a revision interface for Bcfg2 repos using
Subversion. If PySvn libraries are installed, then it exposes two
additional XML-RPC methods for committing data to the repository and
updating the repository. """

import sys
import Bcfg2.Server.Plugin
from Bcfg2.Compat import ConfigParser
try:
    import pysvn
    HAS_SVN = True
except ImportError:
    import pipes
    from subprocess import Popen, PIPE
    HAS_SVN = False


class Svn(Bcfg2.Server.Plugin.Version):
    """Svn is a version plugin for dealing with Bcfg2 repos."""
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __vcs_metadata_path__ = ".svn"
    if HAS_SVN:
        __rmi__ = Bcfg2.Server.Plugin.Version.__rmi__ + ['Update', 'Commit']
    else:
        __vcs_metadata_path__ = ".svn"

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Version.__init__(self, core, datastore)

        self.revision = None
        self.svn_root = None
        if not HAS_SVN:
            self.logger.debug("Svn: PySvn not found, using CLI interface to "
                              "SVN")
            self.client = None
        else:
            self.client = pysvn.Client()
            # pylint: disable=E1101
            choice = pysvn.wc_conflict_choice.postpone
            try:
                resolution = self.core.setup.cfp.get(
                    "svn",
                    "conflict_resolution").replace('-', '_')
                if resolution in ["edit", "launch", "working"]:
                    self.logger.warning("Svn: Conflict resolver %s requires "
                                        "manual intervention, using %s" %
                                        choice)
                else:
                    choice = getattr(pysvn.wc_conflict_choice, resolution)
            except AttributeError:
                self.logger.warning("Svn: Conflict resolver %s does not "
                                    "exist, using %s" % choice)
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                self.logger.info("Svn: No conflict resolution method "
                                 "selected, using %s" % choice)
            # pylint: enable=E1101
            self.debug_log("Svn: Conflicts will be resolved with %s" %
                           choice)
            self.client.callback_conflict_resolver = \
                self.get_conflict_resolver(choice)

            try:
                if self.core.setup.cfp.get(
                        "svn",
                        "always_trust").lower() == "true":
                    self.client.callback_ssl_server_trust_prompt = \
                        self.ssl_server_trust_prompt
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                self.logger.debug("Svn: Using subversion cache for SSL "
                                  "certificate trust")

            try:
                if (self.core.setup.cfp.get("svn", "user") and
                    self.core.setup.cfp.get("svn", "password")):
                    self.client.callback_get_login = \
                        self.get_login
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                self.logger.info("Svn: Using subversion cache for "
                                 "password-based authetication")

        self.logger.debug("Svn: Initialized svn plugin with SVN directory %s" %
                          self.vcs_path)

    # pylint: disable=W0613
    def get_login(self, realm, username, may_save):
        """ PySvn callback to get credentials for HTTP basic authentication """
        self.logger.debug("Svn: Logging in with username: %s" %
                          self.core.setup.cfp.get("svn", "user"))
        return True, \
            self.core.setup.cfp.get("svn", "user"), \
            self.core.setup.cfp.get("svn", "password"), \
            False
    # pylint: enable=W0613

    def ssl_server_trust_prompt(self, trust_dict):
        """ PySvn callback to always trust SSL certificates from SVN server """
        self.logger.debug("Svn: Trusting SSL certificate from %s, "
                          "issued by %s for realm %s" %
                          (trust_dict['hostname'],
                           trust_dict['issuer_dname'],
                           trust_dict['realm']))
        return True, trust_dict['failures'], False

    def get_conflict_resolver(self, choice):
        """ Get a PySvn conflict resolution callback """
        def callback(conflict_description):
            """ PySvn callback function to resolve conflicts """
            self.logger.info("Svn: Resolving conflict for %s with %s" %
                             (conflict_description['path'], choice))
            return choice, None, False

        return callback

    def get_revision(self):
        """Read svn revision information for the Bcfg2 repository."""
        msg = None
        if HAS_SVN:
            try:
                info = self.client.info(self.vcs_root)
                self.revision = info.revision
                self.svn_root = info.url
                return str(self.revision.number)
            except pysvn.ClientError:  # pylint: disable=E1101
                msg = "Svn: Failed to get revision: %s" % sys.exc_info()[1]
        else:
            try:
                data = Popen("env LC_ALL=C svn info %s" %
                             pipes.quote(self.vcs_root), shell=True,
                             stdout=PIPE).communicate()[0].split('\n')
                return [line.split(': ')[1] for line in data
                        if line[:9] == 'Revision:'][-1]
            except IndexError:
                msg = "Failed to read svn info"
                self.logger.error('Ran command "svn info %s"' % self.vcs_root)
        self.revision = None
        raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

    def Update(self):
        '''Svn.Update() => True|False\nUpdate svn working copy\n'''
        try:
            old_revision = self.revision.number
            self.revision = self.client.update(self.vcs_root, recurse=True)[0]
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
                             (self.vcs_root, old_revision,
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
            self.revision = self.client.checkin([self.vcs_root],
                                                'Svn: autocommit',
                                                recurse=True)
            self.revision = self.client.update(self.vcs_root, recurse=True)[0]
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
