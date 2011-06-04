"""This module sets up a base list of configuration entries."""
__revision__ = '$Revision$'

import copy
import lxml.etree
import sys
# py3k compatibility
if sys.hexversion >= 0x03000000:
    from functools import reduce

import Bcfg2.Server.Plugin


class Base(Bcfg2.Server.Plugin.Plugin,
           Bcfg2.Server.Plugin.Structure,
           Bcfg2.Server.Plugin.XMLDirectoryBacked):
    """This Structure is good for the pile of independent configs
    needed for most actual systems.
    """
    name = 'Base'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = Bcfg2.Server.Plugin.StructFile
    deprecated = True

    """Base creates independent clauses based on client metadata."""
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        try:
            Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self,
                                                            self.data,
                                                            self.core.fam)
        except OSError:
            self.logger.error("Failed to load Base repository")
            raise Bcfg2.Server.Plugin.PluginInitError

    def BuildStructures(self, metadata):
        """Build structures for client described by metadata."""
        ret = lxml.etree.Element("Independent", version='2.0')
        fragments = reduce(lambda x, y: x + y,
                           [base.Match(metadata) for base
                            in list(self.entries.values())], [])
        [ret.append(copy.deepcopy(frag)) for frag in fragments]
        return [ret]
