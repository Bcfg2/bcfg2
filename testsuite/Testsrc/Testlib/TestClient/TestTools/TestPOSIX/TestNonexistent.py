import os
import sys
import copy
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Nonexistent import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from Test__init import get_config, get_posix_object
from Testbase import TestPOSIXTool
from common import *

class TestPOSIXNonexistent(TestPOSIXTool):
    test_obj = POSIXNonexistent

    @patch("os.path.lexists")
    def test_verify(self, mock_lexists):
        entry = lxml.etree.Element("Path", name="/test", type="nonexistent")

        for val in [True, False]:
            mock_lexists.reset_mock()
            mock_lexists.return_value = val
            self.assertEqual(self.ptool.verify(entry, []), not val)
            mock_lexists.assert_called_with(entry.get("name"))

    @patch("os.rmdir")
    @patch("os.remove")
    @patch("os.path.isdir")
    @patch("shutil.rmtree")
    def test_install(self, mock_rmtree, mock_isdir, mock_remove, mock_rmdir):
        entry = lxml.etree.Element("Path", name="/test", type="nonexistent")

        def reset():
            mock_isdir.reset_mock()
            mock_remove.reset_mock()
            mock_rmdir.reset_mock()
            mock_rmtree.reset_mock()

        mock_isdir.return_value = False
        self.assertTrue(self.ptool.install(entry))
        mock_remove.assert_called_with(entry.get("name"))

        reset()
        mock_remove.side_effect = OSError
        self.assertFalse(self.ptool.install(entry))
        mock_remove.assert_called_with(entry.get("name"))

        reset()
        mock_isdir.return_value = True
        self.assertTrue(self.ptool.install(entry))
        mock_rmdir.assert_called_with(entry.get("name"))

        reset()
        mock_rmdir.side_effect = OSError
        self.assertFalse(self.ptool.install(entry))
        mock_rmdir.assert_called_with(entry.get("name"))

        reset()
        entry.set("recursive", "true")
        self.assertTrue(self.ptool.install(entry))
        mock_rmtree.assert_called_with(entry.get("name"))

        reset()
        mock_rmtree.side_effect = OSError
        self.assertFalse(self.ptool.install(entry))
        mock_rmtree.assert_called_with(entry.get("name"))

        reset()
        child_entry = lxml.etree.Element("Path", name="/test/foo",
                                         type="nonexistent")
        ptool = self.get_obj(posix=get_posix_object(config=get_config([child_entry])))
        mock_rmtree.side_effect = None
        self.assertTrue(ptool.install(entry))
        mock_rmtree.assert_called_with(entry.get("name"))

        reset()
        child_entry = lxml.etree.Element("Path", name="/test/foo",
                                         type="file")
        ptool = self.get_obj(posix=get_posix_object(config=get_config([child_entry])))
        mock_rmtree.side_effect = None
        self.assertFalse(ptool.install(entry))
