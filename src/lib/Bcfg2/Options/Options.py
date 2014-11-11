"""Base :class:`Bcfg2.Options.Option` object to represent an option.

Unlike options in :mod:`argparse`, an Option object does not need to
be associated with an option parser; it exists on its own.
"""

import argparse
import copy
import fnmatch
import os
import sys

from Bcfg2.Options import Types
from Bcfg2.Compat import ConfigParser


__all__ = ["Option", "BooleanOption", "RepositoryMacroOption", "PathOption",
           "PositionalArgument", "_debug"]

unit_test = False  # pylint: disable=C0103


def _debug(msg):
    """ Option parsing happens before verbose/debug have been set --
    they're options, after all -- so option parsing verbosity is
    enabled by changing this to True. The verbosity here is primarily
    of use to developers. """
    if unit_test:
        print("DEBUG: %s" % msg)
    elif os.environ.get('BCFG2_OPTIONS_DEBUG', '0').lower() in ["true", "yes",
                                                                "on", "1"]:
        sys.stderr.write("%s\n" % msg)


#: A dict that records a mapping of argparse action name (e.g.,
#: "store_true") to the argparse Action class for it.  See
#: :func:`_get_action_class`
_action_map = dict()  # pylint: disable=C0103


def _get_action_class(action_name):
    """ Given an argparse action name (e.g., "store_true"), get the
    related :class:`argparse.Action` class.  The mapping that stores
    this information in :mod:`argparse` itself is unfortunately
    private, so it's an implementation detail that we shouldn't depend
    on.  So we just instantiate a dummy parser, add a dummy argument,
    and determine the class that way. """
    if (isinstance(action_name, type) and
            issubclass(action_name, argparse.Action)):
        return action_name
    if action_name not in _action_map:
        action = argparse.ArgumentParser().add_argument(action_name,
                                                        action=action_name)
        _action_map[action_name] = action.__class__
    return _action_map[action_name]


class Option(object):
    """ Representation of an option that can be specified on the
    command line, as an environment variable, or in a config
    file. Precedence is in that order; that is, an option specified on
    the command line takes precendence over an option given by the
    environment, which takes precedence over an option specified in
    the config file. """

    #: Keyword arguments that should not be passed on to the
    #: :class:`argparse.ArgumentParser` constructor
    _local_args = ['cf', 'env', 'man']

    def __init__(self, *args, **kwargs):
        """ See :meth:`argparse.ArgumentParser.add_argument` for a
        full list of accepted parameters.

        In addition to supporting all arguments and keyword arguments
        from :meth:`argparse.ArgumentParser.add_argument`, several
        additional keyword arguments are allowed.

        :param cf: A tuple giving the section and option name that
                   this argument can be referenced as in the config
                   file.  The option name may contain the wildcard
                   '*', in which case the value will be a dict of all
                   options matching the glob.  (To use a wildcard in
                   the section, use a
                   :class:`Bcfg2.Options.WildcardSectionGroup`.)
        :type cf: tuple
        :param env: An environment variable that the value of this
                    option can be taken from.
        :type env: string
        :param man: A detailed description of the option that will be
                    used to populate automatically-generated manpages.
        :type man: string
        """
        #: The options by which this option can be called.
        #: (Coincidentally, this is also the list of arguments that
        #: will be passed to
        #: :meth:`argparse.ArgumentParser.add_argument` when this
        #: option is added to a parser.)  As a result, ``args`` can be
        #: tested to see if this argument can be given on the command
        #: line at all, or if it is purely a config file option.
        self.args = args
        self._kwargs = kwargs

        #: The tuple giving the section and option name for this
        #: option in the config file
        self.cf = None  # pylint: disable=C0103

        #: The environment variable that this option can take its
        #: value from
        self.env = None

        #: A detailed description of this option that will be used in
        #: man pages.
        self.man = None

        #: A list of :class:`Bcfg2.Options.Parser` objects to which
        #: this option has been added.  (There will be more than one
        #: parser if this option is added to a subparser, for
        #: instance.)
        self.parsers = []

        #: A dict of :class:`Bcfg2.Options.Parser` ->
        #: :class:`argparse.Action` that gives the actions that
        #: resulted from adding this option to each parser that it was
        #: added to.  If this option cannot be specified on the
        #: command line (i.e., it only takes its value from the config
        #: file), then this will be empty.
        self.actions = dict()

        self.type = self._kwargs.get("type")
        self.help = self._kwargs.get("help")
        self._default = self._kwargs.get("default")
        for kwarg in self._local_args:
            setattr(self, kwarg, self._kwargs.pop(kwarg, None))
        if self.args:
            # cli option
            self._dest = None
        else:
            action_cls = _get_action_class(self._kwargs.get('action', 'store'))
            # determine the name of this option.  use, in order, the
            # 'name' kwarg; the option name; the environment variable
            # name.
            self._dest = None
            if 'dest' in self._kwargs:
                self._dest = self._kwargs.pop('dest')
            elif self.env is not None:
                self._dest = self.env
            elif self.cf is not None:
                self._dest = self.cf[1]
            self._dest = self._dest.lower().replace("-", "_")
            kwargs = copy.copy(self._kwargs)
            kwargs.pop("action", None)
            self.actions[None] = action_cls(self._dest, self._dest, **kwargs)

    def __repr__(self):
        sources = []
        if self.args:
            sources.extend(self.args)
        if self.cf:
            sources.append("%s.%s" % self.cf)
        if self.env:
            sources.append("$" + self.env)
        spec = ["sources=%s" % sources, "default=%s" % self.default,
                "%d parsers" % len(self.parsers)]
        return '%s(%s: %s)' % (self.__class__.__name__,
                               self.dest, ", ".join(spec))

    def list_options(self):
        """ List options contained in this option.  This exists to
        provide a consistent interface with
        :class:`Bcfg2.Options.OptionGroup` """
        return [self]

    def finalize(self, namespace):
        """ Finalize the default value for this option.  This is used
        with actions (such as :class:`Bcfg2.Options.ComponentAction`)
        that allow you to specify a default in a different format than
        its final storage format; this can be called after it has been
        determined that the default will be used (i.e., the option is
        not given on the command line or in the config file) to store
        the appropriate default value in the appropriate format."""
        for parser, action in self.actions.items():
            if hasattr(action, "finalize"):
                if parser:
                    _debug("Finalizing %s for %s" % (self, parser))
                else:
                    _debug("Finalizing %s" % self)
                action.finalize(parser, namespace)

    @property
    def _type_func(self):
        """get a function for converting a value to the option type.

        this always returns a callable, even when ``type`` is None.
        """
        if self.type:
            return self.type
        else:
            return lambda x: x

    def from_config(self, cfp):
        """ Get the value of this option from the given
        :class:`ConfigParser.ConfigParser`.  If it is not found in the
        config file, the default is returned.  (If there is no
        default, None is returned.)

        :param cfp: The config parser to get the option value from
        :type cfp: ConfigParser.ConfigParser
        :returns: The default value
        """
        if not self.cf:
            return None
        if '*' in self.cf[1]:
            if cfp.has_section(self.cf[0]):
                # build a list of known options in this section, and
                # exclude them
                exclude = set()
                for parser in self.parsers:
                    exclude.update(o.cf[1]
                                   for o in parser.option_list
                                   if o.cf and o.cf[0] == self.cf[0])
                rv = dict([(o, cfp.get(self.cf[0], o))
                           for o in fnmatch.filter(cfp.options(self.cf[0]),
                                                   self.cf[1])
                           if o not in exclude])
            else:
                rv = {}
        else:
            try:
                rv = self._type_func(self.get_config_value(cfp))
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                rv = None
        _debug("Getting value of %s from config file(s): %s" % (self, rv))
        return rv

    def get_config_value(self, cfp):
        """fetch a value from the config file.

        This is passed the config parser. Its result is passed to the
        type function for this option. It can be overridden to, e.g.,
        handle boolean options.
        """
        return cfp.get(*self.cf)

    def get_environ_value(self, value):
        """fetch a value from the environment.

        This is passed the raw value from the environment variable,
        and its result is passed to the type function for this
        option. It can be overridden to, e.g., handle boolean options.
        """
        return value

    def default_from_config(self, cfp):
        """ Set the default value of this option from the config file
        or from the environment.

        :param cfp: The config parser to get the option value from
        :type cfp: ConfigParser.ConfigParser
        """
        if self.env and self.env in os.environ:
            self.default = self._type_func(
                self.get_environ_value(os.environ[self.env]))
            _debug("Setting the default of %s from environment: %s" %
                   (self, self.default))
        else:
            val = self.from_config(cfp)
            if val is not None:
                _debug("Setting the default of %s from config: %s" %
                       (self, val))
                self.default = val

    def _get_default(self):
        """ Getter for the ``default`` property """
        return self._default

    def _set_default(self, value):
        """ Setter for the ``default`` property """
        self._default = value
        for action in self.actions.values():
            action.default = value

    #: The current default value of this option
    default = property(_get_default, _set_default)

    def _get_dest(self):
        """ Getter for the ``dest`` property """
        return self._dest

    def _set_dest(self, value):
        """ Setter for the ``dest`` property """
        self._dest = value
        for action in self.actions.values():
            action.dest = value

    def early_parsing_hook(self, early_opts):  # pylint: disable=C0111
        """Hook called at the end of early option parsing.

        This can be used to save option values for macro fixup.
        """
        pass

    #: The namespace destination of this option (see `dest
    #: <http://docs.python.org/dev/library/argparse.html#dest>`_)
    dest = property(_get_dest, _set_dest)

    def add_to_parser(self, parser):
        """ Add this option to the given parser.

        :param parser: The parser to add the option to.
        :type parser: Bcfg2.Options.Parser
        :returns: argparse.Action
        """
        self.parsers.append(parser)
        if self.args:
            # cli option
            _debug("Adding %s to %s as a CLI option" % (self, parser))
            action = parser.add_argument(*self.args, **self._kwargs)
            if not self._dest:
                self._dest = action.dest
            if self._default:
                action.default = self._default
            self.actions[parser] = action
        else:
            # else, config file-only option
            _debug("Adding %s to %s as a config file-only option" %
                   (self, parser))


class RepositoryMacroOption(Option):
    """Option that does translation of ``<repository>`` macros.

    Macro translation is done on the fly instead of just fixing up all
    values at the end of parsing because macro expansion needs to be
    done before path canonicalization for
    :class:`Bcfg2.Options.Options.PathOption`.
    """
    repository = None

    def __init__(self, *args, **kwargs):
        self._original_type = kwargs.pop('type', lambda x: x)
        kwargs['type'] = self._type
        kwargs.setdefault('metavar', '<path>')
        Option.__init__(self, *args, **kwargs)

    def early_parsing_hook(self, early_opts):
        if hasattr(early_opts, "repository"):
            if self.__class__.repository is None:
                _debug("Setting repository to %s for %s" %
                       (early_opts.repository, self.__class__.__name__))
                self.__class__.repository = early_opts.repository
            else:
                _debug("Repository is already set for %s" % self.__class__)

    def _get_default(self):
        """ Getter for the ``default`` property """
        if not hasattr(self._default, "replace"):
            return self._default
        else:
            return self._type(self._default)

    default = property(_get_default, Option._set_default)

    def transform_value(self, value):
        """transform the value after macro expansion.

         this can be overridden to further transform the value set by
        the user *after* macros are expanded, but before the user's
        ``type`` function is applied. principally exists for
        PathOption to canonicalize the path.
        """
        return value

    def _type(self, value):
        """Type function that fixes up <repository> macros."""
        if self.__class__.repository is None:
            return value
        else:
            return self._original_type(self.transform_value(
                value.replace("<repository>", self.__class__.repository)))


class PathOption(RepositoryMacroOption):
    """Shortcut for options that expect a path argument.

    Uses :meth:`Bcfg2.Options.Types.path` to transform the argument
    into a canonical path. The type of a path option can also be
    overridden to return a file-like object. For example:

    .. code-block:: python

        options = [
            Bcfg2.Options.PathOption(
                "--input", type=argparse.FileType('r'),
                help="The input file")]

    PathOptions also do translation of ``<repository>`` macros.
    """
    def transform_value(self, value):
        return Types.path(value)


class _BooleanOptionAction(argparse.Action):
    """BooleanOptionAction sets a boolean value.

    - if None is passed, store the default
    - if the option_string is not None, then the option was passed on the
      command line, thus store the opposite of the default (this is the
      argparse store_true and store_false behavior)
    - if a boolean value is passed, use that

    Makes a copy of the initial default, because otherwise the default
    can be changed by config file settings or environment
    variables. For instance, if a boolean option that defaults to True
    was set to False in the config file, specifying the option on the
    CLI would then set it back to True.

    Defined here instead of :mod:`Bcfg2.Options.Actions` because otherwise
    there is a circular import Options -> Actions -> Parser -> Options.
    """

    def __init__(self, *args, **kwargs):
        argparse.Action.__init__(self, *args, **kwargs)
        self.original = self.default

    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            setattr(namespace, self.dest, self.default)
        elif option_string is not None:
            setattr(namespace, self.dest, not self.original)
        else:
            setattr(namespace, self.dest, bool(values))


class BooleanOption(Option):
    """ Shortcut for boolean options.  The default is False, but this
    can easily be overridden:

    .. code-block:: python

        options = [
            Bcfg2.Options.PathOption(
                "--dwim", default=True, help="Do What I Mean")]
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('action', _BooleanOptionAction)
        kwargs.setdefault('nargs', 0)
        kwargs.setdefault('default', False)
        Option.__init__(self, *args, **kwargs)

    def get_environ_value(self, value):
        if value.lower() in ["false", "no", "off", "0"]:
            return False
        elif value.lower() in ["true", "yes", "on", "1"]:
            return True
        else:
            raise ValueError("Invalid boolean value %s" % value)

    def get_config_value(self, cfp):
        """fetch a value from the config file.

        This is passed the config parser. Its result is passed to the
        type function for this option. It can be overridden to, e.g.,
        handle boolean options.
        """
        return cfp.getboolean(*self.cf)


class PositionalArgument(Option):
    """ Shortcut for positional arguments. """
    def __init__(self, *args, **kwargs):
        if 'metavar' not in kwargs:
            kwargs['metavar'] = '<%s>' % args[0]
        Option.__init__(self, *args, **kwargs)
