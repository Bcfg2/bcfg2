'''This module implements a templating generator based on Cheetah'''
__revision__ = '$Revision$'

import Cheetah.Template, Cheetah.Parser
import logging, sys, traceback
import Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.TCheetah')

class TemplateFile:
    '''Template file creates Cheetah template structures for the loaded file'''
    def __init__(self, name, properties, specific, encoding):
        self.name = name
        self.properties = properties
        self.specific = specific
        self.encoding = encoding
        self.template = None
        self.searchlist = {'properties': properties}
    
    def handle_event(self, event):
        '''Handle all fs events for this template'''
        if event.code2str() == 'deleted':
            return
        try:
            s = {'useStackFrames': False}
            self.template = Cheetah.Template.Template(open(self.name).read(),
                                                      compilerSettings=s,
                                                      searchList = [self.searchlist])

        except Cheetah.Parser.ParseError, perror:
            logger.error("Cheetah parse error for file %s" % (self.name))
            logger.error(perror.report())
    
    def bind_entry(self, entry, metadata):
        '''Build literal file information'''
        self.template.metadata = metadata
        self.searchlist['metadata'] = metadata
        self.template.path = entry.get('realname', entry.get('name'))
        self.searchlist['path'] = entry.get('realname', entry.get('name'))
        self.template.source_path = self.name
        self.searchlist['source_path'] = self.name
        
        try:
            if type(self.template) == unicode:
                entry.text = self.template
            else :
                logger.debug("Override encoding of template to %s" % self.encoding)
                entry.text = unicode(str(self.template), self.encoding)
        except:
            (a, b, c) = sys.exc_info()
            msg = traceback.format_exception(a, b, c, limit=2)[-1][:-1]
            logger.error(msg)
            logger.error("TCheetah template error for %s" % self.searchlist['path'])
            del a, b, c
            raise Bcfg2.Server.Plugin.PluginExecutionError


class TCheetah(Bcfg2.Server.Plugin.GroupSpool):
    '''The TCheetah generator implements a templating mechanism for configuration files'''
    __name__ = 'TCheetah'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    filename_pattern = 'template'
    es_child_cls = TemplateFile
    use_props = True
