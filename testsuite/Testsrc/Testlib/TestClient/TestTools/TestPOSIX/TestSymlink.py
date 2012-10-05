import os
import sys
import copy
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Symlink import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from Test__init import get_posix_object
from Testbase import TestPOSIXTool
from common import *

class TestPOSIXSymlink(TestPOSIXTool):
    test_obj = POSIXSymlink

    @patch("os.readlink")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    def test_verify(self, mock_verify, mock_readlink):
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="/dest")
        ptool = self.get_obj()

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
        
        # relative symlink
        mock_readlink.reset_mock()
        mock_verify.reset_mock()
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="dest")
        mock_readlink.return_value = entry.get("to")
        self.assertTrue(ptool.verify(entry, []))
        mock_readlink.assert_called_with(entry.get("name"))
        mock_verify.assert_called_with(ptool, entry, [])

        mock_readlink.reset_mock()
        mock_verify.reset_mock()
        mock_readlink.side_effect = OSError
        self.assertFalse(ptool.verify(entry, []))
        mock_readlink.assert_called_with(entry.get("name"))

    @patch("os.symlink")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    @patch("Bcfg2.Client.Tools.POSIX.Symlink.%s._exists" % test_obj.__name__)
    def test_install(self, mock_exists, mock_install, mock_symlink):
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="/dest")
        ptool = self.get_obj()

        mock_exists.return_value = False
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_exists.assert_called_with(entry, remove=True)
        mock_symlink.assert_called_with(entry.get("to"), entry.get("name"))
        mock_install.assert_called_with(ptool, entry)

        # relative symlink
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="dest")
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
