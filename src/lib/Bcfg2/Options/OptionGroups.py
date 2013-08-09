""" Option grouping classes """

import re
import copy
import fnmatch
from Options import Option
from itertools import chain

__all__ = ["OptionGroup", "ExclusiveOptionGroup", "Subparser",
           "WildcardSectionGroup"]

#: A dict that records a mapping of argparse action name (e.g.,
#: "store_true") to the argparse Action class for it.  See
#: :func:`_get_action_class`
_action_map = dict()


class OptionContainer(list):
    """ Parent class of all option groups """

    def list_options(self):
        """ Get a list of all options contained in this group,
        including options contained in option groups in this group,
        and so on. """
        return list(chain(*[o.list_options() for o in self]))

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, list.__repr__(self))

    def add_to_parser(self, parser):
        """ Add this option group to a :class:`Bcfg2.Options.Parser`
        object. """
        for opt in self:
            opt.add_to_parser(parser)


class OptionGroup(OptionContainer):
    """ Generic option group that is used only to organize options.
    This uses :meth:`argparse.ArgumentParser.add_argument_group`
    behind the scenes. """

    def __init__(self, *items, **kwargs):
        """
        :param \*args: Child options
        :type \*args: Bcfg2.Options.Option
        :param title: The title of the option group
        :type title: string
        :param description: A longer description of the option group
        :param description: string
        """
        OptionContainer.__init__(self, items)
        self.title = kwargs.pop('title')
        self.description = kwargs.pop('description', None)

    def add_to_parser(self, parser):
        group = parser.add_argument_group(self.title, self.description)
        OptionContainer.add_to_parser(self, group)


class ExclusiveOptionGroup(OptionContainer):
    """ Option group that ensures that only one argument in the group
    is present.  This uses
    :meth:`argparse.ArgumentParser.add_mutually_exclusive_group`
    behind the scenes."""

    def __init__(self, *items, **kwargs):
        """
        :param \*args: Child options
        :type \*args: Bcfg2.Options.Option
        :param required: Exactly one argument in the group *must* be
                         specified.
        :type required: boolean
        """
        OptionContainer.__init__(self, items)
        self.required = kwargs.pop('required', False)

    def add_to_parser(self, parser):
        group = parser.add_mutually_exclusive_group(required=self.required)
        OptionContainer.add_to_parser(self, group)


class Subparser(OptionContainer):
    """ Option group that adds options in it to a subparser.  This
    uses a lot of functionality tied to `argparse Sub-commands
    <http://docs.python.org/dev/library/argparse.html#sub-commands>`_.

    The subcommand string itself is stored in the
    :attr:`Bcfg2.Options.setup` namespace as ``subcommand``.

    This is commonly used with :class:`Bcfg2.Options.Subcommand`
    groups.
    """

    _subparsers = dict()

    def __init__(self, *items, **kwargs):
        """
        :param \*args: Child options
        :type \*args: Bcfg2.Options.Option
        :param name: The name of the subparser.  Required.
        :type name: string
        :param help: A help message for the subparser
        :param help: string
        """
        self.name = kwargs.pop('name')
        self.help = kwargs.pop('help', None)
        OptionContainer.__init__(self, items)

    def __repr__(self):
        return "%s %s(%s)" % (self.__class__.__name__,
                              self.name,
                              list.__repr__(self))

    def add_to_parser(self, parser):
        if parser not in self._subparsers:
            self._subparsers[parser] = parser.add_subparsers(dest='subcommand')
        subparser = self._subparsers[parser].add_parser(self.name,
                                                        help=self.help)
        OptionContainer.add_to_parser(self, subparser)


class WildcardSectionGroup(OptionContainer, Option):
    """ WildcardSectionGroups contain options that may exist in
    several different sections of the config that match a glob.  It
    works by creating options on the fly to match the sections
    described in the glob.  For example, consider:

    .. code-block:: python

        options = [
            Bcfg2.Options.WildcardSectionGroup(
                Bcfg2.Options.Option(cf=("myplugin:*", "number"), type=int),
                Bcfg2.Options.Option(cf=("myplugin:*", "description"))]

    If the config file contained ``[myplugin:foo]`` and
    ``[myplugin:bar]`` sections, then this would automagically create
    options for each of those.  The end result would be:

    .. code-block:: python

        >>> Bcfg2.Options.setup
        Namespace(myplugin_bar_description='Bar description', myplugin_bar_number=2, myplugin_foo_description='Foo description', myplugin_foo_number=1, myplugin_sections=['myplugin:foo', 'myplugin:bar'])

    All options must have the same section glob.

    The options are stored in an automatically-generated destination
    given by::

        <prefix><section>_<destination>

    ``<destination>`` is the original `dest
    <http://docs.python.org/dev/library/argparse.html#dest>`_ of the
    option. ``<section>`` is the section that it's found in.
    ``<prefix>`` is automatically generated from the section glob by
    replacing all consecutive characters disallowed in Python variable
    names into underscores.  (This can be overridden with the
    constructor.)

    This group stores an additional option, the sections themselves,
    in an option given by ``<prefix>sections``.
    """

    #: Regex to automatically get a destination for this option
    _dest_re = re.compile(r'(\A(_|[^A-Za-z])+)|((_|[^A-Za-z0-9])+)')

    def __init__(self, *items, **kwargs):
        """
        :param \*args: Child options
        :type \*args: Bcfg2.Options.Option
        :param prefix: The prefix to use for options generated by this
                       option group.  By default this is generated
                       automatically from the config glob; see above
                       for details.
        :type prefix: string
        :param dest: The destination for the list of known sections
                     that match the glob.
        :param dest: string
        """
        OptionContainer.__init__(self, [])
        self._section_glob = items[0].cf[0]
        # get a default destination
        self._prefix = kwargs.get("prefix",
                                  self._dest_re.sub('_', self._section_glob))
        Option.__init__(self, dest=kwargs.get('dest',
                                              self._prefix + "sections"))
        self._options = items

    def list_options(self):
        return [self] + OptionContainer.list_options(self)

    def from_config(self, cfp):
        sections = []
        for section in cfp.sections():
            if fnmatch.fnmatch(section, self._section_glob):
                sections.append(section)
                newopts = []
                for opt_tmpl in self._options:
                    option = copy.deepcopy(opt_tmpl)
                    option.cf = (section, option.cf[1])
                    option.dest = self._prefix + section + "_" + option.dest
                    newopts.append(option)
                self.extend(newopts)
                for parser in self.parsers:
                    parser.add_options(newopts)
        return sections

    def add_to_parser(self, parser):
        Option.add_to_parser(self, parser)
        OptionContainer.add_to_parser(self, parser)
