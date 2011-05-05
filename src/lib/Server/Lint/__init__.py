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
    return fn

class Plugin (object):
    """ base class for ServerlessPlugin and ServerPlugin """

    def __init__(self, config, errorhandler=None, files=None):
        self.files = files
        self.config = config
        self.logger = logging.getLogger('bcfg2-lint')
        if errorhandler is None:
            self.errorHandler = ErrorHandler()
        else:
            self.errorHandler = errorhandler

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

    def LintError(self, err, msg):
        self.errorHandler.dispatch(err, msg)
    
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


class ErrorHandler (object):
    # how to handle different errors by default
    _errors = {"no-infoxml":"warning",
               "paranoid-false":"warning",
               "bundle-not-found":"error",
               "inconsistent-bundle-name":"warning",
               "group-tag-not-allowed":"error",
               "unexpanded-keywords":"warning",
               "keywords-not-found":"warning",
               "comments-not-found":"warning",
               "broken-xinclude-chain":"warning",
               "duplicate-client":"error",
               "duplicate-group":"error",
               "duplicate-package":"error",
               "multiple-default-groups":"error",
               "required-infoxml-attrs-missing":"error",
               "unknown-path-type":"error",
               "required-attrs-missing":"error",
               "schema-failed-to-parse":"warning",
               "properties-schema-not-found":"warning",
               "xml-failed-to-parse":"error",
               "xml-failed-to-read":"error",
               "xml-failed-to-verify":"error",}

    def __init__(self, config=None):
        self.errors = 0
        self.warnings = 0

        self.logger = logging.getLogger('bcfg2-lint')

        self._handlers = {}
        if config is not None:
            for err, action in config.items():
                if "warn" in action:
                    self._handlers[err] = self.warn
                elif "err" in action:
                    self._handlers[err] = self.error
                else:
                    self._handlers[err] = self.debug

        for err, action in self._errors.items():
            if err not in self._handlers:
                if "warn" in action:
                    self._handlers[err] = self.warn
                elif "err" in action:
                    self._handlers[err] = self.error
                else:
                    self._handlers[err] = self.debug

    def dispatch(self, err, msg):
        if err in self._handlers:
            self._handlers[err](msg)
            self.logger.debug("    (%s)" % err)
        else:
            self.logger.info("Unknown error %s" % err)

    def error(self, msg):
        """ log an error condition """
        self.errors += 1
        lines = msg.splitlines()
        self.logger.error("ERROR: %s" % lines.pop())
        [self.logger.error("  %s" % l) for l in lines]

    def warn(self, msg):
        """ log a warning condition """
        self.warnings += 1
        lines = msg.splitlines()
        self.logger.warning("WARNING: %s" % lines.pop())
        [self.logger.warning("  %s" % l) for l in lines]

    def debug(self, msg):
        """ log a silent/debug condition """
        lines = msg.splitlines()
        [self.logger.debug("%s" % l) for l in lines]


class ServerlessPlugin (Plugin):
    """ base class for plugins that are run before the server starts
    up (i.e., plugins that check things that may prevent the server
    from starting up) """
    pass


class ServerPlugin (Plugin):
    """ base class for plugins that check things that require the
    running Bcfg2 server """
    def __init__(self, lintCore, config, **kwargs):
        Plugin.__init__(self, config, **kwargs)
        self.core = lintCore
        self.logger = self.core.logger
        self.metadata = self.core.metadata
