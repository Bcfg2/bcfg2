import os
import sys
import copy
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Hardlink import *

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


class TestPOSIXHardlink(TestPOSIXLinkTool):
    test_obj = POSIXHardlink

    @patch("os.path.samefile")
    def test__verify(self, mock_samefile):
        entry = lxml.etree.Element("Path", name="/test", type="hardlink",
                                   to="/dest")
        ptool = self.get_obj()
        self.assertEqual(ptool._verify(entry), mock_samefile.return_value)
        self.assertItemsEqual(mock_samefile.call_args[0],
                              [entry.get("name"), entry.get("to")])

    @patch("os.link")
    def test__link(self, mock_link):
        entry = lxml.etree.Element("Path", name="/test", type="hardlink",
                                   to="/dest")
        ptool = self.get_obj()
        self.assertEqual(ptool._link(entry), mock_link.return_value)
        mock_link.assert_called_with(entry.get("to"), entry.get("name"))
