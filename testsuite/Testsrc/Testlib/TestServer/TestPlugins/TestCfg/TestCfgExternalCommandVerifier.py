import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg.CfgExternalCommandVerifier import *
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
from TestServer.TestPlugins.TestCfg.Test_init import TestCfgVerifier


class TestCfgExternalCommandVerifier(TestCfgVerifier):
    test_obj = CfgExternalCommandVerifier

    @patch("Bcfg2.Server.Plugins.Cfg.CfgExternalCommandVerifier.Popen")
    def test_verify_entry(self, mock_Popen):
        proc = Mock()
        mock_Popen.return_value = proc
        proc.wait.return_value = 0
        proc.communicate.return_value = MagicMock()
        entry = lxml.etree.Element("Path", name="/test.txt")
        metadata = Mock()

        ecv = self.get_obj()
        ecv.cmd = ["/bin/bash", "-x", "foo"]
        ecv.verify_entry(entry, metadata, "data")
        self.assertEqual(mock_Popen.call_args[0], (ecv.cmd,))
        proc.communicate.assert_called_with(input="data")
        proc.wait.assert_called_with()

        mock_Popen.reset_mock()
        proc.wait.return_value = 13
        self.assertRaises(CfgVerificationError,
                          ecv.verify_entry, entry, metadata, "data")
        self.assertEqual(mock_Popen.call_args[0], (ecv.cmd,))
        proc.communicate.assert_called_with(input="data")
        proc.wait.assert_called_with()

        mock_Popen.reset_mock()
        mock_Popen.side_effect = OSError
        self.assertRaises(CfgVerificationError,
                          ecv.verify_entry, entry, metadata, "data")
        self.assertEqual(mock_Popen.call_args[0], (ecv.cmd,))

    @patch("os.access")
    def test_handle_event(self, mock_access):
        @patch("Bcfg2.Server.Plugins.Cfg.CfgVerifier.handle_event")
        def inner(mock_handle_event):
            ecv = self.get_obj()
            event = Mock()
            mock_access.return_value = False
            ecv.data = "data"
            self.assertRaises(PluginExecutionError,
                              ecv.handle_event, event)
            mock_handle_event.assert_called_with(ecv, event)
            mock_access.assert_called_with(ecv.name, os.X_OK)
            self.assertItemsEqual(ecv.cmd, [])

            mock_access.reset_mock()
            mock_handle_event.reset_mock()
            ecv.data = "#! /bin/bash -x\ntrue"
            ecv.handle_event(event)
            mock_handle_event.assert_called_with(ecv, event)
            mock_access.assert_called_with(ecv.name, os.X_OK)
            self.assertEqual(ecv.cmd, ["/bin/bash", "-x", ecv.name])

            mock_access.reset_mock()
            mock_handle_event.reset_mock()
            mock_access.return_value = True
            ecv.data = "true"
            ecv.handle_event(event)
            mock_handle_event.assert_called_with(ecv, event)
            mock_access.assert_called_with(ecv.name, os.X_OK)
            self.assertItemsEqual(ecv.cmd, [ecv.name])

        inner()
        mock_access.return_value = True
        TestCfgVerifier.test_handle_event(self)
