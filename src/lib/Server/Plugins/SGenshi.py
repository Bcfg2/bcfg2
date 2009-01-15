'''This module implements a templating generator based on Genshi'''
__revision__ = '$Revision$'

import Bcfg2.Server.Plugin, Bcfg2.Server.Plugins.TGenshi
import lxml.etree, logging
import genshi.template

logger = logging.getLogger('Bcfg2.Plugins.SGenshi')

class SGenshiTemplateFile(Bcfg2.Server.Plugins.TGenshi.TemplateFile):
    def get_xml_value(self, metadata):
        stream = self.template.generate(metadata=metadata,
                                        properties=self.properties.properties).filter( \
            Bcfg2.Server.Plugins.TGenshi.removecomment)
        data = stream.render('xml')
        return lxml.etree.XML(data)

class SGenshiEntrySet(Bcfg2.Server.Plugin.EntrySet):
    def __init__(self, path, fam, encoding):
        fpattern = '\S+\.xml'
        try:
            properties = Bcfg2.Server.Plugin.TemplateProperties( \
                    '%s/../etc/properties.xml' % (path), fam)
        except:
            properties = Bcfg2.Server.Plugin.FakeProperties()

        Bcfg2.Server.Plugin.EntrySet.__init__(self, fpattern, path, properties,
                                              SGenshiTemplateFile, encoding)
        fam.AddMonitor(path, self)

    def HandleEvent(self, event):
        '''passthrough event handler for old calling convention'''
        if event.filename != self.path:
            return self.handle_event(event)

    def BuildStructures(self, metadata):
        '''Build SGenshi structures'''
        ret = []
        for entry in self.get_matching(metadata):
            try:
                ret.append(entry.get_xml_value(metadata))
            except genshi.template.TemplateError, terror:
                logger.error('Genshi template error: %s' % terror)
                logger.error("SGenshi: Failed to template file %s" % entry.name)
        return ret

class SGenshi(SGenshiEntrySet,
              Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Structure):
    '''The SGenshi plugin provides templated structures'''
    name = 'SGenshi'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        try:
            SGenshiEntrySet.__init__(self, self.data, self.core.fam, core.encoding)
        except:
            logger.error("Failed to load %s repository; disabling %s" \
                         % (self.name, self.name))
            raise Bcfg2.Server.Plugin.PluginInitError
        

