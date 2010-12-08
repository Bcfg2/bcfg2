import Bcfg2.Server.Plugin
from bzrlib.workingtree import WorkingTree
from bzrlib import errors

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Bzr')

class Bzr(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    """Bzr is a version plugin for dealing with Bcfg2 repos."""
    name = 'Bzr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.core = core
        self.datastore = datastore

        # Read revision from bcfg2 repo
        revision = self.get_revision()

        logger.debug("Initialized Bazaar plugin with directory = %(dir)s at revision = %(rev)s" % {'dir': datastore, 'rev': revision})

    def get_revision(self):
        """Read Bazaar revision information for the Bcfg2 repository."""
        try:
            working_tree = WorkingTree.open(self.datastore)
            revision = str(working_tree.branch.revno())
            if working_tree.has_changes(working_tree.basis_tree()) or working_tree.unknowns():
                revision += "+"
        except errors.NotBranchError:
            logger.error("Failed to read Bazaar branch; disabling Bazaar support")
            raise Bcfg2.Server.Plugin.PluginInitError
        return revision
