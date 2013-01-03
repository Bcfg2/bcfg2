import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg import CfgCreationError, CfgCreator
from Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator import *
from Bcfg2.Server.Plugin import StructFile, PluginExecutionError

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
from TestServer.TestPlugins.TestCfg.Test_init import TestCfgCreator
from TestServer.TestPlugin.Testhelpers import TestStructFile


class TestCfgPublicKeyCreator(TestCfgCreator, TestStructFile):
    test_obj = CfgPublicKeyCreator
    should_monitor = False

    def get_obj(self, name=None, fam=None):
        return TestCfgCreator.get_obj(self, name=name)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgCreator.handle_event")
    @patch("Bcfg2.Server.Plugin.helpers.StructFile.HandleEvent")
    def test_handle_event(self, mock_HandleEvent, mock_handle_event):
        pkc = self.get_obj()
        evt = Mock()
        pkc.handle_event(evt)
        mock_HandleEvent.assert_called_with(pkc, evt)
        mock_handle_event.assert_called_with(pkc, evt)

    def test_create_data(self):
        metadata = Mock()
        pkc = self.get_obj()
        pkc.cfg = Mock()

        privkey_entryset = Mock()
        privkey_creator = Mock()
        pubkey = Mock()
        privkey = Mock()
        privkey_creator.create_data.return_value = (pubkey, privkey)
        privkey_entryset.best_matching.return_value = privkey_creator
        pkc.cfg.entries = {"/home/foo/.ssh/id_rsa": privkey_entryset}

        # public key doesn't end in .pub
        entry = lxml.etree.Element("Path", name="/home/bar/.ssh/bogus")
        self.assertRaises(CfgCreationError,
                          pkc.create_data, entry, metadata)

        # private key not in cfg.entries
        entry = lxml.etree.Element("Path", name="/home/bar/.ssh/id_rsa.pub")
        self.assertRaises(CfgCreationError,
                          pkc.create_data, entry, metadata)

        # successful operation
        entry = lxml.etree.Element("Path", name="/home/foo/.ssh/id_rsa.pub")
        self.assertEqual(pkc.create_data(entry, metadata), pubkey)
        privkey_entryset.get_handlers.assert_called_with(metadata, CfgCreator)
        privkey_entryset.best_matching.assert_called_with(metadata,
                                                          privkey_entryset.get_handlers.return_value)
        self.assertXMLEqual(privkey_creator.create_data.call_args[0][0],
                            lxml.etree.Element("Path",
                                               name="/home/foo/.ssh/id_rsa"))
        self.assertEqual(privkey_creator.create_data.call_args[0][1], metadata)

        # no privkey.xml
        privkey_entryset.best_matching.side_effect = PluginExecutionError
        self.assertRaises(CfgCreationError,
                          pkc.create_data, entry, metadata)
