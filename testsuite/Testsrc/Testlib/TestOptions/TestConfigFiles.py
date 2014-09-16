"""test reading multiple config files."""

import argparse

from Bcfg2.Options import Option, PathOption, ConfigFileAction, get_parser, \
    new_parser

from testsuite.Testsrc.Testlib.TestOptions import make_config, OptionTestCase


class TestConfigFiles(OptionTestCase):
    def setUp(self):
        self.options = [
            PathOption(cf=("test", "config2"), action=ConfigFileAction),
            PathOption(cf=("test", "config3"), action=ConfigFileAction),
            Option(cf=("test", "foo")),
            Option(cf=("test", "bar")),
            Option(cf=("test", "baz"))]
        self.results = argparse.Namespace()
        new_parser()
        self.parser = get_parser(components=[self], namespace=self.results)

    @make_config({"test": {"baz": "baz"}})
    def test_config_files(self, config3):
        """read multiple config files."""
        # Because make_config() generates temporary files for the
        # configuration, we have to work backwards here.  first we
        # generate config3, then we generate config2 (which includes a
        # reference to config3), then we finally generate the main
        # config file, which contains a reference to config2.  oh how
        # I wish we could use context managers here...

        @make_config({"test": {"bar": "bar", "config3": config3}})
        def inner1(config2):
            @make_config({"test": {"foo": "foo", "config2": config2}})
            def inner2(config):
                self.parser.parse(["-C", config])
                self.assertEqual(self.results.foo, "foo")
                self.assertEqual(self.results.bar, "bar")
                self.assertEqual(self.results.baz, "baz")

            inner2()

        inner1()

    def test_no_config_file(self):
        """fail to read config file."""
        self.assertRaises(SystemExit, self.parser.parse, [])
