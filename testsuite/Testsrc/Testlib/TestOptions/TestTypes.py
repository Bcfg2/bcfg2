"""test builtin option types."""

import argparse

from mock import patch

from Bcfg2.Options import Option, Types, Parser
from testsuite.common import Bcfg2TestCase


class TestOptionTypes(Bcfg2TestCase):
    """test builtin option types."""
    def setUp(self):
        self.options = None

    def _test_options(self, options):
        """helper to test option types.

        this expects that self.options is set to a single option named
        test. The value of that option is returned.
        """
        result = argparse.Namespace()
        parser = Parser(components=[self], namespace=result)
        parser.parse(options)
        return result.test

    def test_comma_list(self):
        """parse comma-list values."""
        self.options = [Option("--test", type=Types.comma_list)]

        expected = ["one", "two", "three"]
        self.assertItemsEqual(self._test_options(["--test", "one,two,three"]),
                              expected)
        self.assertItemsEqual(self._test_options(["--test",
                                                  "one, two, three"]),
                              expected)
        self.assertItemsEqual(self._test_options(["--test",
                                                  "one   , two  ,three"]),
                              expected)
        self.assertItemsEqual(self._test_options(["--test", "one two, three"]),
                              ["one two", "three"])

    def test_colon_list(self):
        """parse colon-list values."""
        self.options = [Option("--test", type=Types.colon_list)]
        self.assertItemsEqual(self._test_options(["--test", "one:two three"]),
                              ["one", "two three"])

    def test_literal_dict(self):
        """parse literal-dict values."""
        self.options = [Option("--test", type=Types.literal_dict)]
        expected = {
            "one": True,
            "two": 2,
            "three": "three",
            "four": False,
            "five": {
                "a": 1,
                "b": 2
        }}
        self.assertDictEqual(
            self._test_options(["--test",
                                '''{ "one": True, "two": 2,
                                     "three": "three", "four": False,
                                     "five": { "a": 1, "b": 2 }}''']),
            expected)

    def test_anchored_regex_list(self):
        """parse regex lists."""
        self.options = [Option("--test", type=Types.anchored_regex_list)]
        self.assertItemsEqual(
            [r.pattern for r in self._test_options(["--test", r'\d+  \s*'])],
            [r'^\d+$', r'^\s*$'])
        self.assertRaises(SystemExit,
                          self._test_options, ["--test", '(]'])

    def test_octal(self):
        """parse octal options."""
        self.options = [Option("--test", type=Types.octal)]
        self.assertEqual(self._test_options(["--test", "0777"]), 511)
        self.assertEqual(self._test_options(["--test", "133114255"]), 23894189)

    @patch("pwd.getpwnam")
    def test_username(self, mock_getpwnam):
        """parse username options."""
        self.options = [Option("--test", type=Types.username)]
        mock_getpwnam.return_value = ("test", '********', 1001, 1001,
                                      "Test user", "/home/test", "/bin/bash")
        self.assertEqual(self._test_options(["--test", "1001"]), 1001)
        self.assertEqual(self._test_options(["--test", "test"]), 1001)

    @patch("grp.getgrnam")
    def test_groupname(self, mock_getpwnam):
        """parse group name options."""
        self.options = [Option("--test", type=Types.groupname)]
        mock_getpwnam.return_value = ("test", '*', 1001, ["test"])
        self.assertEqual(self._test_options(["--test", "1001"]), 1001)
        self.assertEqual(self._test_options(["--test", "test"]), 1001)

    def test_timeout(self):
        """parse timeout options."""
        self.options = [Option("--test", type=Types.timeout)]
        self.assertEqual(self._test_options(["--test", "1.0"]), 1.0)
        self.assertEqual(self._test_options(["--test", "1"]), 1.0)
        self.assertEqual(self._test_options(["--test", "0"]), None)

    def test_size(self):
        """parse human-readable size options."""
        self.options = [Option("--test", type=Types.size)]
        self.assertEqual(self._test_options(["--test", "5k"]), 5120)
        self.assertEqual(self._test_options(["--test", "5"]), 5)
        self.assertRaises(SystemExit,
                          self._test_options, ["--test", "g5m"])
