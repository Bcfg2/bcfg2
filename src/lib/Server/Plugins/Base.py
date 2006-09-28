'''This module sets up a base list of configuration entries'''
__revision__ = '$Revision$'

import Bcfg2.Server.Plugin
import copy
import lxml.etree

class Base(Bcfg2.Server.Plugin.Plugin, Bcfg2.Server.Plugin.DirectoryBacked):
    '''This Structure is good for the pile of independent configs needed for most actual systems'''
    __name__ =  'Base'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = Bcfg2.Server.Plugin.StructFile
    
    '''base creates independent clauses based on client metadata'''
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.fragements = {}
        try:
            Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data, self.core.fam)
        except OSError:
            self.logger.error("Failed to load Base repository")
            raise Bcfg2.Server.Plugin.PluginInitError
        
    def BuildStructures(self, metadata):
        '''Build structures for client described by metadata'''
        ret = lxml.etree.Element("Independant", version='2.0')
        fragments = reduce(lambda x, y: x+y,
                           [base.Match(metadata) for base in self.entries.values()], [])
        [ret.append(copy.deepcopy(frag)) for frag in fragments]
        return [ret]
