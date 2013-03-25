"""This module sets up a base list of configuration entries."""

import copy
import lxml.etree
import Bcfg2.Server.Plugin
from itertools import chain


class Base(Bcfg2.Server.Plugin.Plugin,
           Bcfg2.Server.Plugin.Structure,
           Bcfg2.Server.Plugin.XMLDirectoryBacked):
    """This Structure is good for the pile of independent configs
    needed for most actual systems.
    """
    name = 'Base'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = Bcfg2.Server.Plugin.StructFile
    deprecated = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self, self.data,
                                                        self.core.fam)

    def BuildStructures(self, metadata):
        """Build structures for client described by metadata."""
        ret = lxml.etree.Element("Independent", version='2.0')
        fragments = list(chain(*[base.Match(metadata)
                                 for base in list(self.entries.values())]))
        for frag in fragments:
            ret.append(copy.copy(frag))
        return [ret]
