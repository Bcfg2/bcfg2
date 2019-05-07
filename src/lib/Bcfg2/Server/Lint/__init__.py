""" Base classes for Lint plugins and error handling """

import copy
import fcntl
import fnmatch
import glob
import logging
import os
import struct
import sys
import termios
import textwrap
import time

import lxml.etree


import Bcfg2.Options
import Bcfg2.Server.Core
import Bcfg2.Server.Plugins
from Bcfg2.Compat import walk_packages
from Bcfg2.Options import _debug


def _ioctl_GWINSZ(fd):  # pylint: disable=C0103
    """ get a tuple of (height, width) giving the size of the window
    from the given file descriptor """
    try:
        return struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except (IOError, struct.error):
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
        except IOError:
            pass
    if not dims:
        try:
            dims = (os.environ['LINES'], os.environ['COLUMNS'])
        except KeyError:
            return None
    return int(dims[1]), int(dims[0])


class Plugin(object):
    """ Base class for all bcfg2-lint plugins """

    #: Name of the matching server plugin or None if there is no
    #: matching one. If this is None the lint plugin will only loaded
    #: by default if the matching server plugin is enabled, too.
    __serverplugin__ = None

    options = [Bcfg2.Options.Common.repository]

    def __init__(self, errorhandler=None, files=None):
        """
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
                os.path.join(Bcfg2.Options.setup.repository,
                             fname) in self.files or
                os.path.abspath(fname) in self.files or
                os.path.abspath(os.path.join(Bcfg2.Options.setup.repository,
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
            el = copy.copy(element)
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

    def list_matching_files(self, path):
        """list all files matching the path in self.files or the bcfg2 repo."""
        if self.files is not None:
            return fnmatch.filter(self.files, os.path.join('*', path))
        else:
            return glob.glob(os.path.join(Bcfg2.Options.setup.repository,
                                          path))


class ErrorHandler(object):
    """ A class to handle errors for bcfg2-lint plugins """

    def __init__(self, errors=None):
        """
        :param errors: An initial dict of errors to register
        :type errors: dict
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

    def __init__(self, core, errorhandler=None, files=None):
        """
        :param core: The Bcfg2 server core
        :type core: Bcfg2.Server.Core.BaseCore
        :param errorhandler: A :class:`Bcfg2.Server.Lint.ErrorHandler`
                             that will be used to handle lint errors.
                             If one is not provided, a new one will be
                             instantiated.
        :type errorhandler: Bcfg2.Server.Lint.ErrorHandler
        :param files: A list of files to run bcfg2-lint against.  (See
                      the bcfg2-lint ``--stdin`` option.)
        :type files: list of strings
        """
        Plugin.__init__(self, errorhandler=errorhandler, files=files)

        #: The server core
        self.core = core
        self.logger = self.core.logger

        #: The metadata plugin
        self.metadata = self.core.metadata


class LintPluginAction(Bcfg2.Options.ComponentAction):
    """ Option parser action to load lint plugins """
    bases = ['Bcfg2.Server.Lint']


class LintPluginOption(Bcfg2.Options.Option):
    """ Option class for the lint_plugins """

    def early_parsing_hook(self, namespace):
        """
        We want a usefull default for the enabled lint plugins.
        Therfore we use all importable plugins, that either pertain
        with enabled server plugins or that has no matching plugin.
        """

        plugins = [p.__name__ for p in namespace.plugins]
        for loader, name, _is_pkg in walk_packages(path=__path__):
            try:
                module_name = 'Bcfg2.Server.Lint.%s' % name
                module = loader \
                    .find_module(module_name) \
                    .load_module(module_name)
                plugin = getattr(module, name)
                if plugin.__serverplugin__ is None or \
                   plugin.__serverplugin__ in plugins:
                    _debug("Automatically adding lint plugin %s" %
                           plugin.__name__)
                    self.default.append(plugin.__name__)
            except ImportError:
                pass


class _EarlyOptions(object):
    """ We need the server.plugins options in an early parsing hook
    for determining the default value for the lint_plugins. So we
    create a component that is parsed before the other options. """

    parse_first = True
    options = [Bcfg2.Options.Common.plugins]


class CLI(object):
    """ The bcfg2-lint CLI """
    options = Bcfg2.Server.Core.Core.options + [
        Bcfg2.Options.PathOption(
            '--lint-config', default='/etc/bcfg2-lint.conf',
            action=Bcfg2.Options.ConfigFileAction,
            help='Specify bcfg2-lint configuration file'),
        LintPluginOption(
            "--lint-plugins", cf=('lint', 'plugins'), default=[],
            type=Bcfg2.Options.Types.comma_list, action=LintPluginAction,
            help='bcfg2-lint plugin list'),
        Bcfg2.Options.BooleanOption(
            '--list-errors', help='Show error handling'),
        Bcfg2.Options.BooleanOption(
            '--stdin', help='Operate on a list of files supplied on stdin'),
        Bcfg2.Options.Option(
            cf=("errors", '*'), dest="lint_errors",
            help="How to handle bcfg2-lint errors")]

    def __init__(self):
        parser = Bcfg2.Options.get_parser(
            description="Manage a running Bcfg2 server",
            components=[self, _EarlyOptions])
        parser.parse()

        self.logger = logging.getLogger(parser.prog)

        self.logger.debug("Running lint with plugins: %s" %
                          [p.__name__
                           for p in Bcfg2.Options.setup.lint_plugins])

        if Bcfg2.Options.setup.stdin:
            self.files = [s.strip() for s in sys.stdin.readlines()]
        else:
            self.files = None
        self.errorhandler = self.get_errorhandler()
        self.serverlessplugins = []
        self.serverplugins = []
        for plugin in Bcfg2.Options.setup.lint_plugins:
            if issubclass(plugin, ServerPlugin):
                self.serverplugins.append(plugin)
            else:
                self.serverlessplugins.append(plugin)

    def run(self):
        """ Run bcfg2-lint """
        if Bcfg2.Options.setup.list_errors:
            for plugin in self.serverplugins + self.serverlessplugins:
                self.errorhandler.RegisterErrors(getattr(plugin, 'Errors')())

            print("%-35s %-35s" % ("Error name", "Handler"))
            for err, handler in self.errorhandler.errortypes.items():
                print("%-35s %-35s" % (err, handler.__name__))
            return 0

        if not self.serverplugins and not self.serverlessplugins:
            self.logger.error("No lint plugins loaded!")
            return 1

        self.run_serverless_plugins()

        if self.serverplugins:
            if self.errorhandler.errors:
                # it would be swell if we could try to start the server
                # even if there were errors with the serverless plugins,
                # but since XML parsing errors occur in the FAM thread
                # (not in the core server thread), there's no way we can
                # start the server and try to catch exceptions --
                # bcfg2-lint isn't in the same stack as the exceptions.
                # so we're forced to assume that a serverless plugin error
                # will prevent the server from starting
                print("Serverless plugins encountered errors, skipping server "
                      "plugins")
            else:
                self.run_server_plugins()

        if (self.errorhandler.errors or
                self.errorhandler.warnings or
                Bcfg2.Options.setup.verbose):
            print("%d errors" % self.errorhandler.errors)
            print("%d warnings" % self.errorhandler.warnings)

        if self.errorhandler.errors:
            return 2
        elif self.errorhandler.warnings:
            return 3
        else:
            return 0

    def get_errorhandler(self):
        """ get a Bcfg2.Server.Lint.ErrorHandler object """
        return Bcfg2.Server.Lint.ErrorHandler(
            errors=Bcfg2.Options.setup.lint_errors)

    def run_serverless_plugins(self):
        """ Run serverless plugins """
        self.logger.debug("Running serverless plugins: %s" %
                          [p.__name__ for p in self.serverlessplugins])
        for plugin in self.serverlessplugins:
            self.logger.debug("  Running %s" % plugin.__name__)
            plugin(files=self.files, errorhandler=self.errorhandler).Run()

    def run_server_plugins(self):
        """ run plugins that require a running server to run """
        core = Bcfg2.Server.Core.Core()
        try:
            core.load_plugins()
            core.block_for_fam_events(handle_events=True)
            self.logger.debug("Running server plugins: %s" %
                              [p.__name__ for p in self.serverplugins])
            for plugin in self.serverplugins:
                self.logger.debug("  Running %s" % plugin.__name__)
                plugin(core,
                       files=self.files, errorhandler=self.errorhandler).Run()
        finally:
            core.shutdown()

    def _run_plugin(self, plugin, args=None):
        """ Run a single bcfg2-lint plugin """
        if args is None:
            args = []
        start = time.time()
        # python 2.5 doesn't support mixing *magic and keyword arguments
        kwargs = dict(files=self.files, errorhandler=self.errorhandler)
        rv = plugin(*args, **kwargs).Run()
        self.logger.debug("  Ran %s in %0.2f seconds" % (plugin.__name__,
                                                         time.time() - start))
        return rv
