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

        conflict_resolution_map = {
            "base": pysvn.wc_conflict_choice.base,
            "working": pysvn.wc_conflict_choice.working,
            "mine-conflict": pysvn.wc_conflict_choice.mine_conflict,
            "theirs-conflict": pysvn.wc_conflict_choice.theirs_conflict,
            "mine-full": pysvn.wc_conflict_choice.mine_full,
            "theirs-full": pysvn.wc_conflict_choice.theirs_full,
            "none": None
        }
    else:
        __vcs_metadata_path__ = ".svn"

    def callback_conflict_resolver(self, conflict_description):
        """PySvn callback function to resolve conflicts"""
        self.logger.info("Svn: Resolving conflict for %s with %s" % \
                                            (conflict_description['path'], 
                                             self.svn_resolution)
        return self.conflict_resolution_map[self.svn_resolution], None, False

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
            try:
                if self.core.setup.cfg.has_option("svn",
                                                  "conflict_resolution"):
                    self.svn_resolution = self.core.setup.cfp.get("svn", 
                                                        "conflict_resolution")
                    self.client.callback_conflict_resolver = \
                                                self.callback_conflict_resolver
            except ConfigParser.NoSectionError:
                msg = "Svn: No [svn] section found in bcfg2.conf"
                self.logger.warning(msg)
            except ConfigParser.NoOptionError:
                msg = "Svn: Option not found in bcfg2.conf: %s" % \
                sys.exc_info()[1]
                self.logger.warning(msg)

        self.logger.debug("Initialized svn plugin with SVN directory %s" %
                          self.vcs_path)

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
                data = Popen(("env LC_ALL=C svn info %s" %
                             pipes.quote(self.vcs_root)), shell=True,
                             stdout=PIPE).communicate()[0].split('\n')
                return [line.split(': ')[1] for line in data \
                        if line[:9] == 'Revision:'][-1]
            except IndexError:
                msg = "Failed to read svn info"
                self.logger.error('Ran command "svn info %s"' % self.vcs_root)
        self.revision = None
        self.logger.error(msg)
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
            self.logger.info("Updated %s from revision %s to %s" % \
                (self.vcs_root, old_revision, self.revision.number))
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
