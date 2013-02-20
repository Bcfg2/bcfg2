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
from Test__init import get_config
from Testbase import TestPOSIXTool
from common import *


class TestPOSIXNonexistent(TestPOSIXTool):
    test_obj = POSIXNonexistent

    @patch("os.path.lexists")
    def test_verify(self, mock_lexists):
        ptool = self.get_obj()
        entry = lxml.etree.Element("Path", name="/test", type="nonexistent")

        for val in [True, False]:
            mock_lexists.reset_mock()
            mock_lexists.return_value = val
            self.assertEqual(ptool.verify(entry, []), not val)
            mock_lexists.assert_called_with(entry.get("name"))

    def test_install(self):
        entry = lxml.etree.Element("Path", name="/test", type="nonexistent")

        ptool = self.get_obj()
        ptool._remove = Mock()

        def reset():
            ptool._remove.reset_mock()

        self.assertTrue(ptool.install(entry))
        ptool._remove.assert_called_with(entry, recursive=False)

        reset()
        entry.set("recursive", "true")
        self.assertTrue(ptool.install(entry))
        ptool._remove.assert_called_with(entry, recursive=True)

        reset()
        child_entry = lxml.etree.Element("Path", name="/test/foo",
                                         type="nonexistent")
        ptool = self.get_obj(config=get_config([child_entry]))
        ptool._remove = Mock()
        self.assertTrue(ptool.install(entry))
        ptool._remove.assert_called_with(entry, recursive=True)

        reset()
        child_entry = lxml.etree.Element("Path", name="/test/foo",
                                         type="file")
        ptool = self.get_obj(config=get_config([child_entry]))
        ptool._remove = Mock()
        self.assertFalse(ptool.install(entry))
        self.assertFalse(ptool._remove.called)

        reset()
        entry.set("recursive", "false")
        ptool._remove.side_effect = OSError
        self.assertFalse(ptool.install(entry))
        ptool._remove.assert_called_with(entry, recursive=False)
