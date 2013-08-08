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

    def setUp(self):
        TestPrioDir.setUp(self)
        set_setup_default("rules_regex", False)

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

    @patch("Bcfg2.Server.Plugin.PrioDir._matches")
    def test__matches(self, mock_matches):
        r = self.get_obj()
        metadata = Mock()

        # test parent _matches() returning True
        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        candidate = lxml.etree.Element("Path", name="/etc/bar.conf")
        mock_matches.return_value = True
        self.assertTrue(r._matches(entry, metadata, candidate))
        mock_matches.assert_called_with(r, entry, metadata, candidate)

        # test all conditions returning False
        mock_matches.reset_mock()
        mock_matches.return_value = False
        self.assertFalse(r._matches(entry, metadata, candidate))
        mock_matches.assert_called_with(r, entry, metadata, candidate)

        # test special Path cases -- adding and removing trailing slash
        mock_matches.reset_mock()
        withslash = lxml.etree.Element("Path", name="/etc/foo")
        withoutslash = lxml.etree.Element("Path", name="/etc/foo/")
        self.assertTrue(r._matches(withslash, metadata, withoutslash))
        self.assertTrue(r._matches(withoutslash, metadata, withslash))

        if r._regex_enabled:
            mock_matches.reset_mock()
            candidate = lxml.etree.Element("Path", name="/etc/.*\.conf")
            self.assertTrue(r._matches(entry, metadata, candidate))
            mock_matches.assert_called_with(r, entry, metadata, candidate)
            self.assertIn("/etc/.*\.conf", r._regex_cache.keys())
