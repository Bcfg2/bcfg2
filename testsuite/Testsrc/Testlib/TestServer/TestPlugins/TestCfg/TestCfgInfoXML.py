import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg.CfgInfoXML import *
from Bcfg2.Server.Plugin import InfoXML, PluginExecutionError

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
from TestServer.TestPlugins.TestCfg.Test_init import TestCfgInfo


class TestCfgInfoXML(TestCfgInfo):
    test_obj = CfgInfoXML

    def test__init(self):
        TestCfgInfo.test__init(self)
        ci = self.get_obj()
        self.assertIsInstance(ci.infoxml, InfoXML)

    def test_bind_info_to_entry(self):
        ci = self.get_obj()
        ci.infoxml = Mock()
        entry = Mock()
        metadata = Mock()

        ci.bind_info_to_entry(entry, metadata)
        ci.infoxml.BindEntry.assert_called_with(entry, metadata)

    def test_handle_event(self):
        ci = self.get_obj()
        ci.infoxml = Mock()
        ci.handle_event(Mock)
        ci.infoxml.HandleEvent.assert_called_with()
