import os
import sys
import lxml.etree
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


if can_skip or HAS_CRYPTO:
    class TestCfgEncryptedGenerator(TestCfgGenerator):
        test_obj = CfgEncryptedGenerator

        @skipUnless(HAS_CRYPTO, "Encryption libraries not found, skipping")
        def setUp(self):
            pass

        @patchIf(HAS_CRYPTO,
                 "Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator.get_algorithm")
        @patchIf(HAS_CRYPTO,
                 "Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator.bruteforce_decrypt")
        def test_handle_event(self, mock_decrypt, mock_get_algorithm):
            @patch("Bcfg2.Server.Plugins.Cfg.CfgGenerator.handle_event")
            def inner(mock_handle_event):
                def reset():
                    mock_decrypt.reset_mock()
                    mock_get_algorithm.reset_mock()
                    mock_handle_event.reset_mock()

                def get_event_data(obj, event):
                    obj.data = "encrypted"

                mock_handle_event.side_effect = get_event_data
                mock_decrypt.side_effect = lambda d, **kw: "plaintext"
                event = Mock()
                ceg = self.get_obj()
                ceg.handle_event(event)
                mock_handle_event.assert_called_with(ceg, event)
                mock_decrypt.assert_called_with("encrypted",
                                                setup=SETUP,
                                                algorithm=mock_get_algorithm.return_value)
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
