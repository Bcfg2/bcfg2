""" Base classes for Lint plugins and error handling """

import os
import sys
import logging
from copy import copy
import textwrap
import lxml.etree
import fcntl
import termios
import struct
from Bcfg2.Server import XI_NAMESPACE
from Bcfg2.Compat import walk_packages

__all__ = [m[1] for m in walk_packages(path=__path__)]


def _ioctl_GWINSZ(fd):  # pylint: disable=C0103
    """ get a tuple of (height, width) giving the size of the window
    from the given file descriptor """
    try:
        return struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except:  # pylint: disable=W0702
        return None


def get_termsize():
    """ get a tuple of (width, height) giving the size of the terminal """
    if not sys.stdout.isatty():
        return None
    dims = _ioctl_GWINSZ(0) or _ioctl_GWINSZ(1) or _ioctl_GWINSZ(2)
    if not dims:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            dims = _ioctl_GWINSZ(fd)
            os.close(fd)
        except:  # pylint: disable=W0702
            pass
    if not dims:
        try:
            dims = (os.environ['LINES'], os.environ['COLUMNS'])
        except KeyError:
            return None
    return int(dims[1]), int(dims[0])


class Plugin(object):
    """ base class for ServerlessPlugin and ServerPlugin """

    def __init__(self, config, errorhandler=None, files=None):
        self.files = files
        self.config = config
        self.logger = logging.getLogger('bcfg2-lint')
        if errorhandler is None:
            self.errorhandler = ErrorHandler()
        else:
            self.errorhandler = errorhandler
        self.errorhandler.RegisterErrors(self.Errors())

    def Run(self):
        """ run the plugin.  must be overloaded by child classes """
        pass

    @classmethod
    def Errors(cls):
        """ returns a dict of errors the plugin supplies.  must be
        overloaded by child classes """

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
        """ record an error in the lint process """
        self.errorhandler.dispatch(err, msg)

    def RenderXML(self, element, keep_text=False):
        """render an XML element for error output -- line number
        prefixed, no children"""
        xml = None
        if len(element) or element.text:
            el = copy(element)
            if el.text and not keep_text:
                el.text = '...'
            for child in el.iterchildren():
                el.remove(child)
            xml = lxml.etree.tostring(
                el,
                xml_declaration=False).decode("UTF-8").strip()
        else:
            xml = lxml.etree.tostring(
                element,
                xml_declaration=False).decode("UTF-8").strip()
        return "   line %s: %s" % (element.sourceline, xml)


class ErrorHandler (object):
    """ a class to handle errors for bcfg2-lint plugins """

    def __init__(self, config=None):
        self.errors = 0
        self.warnings = 0

        self.logger = logging.getLogger('bcfg2-lint')

        termsize = get_termsize()
        if termsize is not None and termsize[0] > 0:
            twrap = textwrap.TextWrapper(initial_indent="  ",
                                         subsequent_indent="  ",
                                         width=termsize[0])
            self._wrapper = twrap.wrap
        else:
            self._wrapper = lambda s: [s]

        self.errortypes = dict()
        if config is not None:
            self.RegisterErrors(dict(config.items()))

    def RegisterErrors(self, errors):
        """ Register a dict of errors (name: default level) that a
        plugin may raise """
        for err, action in errors.items():
            if err not in self.errortypes:
                if "warn" in action:
                    self.errortypes[err] = self.warn
                elif "err" in action:
                    self.errortypes[err] = self.error
                else:
                    self.errortypes[err] = self.debug

    def dispatch(self, err, msg):
        """ Dispatch an error to the correct handler """
        if err in self.errortypes:
            self.errortypes[err](msg)
            self.logger.debug("    (%s)" % err)
        else:
            # assume that it's an error, but complain
            self.error(msg)
            self.logger.warning("Unknown error %s" % err)

    def error(self, msg):
        """ log an error condition """
        self.errors += 1
        self._log(msg, self.logger.error, prefix="ERROR: ")

    def warn(self, msg):
        """ log a warning condition """
        self.warnings += 1
        self._log(msg, self.logger.warning, prefix="WARNING: ")

    def debug(self, msg):
        """ log a silent/debug condition """
        self._log(msg, self.logger.debug)

    def _log(self, msg, logfunc, prefix=""):
        """ Generic log function that logs a message with the given
        function after wrapping it for the terminal width """
        # a message may itself consist of multiple lines.  wrap() will
        # elide them all into a single paragraph, which we don't want.
        # so we split the message into its paragraphs and wrap each
        # paragraph individually.  this means, unfortunately, that we
        # lose textwrap's built-in initial indent functionality,
        # because we want to only treat the very first line of the
        # first paragraph specially.  so we do some silliness.
        rawlines = msg.splitlines()
        firstline = True
        for rawline in rawlines:
            lines = self._wrapper(rawline)
            for line in lines:
                if firstline:
                    logfunc(prefix + line.lstrip())
                    firstline = False
                else:
                    logfunc(line)


class ServerlessPlugin (Plugin):
    """ base class for plugins that are run before the server starts
    up (i.e., plugins that check things that may prevent the server
    from starting up) """
    pass


class ServerPlugin (Plugin):
    """ base class for plugins that check things that require the
    running Bcfg2 server """
    def __init__(self, core, config, **kwargs):
        Plugin.__init__(self, config, **kwargs)
        self.core = core
        self.logger = self.core.logger
        self.metadata = self.core.metadata
        self.errorhandler.RegisterErrors({"broken-xinclude-chain": "warning"})

    def has_all_xincludes(self, mfile):
        """ return true if self.files includes all XIncludes listed in
        the specified metadata type, false otherwise"""
        if self.files is None:
            return True
        else:
            path = os.path.join(self.metadata.data, mfile)
            if path in self.files:
                xdata = lxml.etree.parse(path)
                for el in xdata.findall('./%sinclude' % XI_NAMESPACE):
                    if not self.has_all_xincludes(el.get('href')):
                        self.LintError("broken-xinclude-chain",
                                       "Broken XInclude chain: could not "
                                       "include %s" % path)
                        return False

                return True
