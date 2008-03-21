'''This module implements a templating generator based on Genshi'''
__revision__ = '$Revision$'

from genshi.template import TemplateLoader, TextTemplate, MarkupTemplate, TemplateError
import logging
import Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.TGenshi')

class TemplateFile:
    '''Template file creates Genshi template structures for the loaded file'''
    def __init__(self, name, properties, specific):
        self.name = name
        self.properties = properties
        self.specific = specific
        if self.specific.all:
            matchname = self.name
        elif self.specific.group:
            matchname = self.name[:self.name.find('.G')]
        else:
            matchname = self.name[:self.name.find('.H')]
        if matchname.endswith('.txt'):
            self.template_cls = TextTemplate
        else:
            self.template_cls = MarkupTemplate
        
    def handle_event(self, event):
        '''Handle all fs events for this template'''
        if event.code2str() == 'deleted':
            return
        try:
            loader = TemplateLoader()
            self.template = loader.load(self.name, cls=self.template_cls)
        except TemplateError, terror:
            logger.error('Genshi template error: %s' % terror)
            
    def bind_entry(self, entry, metadata):
        '''Build literal file information'''
        fname = entry.get('realname', entry.get('name'))
        try:
            stream = self.template.generate(name=fname,
                                            metadata=metadata,
                                            properties=self.properties)
            if isinstance(self.template, TextTemplate):
                entry.text = stream.render('text')
            else:
                entry.text = stream.render('xml')
        except TemplateError, terror:
            logger.error('Genshi template error: %s' % terror)
            raise Bcfg2.Server.Plugin.PluginExecutionError

class TGenshi(Bcfg2.Server.Plugin.GroupSpool):
    '''The TGenshi generator implements a templating mechanism for configuration files'''
    __name__ = 'TGenshi'
    __version__ = '$Id$'
    __author__ = 'jeff@ocjtech.us'
    use_props = True
    filename_pattern = 'template\.(txt|xml)'
    es_child_cls = TemplateFile
