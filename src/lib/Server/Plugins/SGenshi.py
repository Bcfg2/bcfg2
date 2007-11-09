'''This module implements a templating generator based on Genshi'''
__revision__ = '$Revision$'

import Bcfg2.Server.Plugin
import lxml.etree, logging

logger = logging.getLogger('Bcfg2.Plugins.SGenshi')

try:
    import genshi.template, genshi.core, genshi.template.base
except:
    logger.error("Failed to load Genshi; disabling SGenshi")
    raise 

def removecomment(stream):
    """A genshi filter that removes comments from the stream."""
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos

class TemplateFile(Bcfg2.Server.Plugin.FileBacked):
    '''Genshi template file object'''
    loader = genshi.template.TemplateLoader(auto_reload=True,
                                            max_cache_size=64)
    def HandleEvent(self, _=None):
        '''Process FAM/GAMIN event'''
        try:
            self.template = self.loader.load(self.name,
                                             cls=genshi.template.MarkupTemplate)
        except genshi.template.base.TemplateSyntaxError, e:
            logger.error("SGenshi: Parse failure due to %s" % (e))
        
    def GetValue(self, metadata):
        '''Build actual structure contents'''
        if not hasattr(self, 'template'):
            logger.error("Template data for %s could not be loaded" % self.name)
            raise Bcfg2.Server.Plugin.PluginExecutionError
        stream = self.template.generate(metadata=metadata).filter(removecomment)
        data = stream.render('xml')
        return lxml.etree.XML(data)

class SGenshi(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.XMLDirectoryBacked):
    '''SGenshi is a structure plugin that provides direct plugin access to templated structures'''
    __child__ = TemplateFile
    __name__ = 'SGenshi'
    __version__ = '$Id$'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        try:
            Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self,
                                                            self.data,
                                                            self.core.fam)
        except:
            logger.error("Failed to load SGenshi repository; disabling SGenshi")
            raise Bcfg2.Server.Plugin.PluginInitError
        
    def BuildStructures(self, metadata):
        '''Build SGenshi structures'''
        ret = []
        for entry in self.entries.values():
            try:
                ret.append(entry.GetValue(metadata))
            except Bcfg2.Server.Plugin.PluginExecutionError:
                logger.error("SGenshi: Failed to template file %s" % entry.name)
        return ret
            
