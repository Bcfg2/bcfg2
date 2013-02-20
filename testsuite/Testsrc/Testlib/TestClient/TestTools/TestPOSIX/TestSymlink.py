import os
import sys
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
from Testbase import TestPOSIXLinkTool
from common import *


class TestPOSIXSymlink(TestPOSIXLinkTool):
    test_obj = POSIXSymlink

    @patch("os.readlink")
    def test__verify(self, mock_readlink):
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="/dest")
        ptool = self.get_obj()

        mock_readlink.return_value = entry.get("to")
        self.assertTrue(ptool._verify(entry))
        mock_readlink.assert_called_with(entry.get("name"))

        mock_readlink.reset_mock()
        mock_readlink.return_value = "/bogus"
        self.assertFalse(ptool._verify(entry))
        mock_readlink.assert_called_with(entry.get("name"))

    @patch("os.symlink")
    def test__link(self, mock_symlink):
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="/dest")
        ptool = self.get_obj()
        self.assertEqual(ptool._link(entry),
                         mock_symlink.return_value)
        mock_symlink.assert_called_with(entry.get("to"), entry.get("name"))
