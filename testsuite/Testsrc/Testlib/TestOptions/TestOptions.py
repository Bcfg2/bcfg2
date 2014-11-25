"""basic option parsing tests."""

import argparse
import os
import tempfile

import mock

from Bcfg2.Compat import ConfigParser
from Bcfg2.Options import Option, PathOption, RepositoryMacroOption, \
    BooleanOption, Parser, PositionalArgument, OptionParserException, \
    Common, new_parser, get_parser
from testsuite.Testsrc.Testlib.TestOptions import OptionTestCase, \
    make_config, clean_environment


class TestBasicOptions(OptionTestCase):
    """test basic option parsing."""
    def setUp(self):
        # parsing options can modify the Option objects themselves.
        # that's probably bad -- and it's definitely bad if we ever
        # want to do real on-the-fly config changes -- but it's easier
        # to leave it as is and set the options on each test.
        OptionTestCase.setUp(self)
        self.options = [
            BooleanOption("--test-true-boolean", env="TEST_TRUE_BOOLEAN",
                          cf=("test", "true_boolean"), default=True),
            BooleanOption("--test-false-boolean", env="TEST_FALSE_BOOLEAN",
                          cf=("test", "false_boolean"), default=False),
            BooleanOption(cf=("test", "true_config_boolean"),
                          default=True),
            BooleanOption(cf=("test", "false_config_boolean"),
                          default=False),
            Option("--test-option", env="TEST_OPTION", cf=("test", "option"),
                   default="foo"),
            PathOption("--test-path-option", env="TEST_PATH_OPTION",
                       cf=("test", "path"), default="/test")]

    @clean_environment
    def _test_options(self, options=None, env=None, config=None):
        """helper to test a set of options.

        returns the namespace from parsing the given CLI options with
        the given config and environment.
        """
        if config is not None:
            config = {"test": config}
        if options is None:
            options = []

        @make_config(config)
        def inner(config_file):
            """do the actual tests, since py2.4 lacks context managers."""
            result = argparse.Namespace()
            parser = Parser(components=[self], namespace=result)
            parser.parse(argv=["-C", config_file] + options)
            return result

        if env is not None:
            for name, value in env.items():
                os.environ[name] = value

        return inner()

    def test_expand_path(self):
        """expand ~ in path option."""
        options = self._test_options(options=["--test-path-option",
                                              "~/test"])
        self.assertEqual(options.test_path_option,
                         os.path.expanduser("~/test"))

    def test_canonicalize_path(self):
        """get absolute path from path option."""
        options = self._test_options(options=["--test-path-option",
                                              "./test"])
        self.assertEqual(options.test_path_option,
                         os.path.abspath("./test"))

    @make_config()
    def test_default_path_canonicalization(self, config_file):
        """canonicalize default PathOption values."""
        testdir = os.path.expanduser("~/test")
        result = argparse.Namespace()
        parser = Parser(namespace=result)
        parser.add_options([PathOption("--test1", default="~/test"),
                            PathOption(cf=("test", "test2"),
                                       default="~/test"),
                            Common.repository])
        parser.parse(["-C", config_file])
        self.assertEqual(result.test1, testdir)
        self.assertEqual(result.test2, testdir)

    def test_default_bool(self):
        """use the default value of boolean options."""
        options = self._test_options()
        self.assertTrue(options.test_true_boolean)
        self.assertFalse(options.test_false_boolean)
        self.assertTrue(options.true_config_boolean)
        self.assertFalse(options.false_config_boolean)

    def test_default(self):
        """use the default value of an option."""
        options = self._test_options()
        self.assertEqual(options.test_option, "foo")

    def test_default_path(self):
        """use the default value of a path option."""
        options = self._test_options()
        self.assertEqual(options.test_path_option, "/test")

    def test_invalid_boolean(self):
        """set boolean to invalid values."""
        self.assertRaises(ValueError,
                          self._test_options,
                          config={"true_boolean": "you betcha"})
        self.assertRaises(ValueError,
                          self._test_options,
                          env={"TEST_TRUE_BOOLEAN": "hell no"})

    def test_set_boolean_in_config(self):
        """set boolean options in config files."""
        set_to_defaults = {"true_boolean": "1",
                           "false_boolean": "0",
                           "true_config_boolean": "yes",
                           "false_config_boolean": "no"}
        options = self._test_options(config=set_to_defaults)
        self.assertTrue(options.test_true_boolean)
        self.assertFalse(options.test_false_boolean)
        self.assertTrue(options.true_config_boolean)
        self.assertFalse(options.false_config_boolean)

        set_to_other = {"true_boolean": "false",
                        "false_boolean": "true",
                        "true_config_boolean": "off",
                        "false_config_boolean": "on"}
        options = self._test_options(config=set_to_other)
        self.assertFalse(options.test_true_boolean)
        self.assertTrue(options.test_false_boolean)
        self.assertFalse(options.true_config_boolean)
        self.assertTrue(options.false_config_boolean)

    def test_set_in_config(self):
        """set options in config files."""
        options = self._test_options(config={"option": "foo"})
        self.assertEqual(options.test_option, "foo")

        options = self._test_options(config={"option": "bar"})
        self.assertEqual(options.test_option, "bar")

    def test_set_path_in_config(self):
        """set path options in config files."""
        options = self._test_options(config={"path": "/test"})
        self.assertEqual(options.test_path_option, "/test")

        options = self._test_options(config={"path": "/foo"})
        self.assertEqual(options.test_path_option, "/foo")

    def test_set_boolean_in_env(self):
        """set boolean options in environment."""
        set_to_defaults = {"TEST_TRUE_BOOLEAN": "1",
                           "TEST_FALSE_BOOLEAN": "0"}
        options = self._test_options(env=set_to_defaults)
        self.assertTrue(options.test_true_boolean)
        self.assertFalse(options.test_false_boolean)

        set_to_other = {"TEST_TRUE_BOOLEAN": "false",
                        "TEST_FALSE_BOOLEAN": "true"}
        options = self._test_options(env=set_to_other)
        self.assertFalse(options.test_true_boolean)
        self.assertTrue(options.test_false_boolean)

    def test_set_in_env(self):
        """set options in environment."""
        options = self._test_options(env={"TEST_OPTION": "foo"})
        self.assertEqual(options.test_option, "foo")

        options = self._test_options(env={"TEST_OPTION": "bar"})
        self.assertEqual(options.test_option, "bar")

    def test_set_path_in_env(self):
        """set path options in environment."""
        options = self._test_options(env={"TEST_PATH_OPTION": "/test"})
        self.assertEqual(options.test_path_option, "/test")

        options = self._test_options(env={"TEST_PATH_OPTION": "/foo"})
        self.assertEqual(options.test_path_option, "/foo")

    def test_version(self):
        """print version and exit on --version"""
        self.assertRaises(
            SystemExit,
            self._test_options,
            options=['--version'])

    def test_set_boolean_in_cli(self):
        """set boolean options in CLI options."""
        # passing the option yields the reverse of the default, no
        # matter the default
        options = self._test_options(options=["--test-true-boolean",
                                              "--test-false-boolean"])
        self.assertFalse(options.test_true_boolean)
        self.assertTrue(options.test_false_boolean)

    def test_set_in_cli(self):
        """set options in CLI options."""
        options = self._test_options(options=["--test-option", "foo"])
        self.assertEqual(options.test_option, "foo")

        options = self._test_options(options=["--test-option", "bar"])
        self.assertEqual(options.test_option, "bar")

    def test_set_path_in_cli(self):
        """set path options in CLI options."""
        options = self._test_options(options=["--test-path-option", "/test"])
        self.assertEqual(options.test_path_option, "/test")

        options = self._test_options(options=["--test-path-option", "/foo"])
        self.assertEqual(options.test_path_option, "/foo")

    def test_env_overrides_config_bool(self):
        """setting boolean option in the environment overrides config file."""
        config = {"true_boolean": "false",
                  "false_boolean": "true"}
        env = {"TEST_TRUE_BOOLEAN": "yes",
               "TEST_FALSE_BOOLEAN": "no"}
        options = self._test_options(config=config, env=env)
        self.assertTrue(options.test_true_boolean)
        self.assertFalse(options.test_false_boolean)

    def test_env_overrides_config(self):
        """setting option in the environment overrides config file."""
        options = self._test_options(config={"option": "bar"},
                                     env={"TEST_OPTION": "baz"})
        self.assertEqual(options.test_option, "baz")

    def test_env_overrides_config_path(self):
        """setting path option in the environment overrides config file."""
        options = self._test_options(config={"path": "/foo"},
                                     env={"TEST_PATH_OPTION": "/bar"})
        self.assertEqual(options.test_path_option, "/bar")

    def test_cli_overrides_config_bool(self):
        """setting boolean option in the CLI overrides config file."""
        config = {"true_boolean": "on",
                  "false_boolean": "off"}
        options = ["--test-true-boolean", "--test-false-boolean"]
        options = self._test_options(options=options, config=config)
        self.assertFalse(options.test_true_boolean)
        self.assertTrue(options.test_false_boolean)

    def test_cli_overrides_config(self):
        """setting option in the CLI overrides config file."""
        options = self._test_options(options=["--test-option", "baz"],
                                     config={"option": "bar"})
        self.assertEqual(options.test_option, "baz")

    def test_cli_overrides_config_path(self):
        """setting path option in the CLI overrides config file."""
        options = self._test_options(options=["--test-path-option", "/bar"],
                                     config={"path": "/foo"})
        self.assertEqual(options.test_path_option, "/bar")

    def test_cli_overrides_env_bool(self):
        """setting boolean option in the CLI overrides environment."""
        env = {"TEST_TRUE_BOOLEAN": "0",
               "TEST_FALSE_BOOLEAN": "1"}
        options = ["--test-true-boolean", "--test-false-boolean"]
        options = self._test_options(options=options, env=env)
        self.assertFalse(options.test_true_boolean)
        self.assertTrue(options.test_false_boolean)

    def test_cli_overrides_env(self):
        """setting option in the CLI overrides environment."""
        options = self._test_options(options=["--test-option", "baz"],
                                     env={"TEST_OPTION": "bar"})
        self.assertEqual(options.test_option, "baz")

    def test_cli_overrides_env_path(self):
        """setting path option in the CLI overrides environment."""
        options = self._test_options(options=["--test-path-option", "/bar"],
                                     env={"TEST_PATH_OPTION": "/foo"})
        self.assertEqual(options.test_path_option, "/bar")

    def test_cli_overrides_all_bool(self):
        """setting boolean option in the CLI overrides everything else."""
        config = {"true_boolean": "no",
                  "false_boolean": "yes"}
        env = {"TEST_TRUE_BOOLEAN": "0",
               "TEST_FALSE_BOOLEAN": "1"}
        options = ["--test-true-boolean", "--test-false-boolean"]
        options = self._test_options(options=options, env=env)
        self.assertFalse(options.test_true_boolean)
        self.assertTrue(options.test_false_boolean)

    def test_cli_overrides_all(self):
        """setting option in the CLI overrides everything else."""
        options = self._test_options(options=["--test-option", "baz"],
                                     env={"TEST_OPTION": "bar"},
                                     config={"test": "quux"})
        self.assertEqual(options.test_option, "baz")

    def test_cli_overrides_all_path(self):
        """setting path option in the CLI overrides everything else."""
        options = self._test_options(options=["--test-path-option", "/bar"],
                                     env={"TEST_PATH_OPTION": "/foo"},
                                     config={"path": "/baz"})
        self.assertEqual(options.test_path_option, "/bar")

    @make_config()
    def _test_dest(self, *args, **kwargs):
        """helper to test that ``dest`` is set properly."""
        args = list(args)
        expected = args.pop(0)
        config_file = args.pop()

        sentinel = object()
        kwargs["default"] = sentinel

        result = argparse.Namespace()
        parser = Parser(namespace=result)
        parser.add_options([Option(*args, **kwargs)])
        parser.parse(["-C", config_file])

        self.assertTrue(hasattr(result, expected))
        self.assertEqual(getattr(result, expected), sentinel)

    def test_explicit_dest(self):
        """set the ``dest`` of an option explicitly."""
        self._test_dest("bar", dest="bar")

    def test_dest_from_env_var(self):
        """set the ``dest`` of an option from the env var name."""
        self._test_dest("foo", env="FOO")

    def test_dest_from_cf(self):
        """set the ``dest`` of an option from the config option."""
        self._test_dest("foo_bar", cf=("test", "foo-bar"))

    def test_dest_from_cli(self):
        """set the ``dest`` of an option from the CLI option."""
        self._test_dest("test_foo", "--test-foo")

    def test_dest_from_all(self):
        """set the ``dest`` of an option from the best of multiple sources."""
        self._test_dest("foo_baz", cf=("test", "foo-bar"), env="FOO_BAZ")
        self._test_dest("xyzzy",
                        "--xyzzy", cf=("test", "foo-bar"), env="FOO_BAZ")
        self._test_dest("quux",
                        "--xyzzy", cf=("test", "foo-bar"), env="FOO_BAZ",
                        dest="quux")

    @make_config()
    def test_positional_args(self, config_file):
        """get values from positional arguments."""
        result = argparse.Namespace()
        parser = Parser(namespace=result)
        parser.add_options([PositionalArgument("single")])
        parser.parse(["-C", config_file, "single"])
        self.assertEqual(result.single, "single")

        result = argparse.Namespace()
        parser = Parser(namespace=result)
        parser.add_options([PositionalArgument("one"),
                            PositionalArgument("two")])
        parser.parse(["-C", config_file, "one", "two"])
        self.assertEqual(result.one, "one")
        self.assertEqual(result.two, "two")

    def test_duplicate_cli_option(self):
        """add duplicate CLI option."""
        parser = Parser(components=[self])
        self.assertRaises(
            argparse.ArgumentError,
            parser.add_options,
            [Option("--test-option")])

    def test_duplicate_env_option(self):
        """add duplicate environment option."""
        parser = Parser(components=[self])
        self.assertRaises(
            OptionParserException,
            parser.add_options,
            [Option(env="TEST_OPTION")])

    def test_duplicate_cf_option(self):
        """add duplicate config file option."""
        parser = Parser(components=[self])
        self.assertRaises(
            OptionParserException,
            parser.add_options,
            [Option(cf=("test", "option"))])

    @make_config({"test": {"test_path": "<repository>/test",
                           "test_macro": "<repository>"}})
    def test_repository_macro(self, config_file):
        """fix up <repository> macros."""
        result = argparse.Namespace()
        parser = Parser(namespace=result)
        parser.add_options([PathOption("--test1"),
                            RepositoryMacroOption("--test2"),
                            PathOption(cf=("test", "test_path")),
                            PathOption(cf=("test", "test_path_default"),
                                       default="<repository>/test/default"),
                            RepositoryMacroOption(cf=("test", "test_macro")),
                            RepositoryMacroOption(
                                cf=("test", "test_macro_default"),
                                default="<repository>"),
                            Common.repository])
        parser.parse(["-C", config_file, "-Q", "/foo/bar",
                      "--test1", "<repository>/test1",
                      "--test2", "<repository><repository>"])
        self.assertEqual(result.repository, "/foo/bar")
        self.assertEqual(result.test1, "/foo/bar/test1")
        self.assertEqual(result.test2, "/foo/bar/foo/bar")
        self.assertEqual(result.test_macro, "/foo/bar")
        self.assertEqual(result.test_macro_default, "/foo/bar")
        self.assertEqual(result.test_path, "/foo/bar/test")
        self.assertEqual(result.test_path_default, "/foo/bar/test/default")

    @make_config()
    def test_file_like_path_option(self, config_file):
        """get file-like object from PathOption."""
        result = argparse.Namespace()
        parser = Parser(namespace=result)
        parser.add_options([PathOption("--test", type=argparse.FileType('r'))])

        fd, name = tempfile.mkstemp()
        fh = os.fdopen(fd, "w")
        fh.write("test")
        fh.close()

        try:
            parser.parse(["-C", config_file, "--test", name])
            self.assertEqual(result.test.name, name)
            self.assertEqual(result.test.read(), "test")
        finally:
            os.unlink(name)

    @clean_environment
    @make_config()
    def test_unknown_options(self, config_file):
        """error on unknown options."""
        parser = Parser(components=[self])
        self.assertRaises(SystemExit,
                          parser.parse,
                          ["-C", config_file, "--not-a-real-option"])

    @clean_environment
    @make_config()
    def test_reparse(self, config_file):
        """reparse options."""
        result = argparse.Namespace()
        parser = Parser(components=[self], namespace=result)
        parser.parse(["-C", config_file])
        self.assertFalse(result.test_false_boolean)

        parser.parse(["-C", config_file])
        self.assertFalse(result.test_false_boolean)

        parser.reparse()
        self.assertFalse(result.test_false_boolean)

        parser.reparse(["-C", config_file, "--test-false-boolean"])
        self.assertTrue(result.test_false_boolean)

        cfp = ConfigParser.ConfigParser()
        cfp.add_section("test")
        cfp.set("test", "false_boolean", "on")
        parser.parse(["-C", config_file])
        cfp.write(open(config_file, "w"))
        self.assertTrue(result.test_false_boolean)


class TestParsingHooks(OptionTestCase):
    """test option parsing hooks."""
    def setUp(self):
        self.options_parsed_hook = mock.Mock()
        self.options = [BooleanOption("--test", default=False)]
        self.results = argparse.Namespace()
        new_parser()
        self.parser = get_parser(components=[self], namespace=self.results)

    @make_config()
    def test_parsing_hooks(self, config_file):
        """option parsing hooks are called."""
        self.parser.parse(["-C", config_file])
        self.options_parsed_hook.assert_called_with()


class TestEarlyParsingHooks(OptionTestCase):
    """test early option parsing hooks."""
    parse_first = True

    def setUp(self):
        self.component_parsed_hook = mock.Mock()
        self.options = [BooleanOption("--early-test", default=False)]
        self.results = argparse.Namespace()
        new_parser()
        self.parser = get_parser(components=[self], namespace=self.results)

    @make_config()
    def test_parsing_hooks(self, config_file):
        """early option parsing hooks are called."""
        self.parser.parse(["-C", config_file, "--early-test"])
        self.assertEqual(self.component_parsed_hook.call_count, 1)
        early_opts = self.component_parsed_hook.call_args[0][0]
        self.assertTrue(early_opts.early_test)
