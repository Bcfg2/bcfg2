import os
import sys
import lxml.etree
import Bcfg2.Server.Plugin
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Rules import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import *
from TestPlugin import TestPrioDir


class TestRules(TestPrioDir):
    test_obj = Rules

    def test_HandlesEntry(self):
        r = self.get_obj()
        r.Entries = dict(Path={"/etc/foo.conf": Mock(),
                               "/etc/bar.conf": Mock()})
        r._matches = Mock()
        metadata = Mock()

        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        self.assertEqual(r.HandlesEntry(entry, metadata),
                         r._matches.return_value)
        r._matches.assert_called_with(entry, metadata,
                                      r.Entries['Path'].keys())

        r._matches.reset_mock()
        entry = lxml.etree.Element("Path", name="/etc/baz.conf")
        self.assertEqual(r.HandlesEntry(entry, metadata),
                         r._matches.return_value)
        r._matches.assert_called_with(entry, metadata,
                                      r.Entries['Path'].keys())

        r._matches.reset_mock()
        entry = lxml.etree.Element("Package", name="foo")
        self.assertFalse(r.HandlesEntry(entry, metadata))

    def test_BindEntry(self, method="BindEntry"):
        r = self.get_obj()
        r.get_attrs = Mock()
        r.get_attrs.return_value = dict(overwrite="new", add="add",
                                        text="text")
        entry = lxml.etree.Element("Test", overwrite="old", keep="keep")
        metadata = Mock()

        getattr(r, method)(entry, metadata)
        r.get_attrs.assert_called_with(entry, metadata)
        self.assertItemsEqual(entry.attrib,
                              dict(overwrite="old", add="add", keep="keep",
                                   text="text"))

    def test_HandleEntry(self):
        self.test_BindEntry(method="HandleEntry")

    @patch("Bcfg2.Server.Plugin.PrioDir._matches")
    def test__matches(self, mock_matches):
        """ test _matches() behavior regardless of state of _regex_enabled """
        r = self.get_obj()
        metadata = Mock()

        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        rules = []
        mock_matches.return_value = True
        self.assertTrue(r._matches(entry, metadata, rules))
        mock_matches.assert_called_with(r, entry, metadata, rules)

        # test special Path cases -- adding and removing trailing slash
        mock_matches.reset_mock()
        mock_matches.return_value = False
        rules = ["/etc/foo/", "/etc/bar"]
        entry = lxml.etree.Element("Path", name="/etc/foo")
        self.assertTrue(r._matches(entry, metadata, rules))
        mock_matches.assert_called_with(r, entry, metadata, rules)

        mock_matches.reset_mock()
        entry = lxml.etree.Element("Path", name="/etc/bar/")
        self.assertTrue(r._matches(entry, metadata, rules))
        mock_matches.assert_called_with(r, entry, metadata, rules)

    @patch("Bcfg2.Server.Plugin.PrioDir._matches")
    def test__matches_regex_disabled(self, mock_matches):
        """ test failure to match with regex disabled """
        r = self.get_obj()
        self.set_regex_enabled(r, False)
        metadata = Mock()
        mock_matches.return_value = False

        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        rules = []
        self.assertFalse(r._matches(entry, metadata, rules))
        mock_matches.assert_called_with(r, entry, metadata, rules)

    @patch("Bcfg2.Server.Plugin.PrioDir._matches")
    def test__matches_regex_enabled(self, mock_matches):
        """ test match with regex enabled """
        r = self.get_obj()
        self.set_regex_enabled(r, True)
        metadata = Mock()
        mock_matches.return_value = False

        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        rules = ["/etc/.*\.conf", "/etc/bar"]
        self.assertTrue(r._matches(entry, metadata, rules))
        mock_matches.assert_called_with(r, entry, metadata, rules)
        self.assertIn("/etc/.*\.conf", r._regex_cache.keys())

    def set_regex_enabled(self, rules_obj, state):
        """ set the state of regex_enabled for this implementation of
        Rules """
        if not isinstance(rules_obj.core.setup, MagicMock):
            rules_obj.core.setup = MagicMock()
        rules_obj.core.setup.cfp.getboolean.return_value = state

    def test__regex_enabled(self):
        r = self.get_obj()
        r.core.setup = MagicMock()
        self.assertEqual(r._regex_enabled,
                         r.core.setup.cfp.getboolean.return_value)
        r.core.setup.cfp.getboolean.assert_called_with("rules", "regex",
                                                       default=False)
