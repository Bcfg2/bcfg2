""" The Svn2 plugin provides a revision interface for Bcfg2 repos using
Subversion. It uses a pure python backend and exposes two additional
XML-RPC methods. """

import sys
import Bcfg2.Server.Plugin
try:
    import pysvn
    HAS_SVN = False
except ImportError:
    HAS_SVN = True


class Svn2(Bcfg2.Server.Plugin.Plugin,
           Bcfg2.Server.Plugin.Version):
    """Svn is a version plugin for dealing with Bcfg2 repos."""
    __author__ = 'bcfg-dev@mcs.anl.gov'

    conflicts = ['Svn']
    __rmi__ = Bcfg2.Server.Plugin.Plugin.__rmi__ + ['Update', 'Commit']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self, datastore)

        if HAS_SVN:
            msg = "Missing PySvn"
            self.logger.error("Svn2: " + msg)
            raise Bcfg2.Server.Plugin.PluginInitError(msg)

        self.client = pysvn.Client()

        self.svn_root = None
        self.revision = None

        # Read revision from bcfg2 repo
        revision = self.get_revision()
        if not self.revision:
            raise Bcfg2.Server.Plugin.PluginInitError("Failed to get revision")

        self.logger.debug("Initialized svn plugin with svn root %s at "
                          "revision %s" % (self.svn_root, revision))

    def get_revision(self):
        """Read svn revision information for the Bcfg2 repository."""
        try:
            info = self.client.info(self.datastore)
            self.revision = info.revision
            self.svn_root = info.url
            return str(self.revision.number)
        except pysvn.ClientError:  # pylint: disable=E1101
            self.logger.error("Svn2: Failed to get revision", exc_info=1)
            self.revision = None
        return str(-1)

    def Update(self):
        '''Svn2.Update() => True|False\nUpdate svn working copy\n'''
        try:
            old_revision = self.revision.number
            self.revision = self.client.update(self.datastore, recurse=True)[0]
        except pysvn.ClientError:  # pylint: disable=E1101
            err = sys.exc_info()[1]
            # try to be smart about the error we got back
            details = None
            if "callback_ssl_server_trust_prompt" in str(err):
                details = "SVN server certificate is not trusted"
            elif "callback_get_login" in str(err):
                details = "SVN credentials not cached"

            if details is None:
                self.logger.error("Svn2: Failed to update server repository",
                                  exc_info=1)
            else:
                self.logger.error("Svn2: Failed to update server repository: "
                                  "%s" % details)
            return False

        if old_revision == self.revision.number:
            self.logger.debug("repository is current")
        else:
            self.logger.info("Updated %s from revision %s to %s" % \
                (self.datastore, old_revision, self.revision.number))
        return True

    def Commit(self):
        """Svn2.Commit() => True|False\nCommit svn repository\n"""
        # First try to update
        if not self.Update():
            self.logger.error("Failed to update svn repository, refusing to "
                              "commit changes")
            return False

        try:
            self.revision = self.client.checkin([self.datastore],
                                                'Svn2: autocommit',
                                                recurse=True)
            self.revision = self.client.update(self.datastore, recurse=True)[0]
            self.logger.info("Svn2: Commited changes. At %s" %
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
                self.logger.error("Svn2: Failed to commit changes",
                                  exc_info=1)
            else:
                self.logger.error("Svn2: Failed to commit changes: %s" %
                                  details)
            return False
