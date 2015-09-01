import os
import sys
import copy
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
from Testinterfaces import TestGoalValidator


class TestDefaults(TestRules, TestGoalValidator):
    test_obj = Defaults

    def setUp(self):
        TestRules.setUp(self)
        set_setup_default("defaults_replace_name", True)

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

    def test_validate_goals(self):
        d = self.get_obj()
        d.BindEntry = Mock()
        metadata = Mock()

        entries = []
        config = lxml.etree.Element("Configuration")
        b1 = lxml.etree.SubElement(config, "Bundle")
        entries.append(lxml.etree.SubElement(b1, "Path", name="/foo"))
        entries.append(lxml.etree.SubElement(b1, "Path", name="/bar"))
        b2 = lxml.etree.SubElement(config, "Bundle")
        entries.append(lxml.etree.SubElement(b2, "Package", name="quux"))

        d.validate_goals(metadata, config)
        self.assertItemsEqual(d.BindEntry.call_args_list,
                              [call(e, metadata) for e in entries])

    def test__matches_regex_disabled(self):
        """ cannot disable regex in Defaults plugin """
        pass

    def set_regex_enabled(self, rules_obj, state):
        pass

    def test__regex_enabled(self):
        r = self.get_obj()
        self.assertTrue(r._regex_enabled)

    def _do_test(self, name, groups=None):
        if groups is None:
            groups = []
        d = self.get_obj()
        metadata = Mock(groups=groups)
        config = lxml.etree.Element("Configuration")
        struct = lxml.etree.SubElement(config, "Bundle", name=name)
        entry = copy.deepcopy(self.abstract[name])
        struct.append(entry)
        d.validate_goals(metadata, config)
        self.assertXMLEqual(entry, self.concrete[name])

    def _do_test_failure(self, name, groups=None, handles=None):
        if groups is None:
            groups = []
        d = self.get_obj()
        metadata = Mock(groups=groups)
        config = lxml.etree.Element("Configuration")
        struct = lxml.etree.SubElement(config, "Bundle", name=name)
        orig = copy.deepcopy(self.abstract[name])
        entry = copy.deepcopy(self.abstract[name])
        struct.append(entry)
        d.validate_goals(metadata, config)
        self.assertXMLEqual(entry, orig)

    def test_regex(self):
        self._do_test('regex')

    def test_replace_name(self):
        Bcfg2.Options.setup.defaults_replace_name = True
        self._do_test('replace_name')
        Bcfg2.Options.setup.defaults_replace_name = False
