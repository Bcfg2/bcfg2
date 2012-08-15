import os
import copy
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Symlink import *
from Test__init import get_posix_object

def call(*args, **kwargs):
    """ the Mock call object is a fairly recent addition, but it's
    very very useful, so we create our own function to create Mock
    calls """
    return (args, kwargs)

def get_symlink_object(posix=None):
    if posix is None:
        posix = get_posix_object()
    return POSIXSymlink(posix.logger, posix.setup, posix.config)

class TestPOSIXSymlink(unittest.TestCase):
    @patch("os.readlink")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    def test_verify(self, mock_verify, mock_readlink):
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="/dest")
        ptool = get_symlink_object()

        mock_readlink.return_value = entry.get("to")
        mock_verify.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        mock_readlink.assert_called_with(entry.get("name"))
        mock_verify.assert_called_with(ptool, entry, [])

        mock_readlink.reset_mock()
        mock_verify.reset_mock()
        mock_verify.return_value = True
        self.assertTrue(ptool.verify(entry, []))
        mock_readlink.assert_called_with(entry.get("name"))
        mock_verify.assert_called_with(ptool, entry, [])

        mock_readlink.reset_mock()
        mock_verify.reset_mock()
        mock_readlink.return_value = "/bogus"
        self.assertFalse(ptool.verify(entry, []))
        mock_readlink.assert_called_with(entry.get("name"))
        mock_verify.assert_called_with(ptool, entry, [])
        
        mock_readlink.reset_mock()
        mock_verify.reset_mock()
        mock_readlink.side_effect = OSError
        self.assertFalse(ptool.verify(entry, []))
        mock_readlink.assert_called_with(entry.get("name"))

    @patch("os.symlink")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    @patch("Bcfg2.Client.Tools.POSIX.Symlink.POSIXSymlink._exists")
    def test_install(self, mock_exists, mock_install, mock_symlink):
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="/dest")
        ptool = get_symlink_object()

        mock_exists.return_value = False
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_exists.assert_called_with(entry, remove=True)
        mock_symlink.assert_called_with(entry.get("to"), entry.get("name"))
        mock_install.assert_called_with(ptool, entry)

        mock_symlink.reset_mock()
        mock_exists.reset_mock()
        mock_install.reset_mock()
        mock_symlink.side_effect = OSError
        self.assertFalse(ptool.install(entry))
        mock_exists.assert_called_with(entry, remove=True)
        mock_symlink.assert_called_with(entry.get("to"), entry.get("name"))
        mock_install.assert_called_with(ptool, entry)
