"""test component loading."""

import argparse
import os

from Bcfg2.Options import Option, BooleanOption, PathOption, ComponentAction, \
    get_parser, new_parser, Types, ConfigFileAction, Common

from testsuite.Testsrc.Testlib.TestOptions import make_config, One, Two, \
    OptionTestCase


# create a bunch of fake components for testing component loading options

class ChildOne(object):
    """fake component for testing component loading."""
    options = [Option("--child-one")]


class ChildTwo(object):
    """fake component for testing component loading."""
    options = [Option("--child-two")]


class ChildComponentAction(ComponentAction):
    """child component loader action."""
    islist = False
    mapping = {"one": ChildOne,
               "two": ChildTwo}


class ComponentOne(object):
    """fake component for testing component loading."""
    options = [BooleanOption("--one")]


class ComponentTwo(object):
    """fake component for testing component loading."""
    options = [Option("--child", default="one", action=ChildComponentAction)]


class ComponentThree(object):
    """fake component for testing component loading."""
    options = [BooleanOption("--three")]


class ConfigFileComponent(object):
    """fake component for testing component loading."""
    options = [Option("--config2", action=ConfigFileAction),
               Option(cf=("config", "test"), dest="config2_test",
                      default="bar")]


class PathComponent(object):
    """fake component for testing <repository> macros in child components."""
    options = [PathOption(cf=("test", "test_path")),
               PathOption(cf=("test", "test_path_default"),
                          default="<repository>/test/default")]


class ParentComponentAction(ComponentAction):
    """parent component loader action."""
    mapping = {"one": ComponentOne,
               "two": ComponentTwo,
               "three": ComponentThree,
               "config": ConfigFileComponent,
               "path": PathComponent}


class TestComponentOptions(OptionTestCase):
    """test cases for component loading."""

    def setUp(self):
        OptionTestCase.setUp(self)
        self.options = [
            Option("--parent", type=Types.comma_list,
                   default=["one", "two"], action=ParentComponentAction)]

        self.result = argparse.Namespace()
        new_parser()
        self.parser = get_parser(components=[self], namespace=self.result,
                                 description="component testing parser")

    @make_config()
    def test_loading_components(self, config_file):
        """load a single component during option parsing."""
        self.parser.parse(["-C", config_file, "--parent", "one"])
        self.assertEqual(self.result.parent, [ComponentOne])

    @make_config()
    def test_component_option(self, config_file):
        """use options from a component loaded during option parsing."""
        self.parser.parse(["--one", "-C", config_file, "--parent", "one"])
        self.assertEqual(self.result.parent, [ComponentOne])
        self.assertTrue(self.result.one)

    @make_config()
    def test_multi_component_load(self, config_file):
        """load multiple components during option parsing."""
        self.parser.parse(["-C", config_file, "--parent", "one,three"])
        self.assertEqual(self.result.parent, [ComponentOne, ComponentThree])

    @make_config()
    def test_multi_component_options(self, config_file):
        """use options from multiple components during option parsing."""
        self.parser.parse(["-C", config_file, "--three",
                           "--parent", "one,three", "--one"])
        self.assertEqual(self.result.parent, [ComponentOne, ComponentThree])
        self.assertTrue(self.result.one)
        self.assertTrue(self.result.three)

    @make_config()
    def test_component_default_not_loaded(self, config_file):
        """options from default but unused components not available."""
        self.assertRaises(
            SystemExit,
            self.parser.parse,
            ["-C", config_file, "--child", "one", "--parent", "one"])

    @make_config()
    def test_tiered_components(self, config_file):
        """load child component."""
        self.parser.parse(["-C", config_file, "--parent", "two",
                           "--child", "one"])
        self.assertEqual(self.result.parent, [ComponentTwo])
        self.assertEqual(self.result.child, ChildOne)

    @make_config()
    def test_options_tiered_components(self, config_file):
        """use options from child component."""
        self.parser.parse(["--child-one", "foo", "-C", config_file, "--parent",
                           "two", "--child", "one"])
        self.assertEqual(self.result.parent, [ComponentTwo])
        self.assertEqual(self.result.child, ChildOne)
        self.assertEqual(self.result.child_one, "foo")

    @make_config()
    def test_bogus_component(self, config_file):
        """error out with bad component name."""
        self.assertRaises(SystemExit,
                          self.parser.parse,
                          ["-C", config_file, "--parent", "blargle"])

    @make_config()
    @make_config({"config": {"test": "foo"}})
    def test_config_component(self, config1, config2):
        """load component with alternative config file."""
        self.parser.parse(["-C", config1, "--config2", config2,
                           "--parent", "config"])
        self.assertEqual(self.result.config2, config2)
        self.assertEqual(self.result.config2_test, "foo")

    @make_config()
    def test_config_component_no_file(self, config_file):
        """load component with missing alternative config file."""
        self.parser.parse(["-C", config_file, "--parent", "config"])
        self.assertEqual(self.result.config2, None)

    @make_config({"test": {"test_path": "<repository>/test"}})
    def test_macros_in_component_options(self, config_file):
        """fix up <repository> macros in component options."""
        self.parser.add_options([Common.repository])
        self.parser.parse(["-C", config_file, "-Q", "/foo/bar",
                           "--parent", "path"])
        self.assertEqual(self.result.test_path, "/foo/bar/test")
        self.assertEqual(self.result.test_path_default,
                         "/foo/bar/test/default")


class ImportComponentAction(ComponentAction):
    """action that imports real classes for testing."""
    islist = False
    bases = ["testsuite.Testsrc.Testlib.TestOptions"]


class ImportModuleAction(ImportComponentAction):
    """action that only imports modules for testing."""
    module = True


class TestImportComponentOptions(OptionTestCase):
    """test cases for component loading."""

    def setUp(self):
        self.options = [Option("--cls", cf=("config", "cls"),
                               action=ImportComponentAction),
                        Option("--module", action=ImportModuleAction)]

        self.result = argparse.Namespace()
        new_parser()
        self.parser = get_parser(components=[self], namespace=self.result)

    @make_config()
    def test_import_component(self, config_file):
        """load class components by importing."""
        self.parser.parse(["-C", config_file, "--cls", "One"])
        self.assertEqual(self.result.cls, One.One)

    @make_config()
    def test_import_module(self, config_file):
        """load module components by importing."""
        self.parser.parse(["-C", config_file, "--module", "One"])
        self.assertEqual(self.result.module, One)

    @make_config()
    def test_import_full_path(self, config_file):
        """load components by importing the full path."""
        self.parser.parse(["-C", config_file, "--cls", "os.path"])
        self.assertEqual(self.result.cls, os.path)

    @make_config()
    def test_import_bogus_class(self, config_file):
        """fail to load class component that cannot be imported."""
        self.assertRaises(SystemExit,
                          self.parser.parse,
                          ["-C", config_file, "--cls", "Three"])

    @make_config()
    def test_import_bogus_module(self, config_file):
        """fail to load module component that cannot be imported."""
        self.assertRaises(SystemExit,
                          self.parser.parse,
                          ["-C", config_file, "--module", "Three"])

    @make_config()
    def test_import_bogus_path(self, config_file):
        """fail to load component that cannot be imported by full path."""
        self.assertRaises(SystemExit,
                          self.parser.parse,
                          ["-C", config_file, "--cls", "Bcfg2.No.Such.Thing"])

    @make_config({"config": {"test": "foo", "cls": "Two"}})
    def test_default_from_config_for_component_options(self, config_file):
        """use default value from config file for options added by dynamic loaded component."""
        self.parser.parse(["-C", config_file])
        self.assertEqual(self.result.cls, Two.Two)
        self.assertEqual(self.result.test, "foo")
