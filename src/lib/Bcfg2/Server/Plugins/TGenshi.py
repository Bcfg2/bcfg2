"""This module implements a templating generator based on Genshi."""

import logging
import sys
import Bcfg2.Server.Plugin

from Bcfg2.Compat import unicode, b64encode

logger = logging.getLogger('Bcfg2.Plugins.TGenshi')

# try to import genshi stuff
try:
    import genshi.core
    import genshi.input
    from genshi.template import TemplateLoader, \
                                TextTemplate, MarkupTemplate, TemplateError
except ImportError:
    logger.error("TGenshi: Failed to import Genshi. Is it installed?")
    raise
try:
    from genshi.template import NewTextTemplate
    have_ntt = True
except:
    have_ntt = False

def removecomment(stream):
    """A genshi filter that removes comments from the stream."""
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class TemplateFile(object):
    """Template file creates Genshi template structures for the loaded file."""

    def __init__(self, name, specific, encoding):
        self.name = name
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
        elif matchname.endswith('.newtxt'):
            if not have_ntt:
                logger.error("Genshi NewTextTemplates not supported by this version of Genshi")
            else:
                self.template_cls = NewTextTemplate
        else:
            self.template_cls = MarkupTemplate
        self.HandleEvent = self.handle_event

    def handle_event(self, event=None):
        """Handle all fs events for this template."""
        if event and event.code2str() == 'deleted':
            return
        try:
            loader = TemplateLoader()
            try:
                self.template = loader.load(self.name, cls=self.template_cls,
                                            encoding=self.encoding)
            except LookupError:
                lerror = sys.exc_info()[1]
                logger.error('Genshi lookup error: %s' % lerror)
        except TemplateError:
            terror = sys.exc_info()[1]
            logger.error('Genshi template error: %s' % terror)
        except genshi.input.ParseError:
            perror = sys.exc_info()[1]
            logger.error('Genshi parse error: %s' % perror)

    def bind_entry(self, entry, metadata):
        """Build literal file information."""
        fname = entry.get('realname', entry.get('name'))
        if entry.tag == 'Path':
            entry.set('type', 'file')
        try:
            stream = self.template.generate( \
                name=fname, metadata=metadata,
                path=self.name).filter(removecomment)
            if have_ntt:
                ttypes = [TextTemplate, NewTextTemplate]
            else:
                ttypes = [TextTemplate]
            if True in [isinstance(self.template, t) for t in ttypes]:
                try:
                    textdata = stream.render('text', strip_whitespace=False)
                except TypeError:
                    textdata = stream.render('text')
                if type(textdata) == unicode:
                    entry.text = textdata
                else:
                    if entry.get('encoding') == 'base64':
                        # take care of case where file needs base64 encoding
                        entry.text = b64encode(textdata)
                    else:
                        entry.text = unicode(textdata, self.encoding)
            else:
                try:
                    xmldata = stream.render('xml', strip_whitespace=False)
                except TypeError:
                    xmldata = stream.render('xml')
                if type(xmldata) == unicode:
                    entry.text = xmldata
                else:
                    entry.text = unicode(xmldata, self.encoding)
            if entry.text == '':
                entry.set('empty', 'true')
        except TemplateError:
            err = sys.exc_info()[1]
            logger.exception('Genshi template error')
            raise Bcfg2.Server.Plugin.PluginExecutionError('Genshi template error: %s' % err)
        except AttributeError:
            err = sys.exc_info()[1]
            logger.exception('Genshi template loading error')
            raise Bcfg2.Server.Plugin.PluginExecutionError('Genshi template loading error: %s' % err)


class TemplateEntrySet(Bcfg2.Server.Plugin.EntrySet):
    basename_is_regex = True


class TGenshi(Bcfg2.Server.Plugin.GroupSpool):
    """
    The TGenshi generator implements a templating
    mechanism for configuration files.

    """
    name = 'TGenshi'
    __author__ = 'jeff@ocjtech.us'
    filename_pattern = 'template\.(txt|newtxt|xml)'
    es_cls = TemplateEntrySet
    es_child_cls = TemplateFile
    deprecated = True
