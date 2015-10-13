""" Classes to make it easier to create commands with large numbers of
subcommands (e.g., bcfg2-admin, bcfg2-info). """

import re
import cmd
import sys
import copy
import shlex
import logging

from Bcfg2.Compat import StringIO
from Bcfg2.Options import PositionalArgument, _debug
from Bcfg2.Options.OptionGroups import Subparser
from Bcfg2.Options.Parser import Parser, setup as master_setup

__all__ = ["Subcommand", "CommandRegistry"]


class Subcommand(object):
    """ Base class for subcommands.  This must be subclassed to create
    commands.

    Specifically, you must override
    :func:`Bcfg2.Options.Subcommand.run`.  You may want to override:

    * The docstring, which will be used as the short help.
    * :attr:`Bcfg2.Options.Subcommand.options`
    * :attr:`Bcfg2.Options.Subcommand.help`
    * :attr:`Bcfg2.Options.Subcommand.interactive`
    *
    * :func:`Bcfg2.Options.Subcommand.shutdown`

    You should not need to override
    :func:`Bcfg2.Options.Subcommand.__call__` or
    :func:`Bcfg2.Options.Subcommand.usage`.

    A ``Subcommand`` subclass constructor must not take any arguments.
    """

    #: Options this command takes
    options = []

    #: Longer help message
    help = None

    #: Whether or not to expose this command in an interactive
    #: :class:`cmd.Cmd` shell, if one is used.  (``bcfg2-info`` uses
    #: one, ``bcfg2-admin`` does not.)
    interactive = True

    #: Whether or not to expose this command as command line parameter
    #: or only in an interactive :class:`cmd.Cmd` shell.
    only_interactive = False

    #: Additional aliases for the command. The contents of the list gets
    #: added to the default command name (the lowercased class name)
    aliases = []

    _ws_re = re.compile(r'\s+', flags=re.MULTILINE)

    def __init__(self):
        self.core = None
        description = "%s: %s" % (self.__class__.__name__.lower(),
                                  self.__class__.__doc__)

        #: The :class:`Bcfg2.Options.Parser` that will be used to
        #: parse options if this subcommand is called from an
        #: interactive :class:`cmd.Cmd` shell.
        self.parser = Parser(
            prog=self.__class__.__name__.lower(),
            description=description,
            components=[self],
            add_base_options=False,
            epilog=self.help)
        self._usage = None

        #: A :class:`logging.Logger` that can be used to produce
        #: logging output for this command.
        self.logger = logging.getLogger(self.__class__.__name__.lower())

    def __call__(self, args=None):
        """ Perform option parsing and other tasks necessary to
        support running ``Subcommand`` objects as part of a
        :class:`cmd.Cmd` shell.  You should not need to override
        ``__call__``.

        :param args: Arguments given in the interactive shell
        :type args: list of strings
        :returns: The return value of :func:`Bcfg2.Options.Subcommand.run`
        """
        if args is not None:
            self.parser.namespace = copy.copy(master_setup)
            self.parser.parsed = False
            alist = shlex.split(args)
            try:
                setup = self.parser.parse(alist)
            except SystemExit:
                return sys.exc_info()[1].code
            return self.run(setup)
        else:
            return self.run(master_setup)

    def usage(self):
        """ Get the short usage message. """
        if self._usage is None:
            sio = StringIO()
            self.parser.print_usage(file=sio)
            usage = self._ws_re.sub(' ', sio.getvalue()).strip()[7:]
            doc = self._ws_re.sub(' ', getattr(self, "__doc__") or "").strip()
            if not doc:
                self._usage = usage
            else:
                self._usage = "%s - %s" % (usage, doc)
        return self._usage

    def run(self, setup):
        """ Run the command.

        :param setup: A namespace giving the options for this command.
                      This must be used instead of
                      :attr:`Bcfg2.Options.setup` because this command
                      may have been called from an interactive
                      :class:`cmd.Cmd` shell, and thus has its own
                      option parser and its own (private) namespace.
                      ``setup`` is guaranteed to contain all of the
                      options in the global
                      :attr:`Bcfg2.Options.setup` namespace, in
                      addition to any local options given to this
                      command from the interactive shell.
        :type setup: argparse.Namespace
        """
        raise NotImplementedError  # pragma: nocover

    def shutdown(self):
        """ Perform any necessary shutdown tasks for this command This
        is called to when the program exits (*not* when this command
        is finished executing). """
        pass  # pragma: nocover


class Help(Subcommand):
    """List subcommands and usage, or get help on a specific subcommand."""
    options = [PositionalArgument("command", nargs='?')]

    # the interactive shell has its own help
    interactive = False

    def __init__(self, registry):
        Subcommand.__init__(self)
        self._registry = registry

    def run(self, setup):
        commands = dict((name, cmd)
                        for (name, cmd) in self._registry.commands.items()
                        if not cmd.only_interactive)
        if setup.command:
            try:
                commands[setup.command].parser.print_help()
                return 0
            except KeyError:
                print("No such command: %s" % setup.command)
                return 1
        for command in sorted(commands.keys()):
            print(commands[command].usage())


class CommandRegistry(object):
    """A ``CommandRegistry`` is used to register subcommands and provides
    a single interface to run them.  It's also used by
    :class:`Bcfg2.Options.Subcommands.Help` to produce help messages
    for all available commands.
    """

    def __init__(self):
        #: A dict of registered commands.  Keys are the class names,
        #: lowercased (i.e., the command names), and values are instances
        #: of the command objects.
        self.commands = dict()

        #: A list of options that should be added to the option parser
        #: in order to handle registered subcommands.
        self.subcommand_options = []

        #: the help command
        self.help = Help(self)
        self.register_command(self.help)

    def runcommand(self):
        """ Run the single command named in
        ``Bcfg2.Options.setup.subcommand``, which is where
        :class:`Bcfg2.Options.Subparser` groups store the
        subcommand. """
        _debug("Running subcommand %s" % master_setup.subcommand)
        try:
            return self.commands[master_setup.subcommand].run(master_setup)
        finally:
            self.shutdown()

    def shutdown(self):
        """Perform shutdown tasks.

        This calls the ``shutdown`` method of the subcommand that was
        run.
        """
        _debug("Shutting down subcommand %s" % master_setup.subcommand)
        self.commands[master_setup.subcommand].shutdown()

    def register_command(self, cls_or_obj):
        """ Register a single command.

        :param cls_or_obj: The command class or object to register
        :type cls_or_obj: type or Subcommand
        :returns: An instance of ``cmdcls``
        """
        if isinstance(cls_or_obj, type):
            cmdcls = cls_or_obj
            cmd_obj = cmdcls()
        else:
            cmd_obj = cls_or_obj
            cmdcls = cmd_obj.__class__
        names = [cmdcls.__name__.lower()]
        if cmdcls.aliases:
            names.extend(cmdcls.aliases)

        for name in names:
            self.commands[name] = cmd_obj

            if not cmdcls.only_interactive:
                # py2.5 can't mix *magic and non-magical keyword args, thus
                # the **dict(...)
                self.subcommand_options.append(
                    Subparser(*cmdcls.options, **dict(name=name,
                                                      help=cmdcls.__doc__)))
            if issubclass(self.__class__, cmd.Cmd) and cmdcls.interactive:
                setattr(self, "do_%s" % name, cmd_obj)
                setattr(self, "help_%s" % name, cmd_obj.parser.print_help)
        return cmd_obj

    def register_commands(self, candidates, parent=Subcommand):
        """ Register all subcommands in ``candidates`` against the
        :class:`Bcfg2.Options.CommandRegistry` subclass given in
        ``registry``.  A command is registered if and only if:

        * It is a subclass of the given ``parent`` (by default,
          :class:`Bcfg2.Options.Subcommand`);
        * It is not the parent class itself; and
        * Its name does not start with an underscore.

        :param registry: The :class:`Bcfg2.Options.CommandRegistry`
                         subclass against which commands will be
                         registered.
        :type registry: Bcfg2.Options.CommandRegistry
        :param candidates: A list of objects that will be considered for
                           registration.  Only objects that meet the
                           criteria listed above will be registered.
        :type candidates: list
        :param parent: Specify a parent class other than
                       :class:`Bcfg2.Options.Subcommand` that all
                       registered commands must subclass.
        :type parent: type
        """
        for attr in candidates:
            if (isinstance(attr, type) and
                    issubclass(attr, parent) and
                    attr != parent and
                    not attr.__name__.startswith("_")):
                self.register_command(attr)
