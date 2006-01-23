'''This provides bundle clauses with translation functionality'''
__revision__ = '$Revision$'

import Bcfg2.Server.Plugin
import copy
import lxml.etree

class Bundler(Bcfg2.Server.Plugin.Plugin, Bcfg2.Server.Plugin.DirectoryBacked):
    '''The bundler creates dependent clauses based on the bundle/translation scheme from bcfg1'''
    __name__ =  'Bundler'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = Bcfg2.Server.Plugin.StructFile
    
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        try:
            Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data, self.core.fam)
        except OSError:
            self.LogError("Failed to load Bundle repository")
            raise Bcfg2.Server.Plugin.PluginInitError

    def BuildStructures(self, metadata):
        '''Build all structures for client (metadata)'''
        bundleset = []
        for bundlename in metadata.bundles:
            if not self.entries.has_key("%s.xml"%(bundlename)):
                self.LogError("Client %s requested nonexistent bundle %s" % \
                              (metadata.hostname, bundlename))
                continue
            bundle = lxml.etree.Element('Bundle', name=bundlename)
            [bundle.append(copy.deepcopy(item))
             for item in self.entries["%s.xml" % (bundlename)].Match(metadata)]
            bundleset.append(bundle)
        return bundleset

