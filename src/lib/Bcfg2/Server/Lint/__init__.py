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
from Bcfg2.Compat import walk_packages

plugins = [m[1] for m in walk_packages(path=__path__)]  # pylint: disable=C0103


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
    """ Base class for all bcfg2-lint plugins """

    def __init__(self, config, errorhandler=None, files=None):
        """
        :param config: A :mod:`Bcfg2.Options` setup dict
        :type config: dict
        :param errorhandler: A :class:`Bcfg2.Server.Lint.ErrorHandler`
                             that will be used to handle lint errors.
                             If one is not provided, a new one will be
                             instantiated.
        :type errorhandler: Bcfg2.Server.Lint.ErrorHandler
        :param files: A list of files to run bcfg2-lint against.  (See
                      the bcfg2-lint ``--stdin`` option.)
        :type files: list of strings
        """

        #: The list of files that bcfg2-lint should be run against
        self.files = files

        #: The Bcfg2.Options setup dict
        self.config = config

        self.logger = logging.getLogger('bcfg2-lint')
        if errorhandler is None:
            #: The error handler
            self.errorhandler = ErrorHandler()
        else:
            self.errorhandler = errorhandler
        self.errorhandler.RegisterErrors(self.Errors())

    def Run(self):
        """ Run the plugin.  Must be overloaded by child classes. """
        raise NotImplementedError

    @classmethod
    def Errors(cls):
        """ Returns a dict of errors the plugin supplies, in a format
        suitable for passing to
        :func:`Bcfg2.Server.Lint.ErrorHandler.RegisterErrors`.

        Must be overloaded by child classes.

        :returns: dict
        """
        raise NotImplementedError

    def HandlesFile(self, fname):
        """ Returns True if the given file should be handled by the
        plugin according to :attr:`Bcfg2.Server.Lint.Plugin.files`,
        False otherwise. """
        return (self.files is None or
                fname in self.files or
                os.path.join(self.config['repo'], fname) in self.files or
                os.path.abspath(fname) in self.files or
                os.path.abspath(os.path.join(self.config['repo'],
                                             fname)) in self.files)

    def LintError(self, err, msg):
        """ Raise an error from the lint process.

        :param err: The name of the error being raised.  This name
                    must be a key in the dict returned by
                    :func:`Bcfg2.Server.Lint.Plugin.Errors`.
        :type err: string
        :param msg: The freeform message to display to the end user.
        :type msg: string
        """
        self.errorhandler.dispatch(err, msg)

    def RenderXML(self, element, keep_text=False):
        """ Render an XML element for error output.  This prefixes the
        line number and removes children for nicer display.

        :param element: The element to render
        :type element: lxml.etree._Element
        :param keep_text: Do not discard text content from the element
                          for display
        :type keep_text: boolean
        """
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


class ErrorHandler(object):
    """ A class to handle errors for bcfg2-lint plugins """

    def __init__(self, errors=None):
        """
        :param config: An initial dict of errors to register
        :type config: dict
        """
        #: The number of errors passed to this error handler
        self.errors = 0

        #: The number of warnings passed to this error handler
        self.warnings = 0

        self.logger = logging.getLogger('bcfg2-lint')

        termsize = get_termsize()
        if termsize is not None and termsize[0] > 0:
            twrap = textwrap.TextWrapper(initial_indent="  ",
                                         subsequent_indent="  ",
                                         width=termsize[0])
            #: A function to wrap text to the width of the terminal
            self._wrapper = twrap.wrap
        else:
            self._wrapper = lambda s: [s]

        #: A dict of registered errors
        self.errortypes = dict()
        if errors is not None:
            self.RegisterErrors(dict(errors.items()))

    def RegisterErrors(self, errors):
        """ Register a dict of errors that a plugin may raise.  The
        keys of the dict are short strings that describe each error;
        the values are the default error handling for that error
        ("error", "warning", or "silent").

        :param errors: The error dict
        :type errors: dict
        """
        for err, action in errors.items():
            if err not in self.errortypes:
                if "warn" in action:
                    self.errortypes[err] = self.warn
                elif "err" in action:
                    self.errortypes[err] = self.error
                else:
                    self.errortypes[err] = self.debug

    def dispatch(self, err, msg):
        """ Dispatch an error to the correct handler.

        :param err: The name of the error being raised.  This name
                    must be a key in
                    :attr:`Bcfg2.Server.Lint.ErrorHandler.errortypes`,
                    the dict of registered errors.
        :type err: string
        :param msg: The freeform message to display to the end user.
        :type msg: string
        """
        if err in self.errortypes:
            self.errortypes[err](msg)
            self.logger.debug("    (%s)" % err)
        else:
            # assume that it's an error, but complain
            self.error(msg)
            self.logger.warning("Unknown error %s" % err)

    def error(self, msg):
        """ Log an error condition.

        :param msg: The freeform message to display to the end user.
        :type msg: string
        """
        self.errors += 1
        self._log(msg, self.logger.error, prefix="ERROR: ")

    def warn(self, msg):
        """ Log a warning condition.

        :param msg: The freeform message to display to the end user.
        :type msg: string
        """
        self.warnings += 1
        self._log(msg, self.logger.warning, prefix="WARNING: ")

    def debug(self, msg):
        """ Log a silent/debug condition.

        :param msg: The freeform message to display to the end user.
        :type msg: string
        """
        self._log(msg, self.logger.debug)

    def _log(self, msg, logfunc, prefix=""):
        """ Generic log function that logs a message with the given
        function after wrapping it for the terminal width. """
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


class ServerlessPlugin(Plugin):  # pylint: disable=W0223
    """ Base class for bcfg2-lint plugins that are run before the
    server starts up (i.e., plugins that check things that may prevent
    the server from starting up). """
    pass


class ServerPlugin(Plugin):  # pylint: disable=W0223
    """ Base class for bcfg2-lint plugins that check things that
    require the running Bcfg2 server. """

    def __init__(self, core, config, errorhandler=None, files=None):
        """
        :param core: The Bcfg2 server core
        :type core: Bcfg2.Server.Core.BaseCore
        :param config: A :mod:`Bcfg2.Options` setup dict
        :type config: dict
        :param errorhandler: A :class:`Bcfg2.Server.Lint.ErrorHandler`
                             that will be used to handle lint errors.
                             If one is not provided, a new one will be
                             instantiated.
        :type errorhandler: Bcfg2.Server.Lint.ErrorHandler
        :param files: A list of files to run bcfg2-lint against.  (See
                      the bcfg2-lint ``--stdin`` option.)
        :type files: list of strings
        """
        Plugin.__init__(self, config, errorhandler=errorhandler, files=files)

        #: The server core
        self.core = core
        self.logger = self.core.logger

        #: The metadata plugin
        self.metadata = self.core.metadata
