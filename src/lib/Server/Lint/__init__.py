__revision__ = '$Revision$'

__all__ = ['Bundles',
           'Comments',
           'Duplicates',
           'InfoXML',
           'Pkgmgr',
           'RequiredAttrs',
           'Validate']

import logging
import os.path
from copy import copy
import lxml.etree
import Bcfg2.Logger

def returnErrors(fn):
    """ Decorator for Run method that returns error counts """
    def run(self, *args, **kwargs):
        fn(self, *args, **kwargs)
        return (self.error_count, self.warning_count)

    return run

class Plugin (object):
    """ base class for ServerlessPlugin and ServerPlugin """
    def __init__(self, config, files=None):
        self.files = files
        self.error_count = 0
        self.warning_count = 0
        self.config = config
        Bcfg2.Logger.setup_logging('bcfg2-info', to_syslog=False)
        self.logger = logging.getLogger('bcfg2-lint')

    def Run(self):
        """ run the plugin.  must be overloaded by child classes """
        pass

    def HandlesFile(self, fname):
        """ returns true if the given file should be handled by the
        plugin according to the files list, false otherwise """
        return (self.files is None or
                fname in self.files or
                os.path.join(self.config['repo'], fname) in self.files or
                os.path.abspath(fname) in self.files or
                os.path.abspath(os.path.join(self.config['repo'],
                                             fname)) in self.files)
    
    def LintError(self, msg):
        """ log an error condition """
        self.error_count += 1
        lines = msg.splitlines()
        self.logger.error("ERROR: %s" % lines.pop())
        [self.logger.error("  %s" % l) for l in lines]

    def LintWarning(self, msg):
        """ log a warning condition """
        self.warning_count += 1
        lines = msg.splitlines()
        self.logger.warning("WARNING: %s" % lines.pop())
        [self.logger.warning("  %s" % l) for l in lines]

    def RenderXML(self, element):
        """render an XML element for error output -- line number
        prefixed, no children"""
        xml = None
        if len(element) or element.text:
            el = copy(element)
            if el.text:
                el.text = '...'
            [el.remove(c) for c in el.iterchildren()]
            xml = lxml.etree.tostring(el).strip()
        else:
            xml = lxml.etree.tostring(element).strip()
        return "   line %s: %s" % (element.sourceline, xml)

class ServerlessPlugin (Plugin):
    """ base class for plugins that are run before the server starts
    up (i.e., plugins that check things that may prevent the server
    from starting up) """
    pass

class ServerPlugin (Plugin):
    """ base class for plugins that check things that require the
    running Bcfg2 server """
    def __init__(self, lintCore, config, files=None):
        Plugin.__init__(self, config, files=files)
        self.core = lintCore
        self.logger = self.core.logger
        self.metadata = self.core.metadata
