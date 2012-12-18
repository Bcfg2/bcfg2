import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Defaults import *

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
from TestRules import TestRules
from Testinterfaces import TestStructureValidator


class TestDefaults(TestRules, TestStructureValidator):
    test_obj = Defaults

    def get_obj(self, *args, **kwargs):
        return TestRules.get_obj(self, *args, **kwargs)

    def test_HandlesEntry(self):
        d = self.get_obj()
        self.assertFalse(d.HandlesEntry(Mock(), Mock()))

    @patch("Bcfg2.Server.Plugin.helpers.XMLDirectoryBacked.HandleEvent")
    def test_HandleEvent(self, mock_HandleEvent):
        d = self.get_obj()
        evt = Mock()
        d.HandleEvent(evt)
        mock_HandleEvent.assert_called_with(d, evt)

    def test_validate_structures(self):
        d = self.get_obj()
        d.BindEntry = Mock()
        metadata = Mock()

        entries = []
        b1 = lxml.etree.Element("Bundle")
        entries.append(lxml.etree.SubElement(b1, "Path", name="/foo"))
        entries.append(lxml.etree.SubElement(b1, "Path", name="/bar"))
        b2 = lxml.etree.Element("Bundle")
        bound = lxml.etree.SubElement(b2, "BoundPath", name="/baz")
        entries.append(bound)
        entries.append(lxml.etree.SubElement(b2, "Package", name="quux"))

        d.validate_structures(metadata, [b1, b2])
        self.assertItemsEqual(d.BindEntry.call_args_list,
                              [call(e, metadata) for e in entries])
        # ensure that BoundEntries stay bound
        self.assertTrue(bound.tag == "BoundPath")

    def test__matches_regex_disabled(self):
        """ cannot disable regex in Defaults plugin """
        pass

    def set_regex_enabled(self, rules_obj, state):
        pass

    def test__regex_enabled(self):
        r = self.get_obj()
        self.assertTrue(r._regex_enabled)
