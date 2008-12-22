'''This provides bundle clauses with translation functionality'''
__revision__ = '$Revision$'

import copy, lxml.etree, Bcfg2.Server.Plugin

class Bundler(Bcfg2.Server.Plugin.StructurePlugin,
              Bcfg2.Server.Plugin.XMLDirectoryBacked):
    '''The bundler creates dependent clauses based on the bundle/translation scheme from bcfg1'''
    __name__ =  'Bundler'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = Bcfg2.Server.Plugin.StructFile
    
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        try:
            Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self, self.data, self.core.fam)
        except OSError:
            self.logger.error("Failed to load Bundle repository")
            raise Bcfg2.Server.Plugin.PluginInitError

    def BuildStructures(self, metadata):
        '''Build all structures for client (metadata)'''
        bundleset = []
        for bundlename in metadata.bundles:
            if not ("%s.xml" % bundlename) in self.entries:
                self.logger.error("Client %s requested nonexistent bundle %s" % \
                                  (metadata.hostname, bundlename))
                continue
            bundle = lxml.etree.Element('Bundle', name=bundlename)
            [bundle.append(copy.deepcopy(item))
             for item in self.entries["%s.xml" % (bundlename)].Match(metadata)]
            bundleset.append(bundle)
        return bundleset

