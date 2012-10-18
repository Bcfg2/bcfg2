""" The Bzr plugin provides a revision interface for Bcfg2 repos using
bazaar. """

import Bcfg2.Server.Plugin
from bzrlib.workingtree import WorkingTree
from bzrlib import errors


class Bzr(Bcfg2.Server.Plugin.Version):
    """ The Bzr plugin provides a revision interface for Bcfg2 repos
    using bazaar. """
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Version.__init__(self, core, datastore)
        self.logger.debug("Initialized Bazaar plugin with directory %s at "
                          "revision = %s" % (self.vcs_root,
                                             self.get_revision()))

    def get_revision(self):
        """Read Bazaar revision information for the Bcfg2 repository."""
        try:
            working_tree = WorkingTree.open(self.vcs_root)
            revision = str(working_tree.branch.revno())
            if (working_tree.has_changes(working_tree.basis_tree()) or
                working_tree.unknowns()):
                revision += "+"
        except errors.NotBranchError:
            msg = "Failed to read Bazaar branch"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        return revision
