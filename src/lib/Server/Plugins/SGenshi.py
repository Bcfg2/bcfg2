'''This module implements a templating generator based on Genshi'''
__revision__ = '$Revision$'

import genshi.input
import genshi.template
import lxml.etree
import logging
import copy
import sys
import os.path

import Bcfg2.Server.Plugin
import Bcfg2.Server.Plugins.TGenshi

logger = logging.getLogger('Bcfg2.Plugins.SGenshi')


class SGenshiTemplateFile(Bcfg2.Server.Plugins.TGenshi.TemplateFile,
                          Bcfg2.Server.Plugin.StructFile):
    def __init__(self, name, specific, encoding):
        Bcfg2.Server.Plugins.TGenshi.TemplateFile.__init__(self, name,
                                                           specific, encoding)
        Bcfg2.Server.Plugin.StructFile.__init__(self, name)

    def get_xml_value(self, metadata):
        if not hasattr(self, 'template'):
            logger.error("No parsed template information for %s" % (self.name))
            raise Bcfg2.Server.Plugin.PluginExecutionError
        try:
            stream = self.template.generate(metadata=metadata).filter( \
                Bcfg2.Server.Plugins.TGenshi.removecomment)
            data = lxml.etree.XML(stream.render('xml', strip_whitespace=False))
            bundlename = os.path.splitext(os.path.basename(self.name))[0]
            bundle = lxml.etree.Element('Bundle', name=bundlename)
            for item in self.Match(metadata, data):
                bundle.append(copy.deepcopy(item))
            return bundle
        except LookupError:
            lerror = sys.exc_info()[1]
            logger.error('Genshi lookup error: %s' % lerror)
        except genshi.template.TemplateError:
            terror = sys.exc_info()[1]
            logger.error('Genshi template error: %s' % terror)
            raise
        except genshi.input.ParseError:
            perror = sys.exc_info()[1]
            logger.error('Genshi parse error: %s' % perror)
        raise

    def Match(self, metadata, xdata):
        """Return matching fragments of parsed template."""
        rv = []
        for child in xdata.getchildren():
            rv.extend(self._match(child, metadata))
        logger.debug("File %s got %d match(es)" % (self.name, len(rv)))
        return rv

class SGenshiEntrySet(Bcfg2.Server.Plugin.EntrySet):

    def __init__(self, path, fam, encoding):
        fpattern = '\S+\.xml'
        Bcfg2.Server.Plugin.EntrySet.__init__(self, fpattern, path,
                                              SGenshiTemplateFile, encoding)
        fam.AddMonitor(path, self)

    def HandleEvent(self, event):
        '''passthrough event handler for old calling convention'''
        if event.filename != self.path:
            return self.handle_event(event)

    def BuildStructures(self, metadata):
        """Build SGenshi structures."""
        ret = []
        for entry in self.get_matching(metadata):
            try:
                ret.append(entry.get_xml_value(metadata))
            except:
                logger.error("SGenshi: Failed to template file %s" % entry.name)
        return ret


class SGenshi(SGenshiEntrySet,
              Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Structure):
    """The SGenshi plugin provides templated structures."""
    name = 'SGenshi'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    deprecated = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        try:
            SGenshiEntrySet.__init__(self, self.data, self.core.fam, core.encoding)
        except:
            logger.error("Failed to load %s repository; disabling %s" \
                         % (self.name, self.name))
            raise Bcfg2.Server.Plugin.PluginInitError
