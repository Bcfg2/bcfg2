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
        entry = lxml.etree.Element("Path", name="/test.txt")
        metadata = Mock()
        ci = self.get_obj()
        ci.infoxml = Mock()
        ci._set_info = Mock()

        self.assertRaises(PluginExecutionError,
                          ci.bind_info_to_entry, entry, metadata)
        ci.infoxml.pnode.Match.assert_called_with(metadata, dict(),
                                                  entry=entry)
        self.assertFalse(ci._set_info.called)

        ci.infoxml.reset_mock()
        ci._set_info.reset_mock()
        mdata_value = Mock()
        def set_mdata(metadata, mdata, entry=None):
            mdata['Info'] = {None: mdata_value}

        ci.infoxml.pnode.Match.side_effect = set_mdata
        ci.bind_info_to_entry(entry, metadata)
        ci.infoxml.pnode.Match.assert_called_with(metadata,
                                                  dict(Info={None: mdata_value}),
                                                  entry=entry)
        ci._set_info.assert_called_with(entry, mdata_value)

    def test_handle_event(self):
        ci = self.get_obj()
        ci.infoxml = Mock()
        ci.handle_event(Mock)
        ci.infoxml.HandleEvent.assert_called_with()

    def test__set_info(self):
        @patch("Bcfg2.Server.Plugins.Cfg.CfgInfo._set_info")
        def inner(mock_set_info):
            ci = self.get_obj()
            entry = Mock()
            info = {"foo": "foo",
                    "__children__": ["one", "two"]}
            ci._set_info(entry, info)
            self.assertItemsEqual(entry.append.call_args_list,
                                  [call(c) for c in info['__children__']])

        inner()
        TestCfgInfo.test__set_info(self)
