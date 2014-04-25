import os
import sys
import lxml.etree
import Bcfg2.Server.Plugins.Cfg
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator import *
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
from TestServer.TestPlugins.TestCfg.Test_init import TestCfgGenerator


class TestCfgEncryptedGenerator(TestCfgGenerator):
    test_obj = CfgEncryptedGenerator

    @skipUnless(HAS_CRYPTO, "M2Crypto is not available")
    def setUp(self):
        TestCfgGenerator.setUp(self)

    @patchIf(HAS_CRYPTO,
             "Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator.bruteforce_decrypt")
    def test_handle_event(self, mock_decrypt):
        @patch("Bcfg2.Server.Plugins.Cfg.CfgGenerator.handle_event")
        @patch("Bcfg2.Options.setup.lax_decryption", False)
        def inner(mock_handle_event):
            def reset():
                mock_decrypt.reset_mock()
                mock_handle_event.reset_mock()

            def get_event_data(obj, event):
                obj.data = "encrypted"

            mock_handle_event.side_effect = get_event_data
            mock_decrypt.side_effect = lambda d, **kw: "plaintext"
            event = Mock()
            ceg = self.get_obj()
            ceg.handle_event(event)
            mock_handle_event.assert_called_with(ceg, event)
            mock_decrypt.assert_called_with("encrypted")
            self.assertEqual(ceg.data, "plaintext")

            reset()
            mock_decrypt.side_effect = EVPError
            self.assertRaises(PluginExecutionError,
                              ceg.handle_event, event)
        inner()

        # to perform the tests from the parent test object, we
        # make bruteforce_decrypt just return whatever data was
        # given to it
        mock_decrypt.side_effect = lambda d, **kw: d
        TestCfgGenerator.test_handle_event(self)

    def test_get_data(self):
        ceg = self.get_obj()
        ceg.data = None
        entry = lxml.etree.Element("Path", name="/test.txt")
        metadata = Mock()

        self.assertRaises(PluginExecutionError,
                          ceg.get_data, entry, metadata)

        TestCfgGenerator.test_get_data(self)
