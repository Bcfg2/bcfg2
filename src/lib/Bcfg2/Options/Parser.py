""" The option parser """

import os
import sys
import argparse
from Bcfg2.version import __version__
from Bcfg2.Compat import ConfigParser
from Options import Option, PathOption, BooleanOption

__all__ = ["setup", "OptionParserException", "Parser", "get_parser"]


#: The repository option.  This is specified here (and imported into
#: :module:`Bcfg2.Options.Common`) rather than vice-versa due to
#: circular imports.
repository = PathOption(
    '-Q', '--repository', cf=('server', 'repository'),
    default='var/lib/bcfg2', help="Server repository path")


#: A module-level :class:`argparse.Namespace` object that stores all
#: configuration for Bcfg2.
setup = argparse.Namespace(version=__version__,
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
                            help="Path to configuration file",
                            default="/etc/bcfg2.conf")

    #: Builtin options that apply to all commands
    options = [configfile,
               BooleanOption('--version', help="Print the version and exit"),
               Option('-E', '--encoding', metavar='<encoding>',
                      default='UTF-8', help="Encoding of config files",
                      cf=('components', 'encoding'))]

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
        add_base_options = kwargs.pop('add_base_options', True)

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
        for component in components:
            self.add_component(component)

    def add_options(self, options):
        """ Add an explicit list of options to the parser.  When
        possible, prefer :func:`Bcfg2.Options.Parser.add_component` to
        add a whole component instead."""
        self.parsed = False
        for option in options:
            if option not in self.option_list:
                self.option_list.extend(option.list_options())
                option.add_to_parser(self)

    def add_component(self, component):
        """ Add a component (and all of its options) to the
        parser. """
        if component not in self.components:
            self.components.append(component)
            if hasattr(component, "options"):
                self.add_options(getattr(component, "options"))

    def _set_defaults(self):
        for opt in self.option_list:
            if opt not in self._defaults_set:
                opt.default_from_config(self._cfp)
                self._defaults_set.append(opt)

    def _parse_config_options(self):
        """ populate the namespace with default values for any options
        that aren't already in the namespace (i.e., options without
        CLI arguments) """
        for opt in self.option_list[:]:
            if not opt.args and opt.dest not in self.namespace:
                value = opt.default
                if value:
                    for parser, action in opt.actions.items():
                        if parser is None:
                            action(self, self.namespace, value)
                        else:
                            action(parser, parser.namespace, value)
                else:
                    setattr(self.namespace, opt.dest, value)

    def _finalize(self):
        for opt in self.option_list[:]:
            opt.finalize(self.namespace)

    def _reset_namespace(self):
        self.parsed = False
        for attr in dir(self.namespace):
            if (not attr.startswith("_") and
                attr not in ['uri', 'version', 'name'] and
                attr not in self._config_files):
                delattr(self.namespace, attr)

    def add_config_file(self, dest, cfile):
        """ Add a config file, which triggers a full reparse of all
        options. """
        if dest not in self._config_files:
            self._reset_namespace()
            self._cfp.read([cfile])
            self._defaults_set = []
            self._set_defaults()
            self._parse_config_options()
            self._config_files.append(dest)

    def reparse(self, argv=None):
        """ Reparse options after they have already been parsed.

        :param argv: The argument list to parse.  By default,
                     :attr:`Bcfg2.Options.Parser.argv` is reused.
                     (I.e., the argument list that was initially
                     parsed.)  :type argv: list
        """
        self._reset_namespace()
        self.parse(argv or self.argv)

    def parse(self, argv=None):
        """ Parse options.

        :param argv: The argument list to parse.  By default,
                     ``sys.argv[1:]`` is used.  This is stored in
                     :attr:`Bcfg2.Options.Parser.argv` for reuse by
                     :func:`Bcfg2.Options.Parser.reparse`.  :type
                     argv: list
        """
        if argv is None:
            argv = sys.argv[1:]
        if self.parsed and self.argv == argv:
            return self.namespace
        self.argv = argv

        # phase 1: get and read config file
        bootstrap_parser = argparse.ArgumentParser(add_help=False)
        self.configfile.add_to_parser(bootstrap_parser)
        bootstrap = bootstrap_parser.parse_known_args(args=self.argv)[0]

        # check whether the specified bcfg2.conf exists
        if not os.path.exists(bootstrap.config):
            print("Could not read %s" % bootstrap.config)
            return 1
        self.add_config_file(self.configfile.dest, bootstrap.config)

        # phase 2: re-parse command line, loading additional
        # components, until all components have been loaded.  On each
        # iteration, set defaults from config file/environment
        # variables
        remaining = self.argv
        while not self.parsed:
            self.parsed = True
            self._set_defaults()
            remaining = self.parse_known_args(args=remaining,
                                              namespace=self.namespace)[1]
            self._parse_config_options()
            self._finalize()

        # phase 3: parse command line for real, with all components
        # loaded and all options known
        self._parse_config_options()

        # phase 4: fix up <repository> macros
        repo = getattr(self.namespace, "repository", repository.default)
        for attr in dir(self.namespace):
            value = getattr(self.namespace, attr)
            if not attr.startswith("_") and hasattr(value, "replace"):
                setattr(self.namespace, attr,
                        value.replace("<repository>", repo, 1))

        # phase 5: call post-parsing hooks
        for component in self.components:
            if hasattr(component, "options_parsed_hook"):
                getattr(component, "options_parsed_hook")()

        return self.namespace


#: A module-level :class:`Bcfg2.Options.Parser` object that is used
#: for all parsing
_parser = Parser()

#: Track whether or not the module-level parser has been initialized
#: yet.  We track this separately because some things (e.g., modules
#: that add components on import) will use the parser before it has
#: been initialized, so we can't just set
#: :attr:`Bcfg2.Options._parser` to None and wait for
#: :func:`Bcfg2.Options.get_parser` to be called.
_parser_initialized = False


def get_parser(description=None, components=None, namespace=None):
    """ Get an existing :class:`Bcfg2.Options.Parser` object.  (One is
    created at the module level when :mod:`Bcfg2.Options` is
    imported.)  If no arguments are given, then the existing parser is
    simply fetched.

    If arguments are given, then one of two things happens:

    * If this is the first ``get_parser`` call with arguments, then
      the values given are set accordingly in the parser, and it is
      returned.
    * If this is not the first such call, then
      :class:`Bcfg2.Options.OptionParserException` is raised.

    That is, a ``get_parser`` call with options is considered to
    initialize the parser that already exists, and that can only
    happen once.

    :param description: Set the parser description
    :type description: string
    :param components: Load the given components in the parser
    :type components: list
    :param namespace: Use the given namespace instead of
                      :attr:`Bcfg2.Options.setup`
    :type namespace: argparse.Namespace
    :returns: Bcfg2.Options.Parser object
    """
    if _parser_initialized and (description or components or namespace):
        raise OptionParserException("Parser has already been initialized")
    elif (description or components or namespace):
        if description:
            _parser.description = description
        if components is not None:
            for component in components:
                _parser.add_component(component)
        if namespace:
            _parser.namespace = namespace
    return _parser
