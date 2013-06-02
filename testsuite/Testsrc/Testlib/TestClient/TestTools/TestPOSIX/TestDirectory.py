import os
import sys
import stat
import copy
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Directory import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from Testbase import TestPOSIXTool
from common import *


class TestPOSIXDirectory(TestPOSIXTool):
    test_obj = POSIXDirectory

    @patch("os.listdir")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    def test_verify(self, mock_verify, mock_listdir):
        ptool = self.get_obj()
        ptool._exists = Mock()
        entry = lxml.etree.Element("Path", name="/test", type="directory",
                                   mode='0644', owner='root', group='root')

        ptool._exists.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        ptool._exists.assert_called_with(entry)

        ptool._exists.reset_mock()
        exists_rv = MagicMock()
        exists_rv.__getitem__.return_value = stat.S_IFREG | 420 # 0o644
        ptool._exists.return_value = exists_rv
        self.assertFalse(ptool.verify(entry, []))
        ptool._exists.assert_called_with(entry)

        ptool._exists.reset_mock()
        mock_verify.return_value = False
        exists_rv.__getitem__.return_value = stat.S_IFDIR | 420 # 0o644
        self.assertFalse(ptool.verify(entry, []))
        ptool._exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])

        ptool._exists.reset_mock()
        mock_verify.reset_mock()
        mock_verify.return_value = True
        self.assertTrue(ptool.verify(entry, []))
        ptool._exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])

        ptool._exists.reset_mock()
        mock_verify.reset_mock()
        entry.set("prune", "true")
        orig_entry = copy.deepcopy(entry)

        entries = ["foo", "bar", "bar/baz"]
        mock_listdir.return_value = entries
        modlist = [os.path.join(entry.get("name"), entries[0])]
        self.assertFalse(ptool.verify(entry, modlist))
        ptool._exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, modlist)
        mock_listdir.assert_called_with(entry.get("name"))
        expected = [os.path.join(entry.get("name"), e)
                    for e in entries
                    if os.path.join(entry.get("name"), e) not in modlist]
        actual = [e.get("name") for e in entry.findall("Prune")]
        self.assertItemsEqual(expected, actual)

        mock_verify.reset_mock()
        ptool._exists.reset_mock()
        mock_listdir.reset_mock()
        entry = copy.deepcopy(orig_entry)
        modlist = [os.path.join(entry.get("name"), e)
                   for e in entries]
        self.assertTrue(ptool.verify(entry, modlist))
        ptool._exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, modlist)
        mock_listdir.assert_called_with(entry.get("name"))
        self.assertEqual(len(entry.findall("Prune")), 0)

    @patch("os.unlink")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    def test_install(self, mock_install, mock_unlink):
        entry = lxml.etree.Element("Path", name="/test/foo/bar",
                                   type="directory", mode='0644',
                                   owner='root', group='root')

        ptool = self.get_obj()
        ptool._exists = Mock()
        ptool._makedirs = Mock()
        ptool._remove = Mock()

        def reset():
            ptool._exists.reset_mock()
            mock_install.reset_mock()
            mock_unlink.reset_mock()
            ptool._makedirs.reset_mock()
            ptool._remove.reset_mock()

        ptool._makedirs.return_value = True
        ptool._exists.return_value = False
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        ptool._exists.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)
        ptool._makedirs.assert_called_with(entry)

        reset()
        exists_rv = MagicMock()
        exists_rv.__getitem__.return_value = stat.S_IFREG | 420 # 0o644
        ptool._exists.return_value = exists_rv
        self.assertTrue(ptool.install(entry))
        mock_unlink.assert_called_with(entry.get("name"))
        ptool._exists.assert_called_with(entry)
        ptool._makedirs.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)

        reset()
        exists_rv.__getitem__.return_value = stat.S_IFDIR | 420 # 0o644
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        ptool._exists.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)

        reset()
        mock_install.return_value = False
        self.assertFalse(ptool.install(entry))
        mock_install.assert_called_with(ptool, entry)

        entry.set("prune", "true")
        prune = ["/test/foo/bar/prune1", "/test/foo/bar/prune2"]
        for path in prune:
            lxml.etree.SubElement(entry, "Prune", name=path)

        reset()
        mock_install.return_value = True

        self.assertTrue(ptool.install(entry))
        ptool._exists.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)
        self.assertItemsEqual([c[0][0].get("name")
                               for c in ptool._remove.call_args_list],
                              prune)
