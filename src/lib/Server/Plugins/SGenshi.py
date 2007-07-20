'''This module implements a templating generator based on Genshi'''
__revision__ = '$Revision$'

import genshi.template
import Bcfg2.Server.Plugin
import lxml.etree, logging

logger = logging.getLogger('Bcfg2.Plugins.SGenshi')

class TemplateFile(Bcfg2.Server.Plugin.FileBacked):
    loader = genshi.template.TemplateLoader(auto_reload=True,
                                            max_cache_size=64)
    def HandleEvent(self, _=None):
        self.template = self.loader.load(self.name,
                                         cls=genshi.template.MarkupTemplate)
        
    def GetValue(self, metadata):
        stream = self.template.generate(metadata=metadata)
        data = stream.render('xml')
        return lxml.etree.XML(data)

class SGenshi(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.XMLDirectoryBacked):
    __child__ = TemplateFile
    __name__ = 'SGenshi'
    __version__ = '$Id$'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self,
                                                        self.data,
                                                        self.core.fam)
        
    def BuildStructures(self, metadata):
        return [entry.GetValue(metadata) \
                for entry in self.entries.values()]
            
