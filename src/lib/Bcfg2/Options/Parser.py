"""The option parser."""

import argparse
import os
import sys

from Bcfg2.version import __version__
from Bcfg2.Compat import ConfigParser
from Bcfg2.Options import Option, PathOption, _debug

__all__ = ["setup", "OptionParserException", "Parser", "get_parser",
           "new_parser"]


#: The repository option.  This is specified here (and imported into
#: :module:`Bcfg2.Options.Common`) rather than vice-versa due to
#: circular imports.
repository = PathOption(  # pylint: disable=C0103
    '-Q', '--repository', cf=('server', 'repository'),
    default='var/lib/bcfg2', help="Server repository path")


#: A module-level :class:`argparse.Namespace` object that stores all
#: configuration for Bcfg2.
setup = argparse.Namespace(version=__version__,  # pylint: disable=C0103
                           name="Bcfg2",
                           uri='http://trac.mcs.anl.gov/projects/bcfg2')


class OptionParserException(Exception):
    """ Base exception raised for generic option parser errors """


class Parser(argparse.ArgumentParser):
    """ The Bcfg2 option parser.  Most interfaces should not need to
    instantiate a parser, but should instead use
    :func:`Bcfg2.Options.get_parser` to get the parser that already
    exists."""

    #: Option for specifying the path to the Bcfg2 config file
    configfile = PathOption('-C', '--config',
                            env="BCFG2_CONFIG_FILE",
                            help="Path to configuration file",
                            default="/etc/bcfg2.conf")

    #: Verbose version string that is printed if executed with --version
    _version_string = "%s %s on Python %s" % (
        os.path.basename(sys.argv[0]),
        __version__,
        ".".join(str(v) for v in sys.version_info[0:3]))

    #: Builtin options that apply to all commands
    options = [configfile,
               Option('--version', help="Print the version and exit",
                      action="version", version=_version_string),
               Option('-E', '--encoding', metavar='<encoding>',
                      default='UTF-8', help="Encoding of config files",
                      cf=('components', 'encoding'))]

    #: Flag used in unit tests to disable actual config file reads
    unit_test = False

    def __init__(self, **kwargs):
        """ See :class:`argparse.ArgumentParser` for a full list of
        accepted parameters.

        In addition to supporting all arguments and keyword arguments
        from :class:`argparse.ArgumentParser`, several additional
        keyword arguments are allowed.

        :param components: A list of components to add to the parser.
        :type components: list
        :param namespace: The namespace to store options in.  Default
                          is :attr:`Bcfg2.Options.setup`.
        :type namespace: argparse.Namespace
        :param add_base_options: Whether or not to add the options in
                                 :attr:`Bcfg2.Options.Parser.options`
                                 to the parser.  Setting this to False
                                 is default for subparsers. Default is
                                 True.
        :type add_base_options: bool
        """
        self._cfp = ConfigParser.ConfigParser()
        components = kwargs.pop('components', [])

        #: The namespace options will be stored in.
        self.namespace = kwargs.pop('namespace', setup)
        if self.namespace is None:
            self.namespace = setup
        add_base_options = kwargs.pop('add_base_options', True)

        #: Flag to indicate that this is the pre-parsing 'early' run
        #: for important options like database settings that must be
        #: loaded before other components can be.
        self._early = kwargs.pop('early', False)

        if 'add_help' not in kwargs:
            kwargs['add_help'] = add_base_options
        argparse.ArgumentParser.__init__(self, **kwargs)

        #: Whether or not parsing has completed on all current options.
        self.parsed = False

        #: The argument list that was parsed.
        self.argv = None

        #: Components that have been added to the parser
        self.components = []

        #: Options that have been added to the parser
        self.option_list = []
        self._defaults_set = []
        self._config_files = []
        if add_base_options:
            self.add_component(self)
        if components:
            for component in components:
                self.add_component(component)

    def _check_duplicate_cf(self, option):
        """Check for a duplicate config file option."""

    def add_options(self, options):
        """ Add an explicit list of options to the parser.  When
        possible, prefer :func:`Bcfg2.Options.Parser.add_component` to
        add a whole component instead."""
        _debug("Adding options: %s" % options)
        self.parsed = False
        for option in options:
            if option not in self.option_list:
                # check for duplicates
                if (hasattr(option, "env") and option.env and
                        option.env in [o.env for o in self.option_list]):
                    raise OptionParserException(
                        "Duplicate environment variable option: %s" %
                        option.env)
                if (hasattr(option, "cf") and option.cf and
                        option.cf in [o.cf for o in self.option_list]):
                    raise OptionParserException(
                        "Duplicate config file option: %s" % (option.cf,))

                self.option_list.extend(option.list_options())
                option.add_to_parser(self)
                for opt in option.list_options():
                    opt.default_from_config(self._cfp)
                    self._defaults_set.append(opt)

    def add_component(self, component):
        """ Add a component (and all of its options) to the
        parser. """
        if component not in self.components:
            _debug("Adding component %s to %s" % (component, self))
            self.components.append(component)
            if hasattr(component, "options"):
                self.add_options(getattr(component, "options"))

    def _set_defaults_from_config(self):
        """ Set defaults from the config file for all options that can
        come from the config file, but haven't yet had their default
        set """
        _debug("Setting defaults on all options")
        for opt in self.option_list:
            if opt not in self._defaults_set:
                opt.default_from_config(self._cfp)
                self._defaults_set.append(opt)

    def _parse_config_options(self):
        """ populate the namespace with default values for any options
        that aren't already in the namespace (i.e., options without
        CLI arguments) """
        _debug("Parsing config file-only options")
        for opt in self.option_list[:]:
            if not opt.args and opt.dest not in self.namespace:
                value = opt.default
                if value:
                    for _, action in opt.actions.items():
                        _debug("Setting config file-only option %s to %s" %
                               (opt, value))
                        action(self, self.namespace, value)
                else:
                    _debug("Setting config file-only option %s to %s" %
                           (opt, value))
                    setattr(self.namespace, opt.dest, value)

    def _finalize(self):
        """ Finalize the value of any options that require that
        additional post-processing step.  (Mostly
        :class:`Bcfg2.Options.Actions.ComponentAction` subclasses.)
        """
        _debug("Finalizing options")
        for opt in self.option_list[:]:
            opt.finalize(self.namespace)

    def _reset_namespace(self):
        """ Delete all options from the namespace except for a few
        predefined values and config file options. """
        self.parsed = False
        _debug("Resetting namespace")
        for attr in dir(self.namespace):
            if (not attr.startswith("_") and
                    attr not in ['uri', 'version', 'name'] and
                    attr not in self._config_files):
                _debug("Deleting %s" % attr)
                delattr(self.namespace, attr)

    def _parse_early_options(self):
        """Parse early options.

        Early options are options that need to be parsed before other
        options for some reason. These fall into two basic cases:

        1. Database options, which need to be parsed so that Django
           modules can be imported, since Django configuration is all
           done at import-time;
        2. The repository (``-Q``) option, so that ``<repository>``
           macros in other options can be resolved.
        """
        _debug("Option parsing phase 2: Parse early options")
        early_opts = argparse.Namespace()
        early_parser = Parser(add_help=False, namespace=early_opts,
                              early=True)

        # add the repo option so we can resolve <repository>
        # macros
        early_parser.add_options([repository])

        early_components = []
        for component in self.components:
            if getattr(component, "parse_first", False):
                early_components.append(component)
                early_parser.add_component(component)
        early_parser.parse(self.argv)

        _debug("Fixing up <repository> macros in early options")
        for attr_name in dir(early_opts):
            if not attr_name.startswith("_"):
                attr = getattr(early_opts, attr_name)
                if hasattr(attr, "replace"):
                    setattr(early_opts, attr_name,
                            attr.replace("<repository>",
                                         early_opts.repository))

        _debug("Early parsing complete, calling hooks")
        for component in early_components:
            if hasattr(component, "component_parsed_hook"):
                _debug("Calling component_parsed_hook on %s" % component)
                getattr(component, "component_parsed_hook")(early_opts)
        _debug("Calling early parsing hooks; early options: %s" %
               early_opts)
        for option in self.option_list:
            option.early_parsing_hook(early_opts)

    def add_config_file(self, dest, cfile, reparse=True):
        """ Add a config file, which triggers a full reparse of all
        options. """
        if dest not in self._config_files:
            _debug("Adding new config file %s for %s" % (cfile, dest))
            self._reset_namespace()
            self._cfp.read([cfile])
            self._defaults_set = []
            self._set_defaults_from_config()
            if reparse:
                self._parse_config_options()
            self._config_files.append(dest)

    def reparse(self, argv=None):
        """ Reparse options after they have already been parsed.

        :param argv: The argument list to parse. By default,
                     :attr:`Bcfg2.Options.Parser.argv` is reused.
                     (I.e., the argument list that was initially
                     parsed.)
        :type argv: list
        """
        _debug("Reparsing all options")
        self._reset_namespace()
        self.parse(argv or self.argv)

    def parse(self, argv=None):
        """ Parse options.

        :param argv: The argument list to parse.  By default,
                     ``sys.argv[1:]`` is used.  This is stored in
                     :attr:`Bcfg2.Options.Parser.argv` for reuse by
                     :func:`Bcfg2.Options.Parser.reparse`.
        :type argv: list
        """
        _debug("Parsing options")
        if argv is None:
            argv = sys.argv[1:]  # pragma: nocover
        if self.parsed and self.argv == argv:
            _debug("Returning already parsed namespace")
            return self.namespace
        self.argv = argv

        # phase 1: get and read config file
        _debug("Option parsing phase 1: Get and read main config file")
        bootstrap_parser = argparse.ArgumentParser(add_help=False)
        self.configfile.add_to_parser(bootstrap_parser)
        self.configfile.default_from_config(self._cfp)
        bootstrap = bootstrap_parser.parse_known_args(args=self.argv)[0]

        # check whether the specified bcfg2.conf exists
        if not self.unit_test and not os.path.exists(bootstrap.config):
            self.error("Could not read %s" % bootstrap.config)
        self.add_config_file(self.configfile.dest, bootstrap.config,
                             reparse=False)

        # phase 2: re-parse command line for early options; currently,
        # that's database options
        if not self._early:
            self._parse_early_options()
        else:
            _debug("Skipping parsing phase 2 in early mode")

        # phase 3: re-parse command line, loading additional
        # components, until all components have been loaded.  On each
        # iteration, set defaults from config file/environment
        # variables
        _debug("Option parsing phase 3: Main parser loop")
        # _set_defaults_from_config must be called before _parse_config_options
        # This is due to a tricky interaction between the two methods:
        #
        # (1) _set_defaults_from_config does what its name implies, it updates
        # the "default" property of each Option based on the value that exists
        # in the config.
        #
        # (2)  _parse_config_options will look at each option and set it to the
        # default value that is _currently_ defined.  If the option does not
        # exist in the namespace, it will be added.  The method carefully
        # avoids overwriting the value of an option that is already defined in
        # the namespace.
        #
        # Thus, if _set_defaults_from_config has not been called yet when
        # _parse_config_options is called, all config file options will get set
        # to their hardcoded defaults.  This process defines the options in the
        # namespace and _parse_config_options will never look at them again.
        #
        # we have to do the parsing in two loops: first, we squeeze as
        # much data out of the config file as we can to ensure that
        # all config file settings are read before we use any default
        # values. then we can start looking at the command line.
        while not self.parsed:
            self.parsed = True
            self._set_defaults_from_config()
            self._parse_config_options()
        self.parsed = False
        remaining = []
        while not self.parsed:
            self.parsed = True
            _debug("Parsing known arguments")
            try:
                _, remaining = self.parse_known_args(args=self.argv,
                                                     namespace=self.namespace)
            except OptionParserException:
                self.error(sys.exc_info()[1])
            self._set_defaults_from_config()
            self._parse_config_options()
            self._finalize()
        if len(remaining) and not self._early:
            self.error("Unknown options: %s" % " ".join(remaining))

        # phase 4: call post-parsing hooks
        if not self._early:
            _debug("Option parsing phase 4: Call hooks")
            for component in self.components:
                if hasattr(component, "options_parsed_hook"):
                    _debug("Calling post-parsing hook on %s" % component)
                    getattr(component, "options_parsed_hook")()

        return self.namespace


#: A module-level :class:`Bcfg2.Options.Parser` object that is used
#: for all parsing
_parser = Parser()  # pylint: disable=C0103


def new_parser():
    """Create a new :class:`Bcfg2.Options.Parser` object.

    The new object can be retrieved with
    :func:`Bcfg2.Options.get_parser`.  This is useful for unit
    testing.
    """
    global _parser
    _parser = Parser()


def get_parser(description=None, components=None, namespace=None):
    """Get an existing :class:`Bcfg2.Options.Parser` object.

    A Parser is created at the module level when :mod:`Bcfg2.Options`
    is imported. If any arguments are given, then the existing parser
    is modified before being returned.

    :param description: Set the parser description
    :type description: string
    :param components: Load the given components in the parser
    :type components: list
    :param namespace: Use the given namespace instead of
                      :attr:`Bcfg2.Options.setup`
    :type namespace: argparse.Namespace
    :returns: Bcfg2.Options.Parser object
    """
    if Parser.unit_test:
        return Parser(description=description, components=components,
                      namespace=namespace)
    elif (description or components or namespace):
        if description:
            _parser.description = description
        if components is not None:
            for component in components:
                _parser.add_component(component)
        if namespace:
            _parser.namespace = namespace
    return _parser
