import os
import copy
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Hardlink import *
from Test__init import get_posix_object
from .....common import *

def get_hardlink_object(posix=None):
    if posix is None:
        posix = get_posix_object()
    return POSIXHardlink(posix.logger, posix.setup, posix.config)

class TestPOSIXHardlink(Bcfg2TestCase):
    @patch("os.path.samefile")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    def test_verify(self, mock_verify, mock_samefile):
        entry = lxml.etree.Element("Path", name="/test", type="hardlink",
                                   to="/dest")
        ptool = get_hardlink_object()

        mock_samefile.return_value = True
        mock_verify.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        mock_samefile.assert_called_with(entry.get("name"),
                                         entry.get("to"))
        mock_verify.assert_called_with(ptool, entry, [])

        mock_samefile.reset_mock()
        mock_verify.reset_mock()
        mock_verify.return_value = True
        self.assertTrue(ptool.verify(entry, []))
        mock_samefile.assert_called_with(entry.get("name"),
                                         entry.get("to"))
        mock_verify.assert_called_with(ptool, entry, [])

        mock_samefile.reset_mock()
        mock_verify.reset_mock()
        mock_samefile.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        mock_samefile.assert_called_with(entry.get("name"),
                                         entry.get("to"))
        mock_verify.assert_called_with(ptool, entry, [])
        
        mock_samefile.reset_mock()
        mock_verify.reset_mock()
        mock_samefile.side_effect = OSError
        self.assertFalse(ptool.verify(entry, []))
        mock_samefile.assert_called_with(entry.get("name"),
                                         entry.get("to"))

    @patch("os.link")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    @patch("Bcfg2.Client.Tools.POSIX.Hardlink.POSIXHardlink._exists")
    def test_install(self, mock_exists, mock_install, mock_link):
        entry = lxml.etree.Element("Path", name="/test", type="hardlink",
                                   to="/dest")
        ptool = get_hardlink_object()

        mock_exists.return_value = False
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_exists.assert_called_with(entry, remove=True)
        mock_link.assert_called_with(entry.get("to"), entry.get("name"))
        mock_install.assert_called_with(ptool, entry)

        mock_link.reset_mock()
        mock_exists.reset_mock()
        mock_install.reset_mock()
        mock_link.side_effect = OSError
        self.assertFalse(ptool.install(entry))
        mock_exists.assert_called_with(entry, remove=True)
        mock_link.assert_called_with(entry.get("to"), entry.get("name"))
        mock_install.assert_called_with(ptool, entry)
