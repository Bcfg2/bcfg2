"""test subcommand option parsing."""

import argparse
import sys

from Bcfg2.Compat import StringIO
from Bcfg2.Options import Option, get_parser, new_parser, Subcommand, \
    Subparser, CommandRegistry
import Bcfg2.Options.Subcommands

from testsuite.Testsrc.Testlib.TestOptions import make_config, OptionTestCase


class MockSubcommand(Subcommand):
    """fake subcommand that just records the options it was called with."""
    run_options = None

    def run(self, setup):
        self.__class__.run_options = setup


class One(MockSubcommand):
    """fake subcommand for testing."""
    options = [Option("--test-one")]


class Two(MockSubcommand):
    """fake subcommand for testing."""
    options = [Option("--test-two")]


def local_subclass(cls):
    """get a subclass of ``cls`` that adds no functionality.

    This can be used to subclass the various test classes above so
    that their options don't get modified by option parsing.
    """
    return type("Local%s" % cls.__name__, (cls,), {})


class TestSubcommands(OptionTestCase):
    """tests for subcommands and subparsers."""

    def setUp(self):
        self.registry = CommandRegistry()

        self.one = local_subclass(One)
        self.two = local_subclass(Two)

        self.registry.register_command(self.one)
        self.registry.register_command(self.two)

        self.result = argparse.Namespace()
        Bcfg2.Options.Subcommands.master_setup = self.result

        new_parser()
        self.parser = get_parser(namespace=self.result,
                                 components=[self])
        self.parser.add_options(self.registry.subcommand_options)

    def test_register_commands(self):
        """register subcommands."""
        registry = CommandRegistry()
        registry.register_commands(globals().values(),
                                   parent=MockSubcommand)
        self.assertItemsEqual(registry.commands.keys(),
                              ["one", "two", "help"])
        self.assertIsInstance(registry.commands['one'], One)
        self.assertIsInstance(registry.commands['two'], Two)

    @make_config()
    def test_get_subcommand(self, config_file):
        """parse simple subcommands."""
        self.parser.parse(["-C", config_file, "localone"])
        self.assertEqual(self.result.subcommand, "localone")

    def test_subcommand_usage(self):
        """sane usage message from subcommands."""
        self.assertEqual(
            One().usage(),
            "one [--test-one TEST_ONE] - fake subcommand for testing.")

        # subclasses do not inherit the docstring from the parent, so
        # this tests a command subclass without a docstring, even
        # though that should never happen due to the pylint tests.
        self.assertEqual(self.one().usage().strip(),
                         "localone [--test-one TEST_ONE]")

    @make_config()
    def test_help(self, config_file):
        """sane help message from subcommand registry."""
        self.parser.parse(["-C", config_file, "help"])
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        self.assertIn(self.registry.runcommand(), [0, None])
        help_message = sys.stdout.getvalue().splitlines()
        sys.stdout = old_stdout

        # the help message will look like:
        #
        # localhelp [<command>]
        # localone [--test-one TEST_ONE]
        # localtwo [--test-two TEST_TWO]
        commands = []
        command_help = {
            "help": self.registry.help.usage(),
            "localone": self.one().usage(),
            "localtwo": self.two().usage()}
        for line in help_message:
            command = line.split()[0]
            commands.append(command)
            if command not in command_help:
                self.fail("Got help for unknown command %s: %s" %
                          (command, line))
            self.assertEqual(line, command_help[command])
        self.assertItemsEqual(commands, command_help.keys())

    @make_config()
    def test_subcommand_help(self, config_file):
        """get help message on a single command."""
        self.parser.parse(["-C", config_file, "help", "localone"])
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        self.assertIn(self.registry.runcommand(), [0, None])
        help_message = sys.stdout.getvalue().splitlines()
        sys.stdout = old_stdout

        self.assertEqual(help_message[0].strip(),
                         "usage: %s" % self.one().usage().strip())

    @make_config()
    def test_nonexistent_subcommand_help(self, config_file):
        """get help message on a nonexistent command."""
        self.parser.parse(["-C", config_file, "help", "blargle"])
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        self.assertNotEqual(self.registry.runcommand(), 0)
        help_message = sys.stdout.getvalue().splitlines()
        sys.stdout = old_stdout

        self.assertIn("No such command", help_message[0])
