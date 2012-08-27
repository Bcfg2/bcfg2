'''This module implements a templating generator based on Cheetah'''

import logging
import sys
import traceback
import Bcfg2.Server.Plugin

from Bcfg2.Compat import unicode, b64encode

logger = logging.getLogger('Bcfg2.Plugins.TCheetah')

try:
    import Cheetah.Template
    import Cheetah.Parser
except:
    logger.error("TCheetah: Failed to import Cheetah. Is it installed?")
    raise


class TemplateFile:
    """Template file creates Cheetah template structures for the loaded file."""

    def __init__(self, name, specific, encoding):
        self.name = name
        self.specific = specific
        self.encoding = encoding
        self.template = None
        self.searchlist = dict()

    def handle_event(self, event):
        """Handle all fs events for this template."""
        if event.code2str() == 'deleted':
            return
        try:
            s = {'useStackFrames': False}
            self.template = Cheetah.Template.Template(open(self.name).read(),
                                                      compilerSettings=s,
                                                      searchList=self.searchlist)
        except Cheetah.Parser.ParseError:
            perror = sys.exc_info()[1]
            logger.error("Cheetah parse error for file %s" % (self.name))
            logger.error(perror.report())

    def bind_entry(self, entry, metadata):
        """Build literal file information."""
        self.template.metadata = metadata
        self.searchlist['metadata'] = metadata
        self.template.path = entry.get('realname', entry.get('name'))
        self.searchlist['path'] = entry.get('realname', entry.get('name'))
        self.template.source_path = self.name
        self.searchlist['source_path'] = self.name

        if entry.tag == 'Path':
            entry.set('type', 'file')
        try:
            if type(self.template) == unicode:
                entry.text = self.template
            else:
                if entry.get('encoding') == 'base64':
                    # take care of case where file needs base64 encoding
                    entry.text = b64encode(self.template)
                else:
                    entry.text = unicode(str(self.template), self.encoding)
        except:
            (a, b, c) = sys.exc_info()
            msg = traceback.format_exception(a, b, c, limit=2)[-1][:-1]
            logger.error(msg)
            logger.error("TCheetah template error for %s" % self.searchlist['path'])
            del a, b, c
            raise Bcfg2.Server.Plugin.PluginExecutionError


class TCheetah(Bcfg2.Server.Plugin.GroupSpool):
    """The TCheetah generator implements a templating mechanism for configuration files."""
    name = 'TCheetah'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    filename_pattern = 'template'
    es_child_cls = TemplateFile
    deprecated = True
