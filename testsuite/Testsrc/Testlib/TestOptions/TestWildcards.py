"""test wildcard options."""

import argparse

from Bcfg2.Options import Option, Parser
from testsuite.Testsrc.Testlib.TestOptions import OptionTestCase, make_config


class TestWildcardOptions(OptionTestCase):
    """test parsing wildcard options."""
    config = {
        "foo": {
            "test1": "test1",
            "test2": "test2",
            "thing1": "thing1",
            "thing2": "thing2",
            "foo": "foo"
        }
    }

    def setUp(self):
        # parsing options can modify the Option objects themselves.
        # that's probably bad -- and it's definitely bad if we ever
        # want to do real on-the-fly config changes -- but it's easier
        # to leave it as is and set the options on each test.
        self.options = [
            Option(cf=("foo", "*"), dest="all"),
            Option(cf=("foo", "test*"), dest="test"),
            Option(cf=("foo", "bogus*"), dest="unmatched"),
            Option(cf=("bar", "*"), dest="no_section"),
            Option(cf=("foo", "foo"))]

    @make_config(config)
    def test_wildcard_options(self, config_file):
        """parse wildcard options."""
        result = argparse.Namespace()
        parser = Parser(components=[self], namespace=result)
        parser.parse(argv=["-C", config_file])

        self.assertDictEqual(result.all, {"test1": "test1",
                                          "test2": "test2",
                                          "thing1": "thing1",
                                          "thing2": "thing2"})
        self.assertDictEqual(result.test, {"test1": "test1",
                                           "test2": "test2"})
        self.assertDictEqual(result.unmatched, {})
        self.assertDictEqual(result.no_section, {})
