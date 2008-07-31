'''This module implements a templating generator based on Genshi'''
__revision__ = '$Revision$'

from genshi.template import TemplateLoader, TextTemplate, MarkupTemplate, TemplateError
import logging
import Bcfg2.Server.Plugin
import genshi.core, genshi.input

logger = logging.getLogger('Bcfg2.Plugins.TGenshi')

def removecomment(stream):
    """A genshi filter that removes comments from the stream."""
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos

class TemplateFile:
    '''Template file creates Genshi template structures for the loaded file'''
    def __init__(self, name, properties, specific, encoding):
        self.name = name
        self.properties = properties
        self.specific = specific
        self.encoding = encoding
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
            self.template = loader.load(self.name, cls=self.template_cls,
                                        encoding=self.encoding)
        except TemplateError, terror:
            logger.error('Genshi template error: %s' % terror)
        except genshi.input.ParseError, perror:
            logger.error('Genshi parse error: %s' % perror)
            
    def bind_entry(self, entry, metadata):
        '''Build literal file information'''
        fname = entry.get('realname', entry.get('name'))
        try:
            stream = self.template.generate( \
                name=fname, metadata=metadata, path=self.name,
                properties=self.properties).filter(removecomment)
            if isinstance(self.template, TextTemplate):
                textdata = stream.render('text')
                if type(textdata) == unicode:
                    entry.text = textdata
                else:
                    if self.encoding != 'ascii':
                        logger.debug("Override encoding of %s TGenshi template to %s" % (self.name, self.encoding))
                    entry.text = unicode(textdata, self.encoding)
            else:
                xmldata = stream.render('xml')
                if type(xmldata) == unicode:
                    entry.text = xmldata
                else:
                    if self.encoding != 'ascii':
                        logger.debug("Override encoding of %s TGenshi template to %s" % (self.name, self.encoding))
                    entry.text = unicode(xmldata, self.encoding)
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
