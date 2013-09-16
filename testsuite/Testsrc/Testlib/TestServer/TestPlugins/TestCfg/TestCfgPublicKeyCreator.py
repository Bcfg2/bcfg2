import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg import CfgCreationError, CfgCreator
from Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator import *
import Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator
from Bcfg2.Server.Plugin import PluginExecutionError

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

    @patch("Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator.get_cfg", Mock())
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

    @patch("os.unlink")
    @patch("os.path.exists")
    @patch("tempfile.mkstemp")
    @patch("os.fdopen", Mock())
    @patch("%s.open" % builtins)
    def test_create_data(self, mock_open, mock_mkstemp, mock_exists,
                         mock_unlink):
        metadata = Mock()
        pkc = self.get_obj()
        pkc.cfg = Mock()
        pkc.core = Mock()
        pkc.cmd = Mock()
        pkc.write_data = Mock()

        pubkey = "public key data"
        privkey_entryset = Mock()
        privkey_creator = Mock()
        privkey_creator.get_specificity = Mock()
        privkey_creator.get_specificity.return_value = dict()
        fileloc = pkc.get_filename()
        pkc.cfg.entries = {"/home/foo/.ssh/id_rsa": privkey_entryset}

        def reset():
            privkey_creator.reset_mock()
            pkc.cmd.reset_mock()
            pkc.core.reset_mock()
            pkc.write_data.reset_mock()
            mock_exists.reset_mock()
            mock_unlink.reset_mock()
            mock_mkstemp.reset_mock()
            mock_open.reset_mock()

        # public key doesn't end in .pub
        entry = lxml.etree.Element("Path", name="/home/bar/.ssh/bogus")
        self.assertRaises(CfgCreationError,
                          pkc.create_data, entry, metadata)
        self.assertFalse(pkc.write_data.called)

        # cannot bind private key
        reset()
        pkc.core.Bind.side_effect = PluginExecutionError
        entry = lxml.etree.Element("Path", name="/home/foo/.ssh/id_rsa.pub")
        self.assertRaises(CfgCreationError,
                          pkc.create_data, entry, metadata)
        self.assertFalse(pkc.write_data.called)

        # private key not in cfg.entries
        reset()
        pkc.core.Bind.side_effect = None
        pkc.core.Bind.return_value = "private key data"
        entry = lxml.etree.Element("Path", name="/home/bar/.ssh/id_rsa.pub")
        self.assertRaises(CfgCreationError,
                          pkc.create_data, entry, metadata)
        self.assertFalse(pkc.write_data.called)

        # no privkey.xml defined
        reset()
        privkey_entryset.best_matching.side_effect = PluginExecutionError
        entry = lxml.etree.Element("Path", name="/home/foo/.ssh/id_rsa.pub")
        self.assertRaises(CfgCreationError,
                          pkc.create_data, entry, metadata)
        self.assertFalse(pkc.write_data.called)

        # successful operation, create new key
        reset()
        pkc.cmd.run.return_value = Mock()
        pkc.cmd.run.return_value.success = True
        pkc.cmd.run.return_value.stdout = pubkey
        mock_mkstemp.return_value = (Mock(), str(Mock()))
        mock_exists.return_value = False
        privkey_entryset.best_matching.side_effect = None
        privkey_entryset.best_matching.return_value = privkey_creator
        entry = lxml.etree.Element("Path", name="/home/foo/.ssh/id_rsa.pub")
        self.assertEqual(pkc.create_data(entry, metadata), pubkey)
        self.assertTrue(pkc.core.Bind.called)
        (privkey_entry, md) = pkc.core.Bind.call_args[0]
        self.assertXMLEqual(privkey_entry,
                            lxml.etree.Element("Path",
                                               name="/home/foo/.ssh/id_rsa"))
        self.assertEqual(md, metadata)

        privkey_entryset.get_handlers.assert_called_with(metadata, CfgCreator)
        privkey_entryset.best_matching.assert_called_with(
            metadata,
            privkey_entryset.get_handlers.return_value)
        mock_exists.assert_called_with(fileloc)
        pkc.cmd.run.assert_called_with(["ssh-keygen", "-y", "-f",
                                        mock_mkstemp.return_value[1]])
        self.assertEqual(pkc.write_data.call_args[0][0], pubkey)
        mock_unlink.assert_called_with(mock_mkstemp.return_value[1])
        self.assertFalse(mock_open.called)

        # successful operation, no need to create new key
        reset()
        mock_exists.return_value = True
        mock_open.return_value = Mock()
        mock_open.return_value.read.return_value = pubkey
        pkc.cmd.run.return_value.stdout = None
        self.assertEqual(pkc.create_data(entry, metadata), pubkey)
        self.assertTrue(pkc.core.Bind.called)
        (privkey_entry, md) = pkc.core.Bind.call_args[0]
        self.assertXMLEqual(privkey_entry,
                            lxml.etree.Element("Path",
                                               name="/home/foo/.ssh/id_rsa"))
        self.assertEqual(md, metadata)

        privkey_entryset.get_handlers.assert_called_with(metadata, CfgCreator)
        privkey_entryset.best_matching.assert_called_with(
            metadata,
            privkey_entryset.get_handlers.return_value)
        mock_exists.assert_called_with(fileloc)
        mock_open.assert_called_with(fileloc)
        self.assertFalse(mock_mkstemp.called)
        self.assertFalse(pkc.write_data.called)
