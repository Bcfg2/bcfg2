"""test reading multiple config files."""

import argparse

from Bcfg2.Options import Option, BooleanOption, Parser, OptionGroup, \
    ExclusiveOptionGroup, WildcardSectionGroup, new_parser, get_parser

from testsuite.common import Bcfg2TestCase
from testsuite.Testsrc.Testlib.TestOptions import make_config, OptionTestCase


class TestOptionGroups(Bcfg2TestCase):
    def setUp(self):
        self.options = None

    def _test_options(self, options):
        """test helper."""
        result = argparse.Namespace()
        parser = Parser(components=[self], namespace=result)
        parser.parse(options)
        return result

    def test_option_group(self):
        """basic option group functionality."""
        self.options = [OptionGroup(BooleanOption("--foo"),
                                    BooleanOption("--bar"),
                                    BooleanOption("--baz"),
                                    title="group")]
        result = self._test_options(["--foo", "--bar"])
        self.assertTrue(result.foo)
        self.assertTrue(result.bar)
        self.assertFalse(result.baz)

    def test_exclusive_option_group(self):
        """parse options from exclusive option group."""
        self.options = [
            ExclusiveOptionGroup(BooleanOption("--foo"),
                                 BooleanOption("--bar"),
                                 BooleanOption("--baz"))]
        result = self._test_options(["--foo"])
        self.assertTrue(result.foo)
        self.assertFalse(result.bar)
        self.assertFalse(result.baz)

        self.assertRaises(SystemExit,
                          self._test_options, ["--foo", "--bar"])

    def test_required_exclusive_option_group(self):
        """parse options from required exclusive option group."""
        self.options = [
            ExclusiveOptionGroup(BooleanOption("--foo"),
                                 BooleanOption("--bar"),
                                 BooleanOption("--baz"),
                                 required=True)]
        result = self._test_options(["--foo"])
        self.assertTrue(result.foo)
        self.assertFalse(result.bar)
        self.assertFalse(result.baz)

        self.assertRaises(SystemExit, self._test_options, [])

    def test_option_group(self):
        """nest option groups."""
        self.options = [
            OptionGroup(
                BooleanOption("--foo"),
                BooleanOption("--bar"),
                OptionGroup(
                    BooleanOption("--baz"),
                    BooleanOption("--quux"),
                    ExclusiveOptionGroup(
                        BooleanOption("--test1"),
                        BooleanOption("--test2")),
                    title="inner"),
                title="outer")]
        result = self._test_options(["--foo", "--baz", "--test1"])
        self.assertTrue(result.foo)
        self.assertFalse(result.bar)
        self.assertTrue(result.baz)
        self.assertFalse(result.quux)
        self.assertTrue(result.test1)
        self.assertFalse(result.test2)

        self.assertRaises(SystemExit,
                          self._test_options, ["--test1", "--test2"])


class TestWildcardSectionGroups(OptionTestCase):
    config = {
        "four:one": {
            "foo": "foo one",
            "bar": "bar one",
            "baz": "baz one"
        },
        "four:two": {
            "foo": "foo two",
            "bar": "bar two"
        },
        "five:one": {
            "foo": "foo one",
            "bar": "bar one"
        },
        "five:two": {
            "foo": "foo two",
            "bar": "bar two"
        },
        "five:three": {
            "foo": "foo three",
            "bar": "bar three"
        }
    }

    def setUp(self):
        self.options = [
            WildcardSectionGroup(
                Option(cf=("four:*", "foo")),
                Option(cf=("four:*", "bar"))),
            WildcardSectionGroup(
                Option(cf=("five:*", "foo")),
                Option(cf=("five:*", "bar")),
                prefix="",
                dest="sections")]
        self.results = argparse.Namespace()
        new_parser()
        self.parser = get_parser(components=[self], namespace=self.results)

    @make_config(config)
    def test_wildcard_section_groups(self, config_file):
        """parse options from wildcard section groups."""
        self.parser.parse(["-C", config_file])
        self.assertEqual(self.results.four_four_one_foo, "foo one")
        self.assertEqual(self.results.four_four_one_bar, "bar one")
        self.assertEqual(self.results.four_four_two_foo, "foo two")
        self.assertEqual(self.results.four_four_two_bar, "bar two")
        self.assertItemsEqual(self.results.four_sections,
                              ["four:one", "four:two"])

        self.assertEqual(self.results.five_one_foo, "foo one")
        self.assertEqual(self.results.five_one_bar, "bar one")
        self.assertEqual(self.results.five_two_foo, "foo two")
        self.assertEqual(self.results.five_two_bar, "bar two")
        self.assertEqual(self.results.five_three_foo, "foo three")
        self.assertEqual(self.results.five_three_bar, "bar three")
        self.assertItemsEqual(self.results.sections,
                              ["five:one", "five:two", "five:three"])
