import os
import sys
import copy
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Device import *

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


class TestPOSIXDevice(TestPOSIXTool):
    test_obj = POSIXDevice

    def test_fully_specified(self):
        ptool = self.get_obj()
        orig_entry = lxml.etree.Element("Path", name="/test", type="device",
                                        dev_type="fifo")
        self.assertTrue(ptool.fully_specified(orig_entry))
        for dtype in ["block", "char"]:
            for attr in ["major", "minor"]:
                entry = copy.deepcopy(orig_entry)
                entry.set("dev_type", dtype)
                entry.set(attr, "0")
                self.assertFalse(ptool.fully_specified(entry))
            entry = copy.deepcopy(orig_entry)
            entry.set("dev_type", dtype)
            entry.set("major", "0")
            entry.set("minor", "0")
            self.assertTrue(ptool.fully_specified(entry))

    @patch("os.major")
    @patch("os.minor")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    def test_verify(self, mock_verify, mock_minor, mock_major):
        entry = lxml.etree.Element("Path", name="/test", type="device",
                                   mode='0644', owner='root', group='root',
                                   dev_type="block", major="0", minor="10")
        ptool = self.get_obj()
        ptool._exists = Mock()

        def reset():
            ptool._exists.reset_mock()
            mock_verify.reset_mock()
            mock_minor.reset_mock()
            mock_major.reset_mock()

        ptool._exists.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        ptool._exists.assert_called_with(entry)

        reset()
        ptool._exists.return_value = MagicMock()
        mock_major.return_value = 0
        mock_minor.return_value = 10
        mock_verify.return_value = True
        self.assertTrue(ptool.verify(entry, []))
        mock_verify.assert_called_with(ptool, entry, [])
        ptool._exists.assert_called_with(entry)
        mock_major.assert_called_with(ptool._exists.return_value.st_rdev)
        mock_minor.assert_called_with(ptool._exists.return_value.st_rdev)

        reset()
        ptool._exists.return_value = MagicMock()
        mock_major.return_value = 0
        mock_minor.return_value = 10
        mock_verify.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        mock_verify.assert_called_with(ptool, entry, [])
        ptool._exists.assert_called_with(entry)
        mock_major.assert_called_with(ptool._exists.return_value.st_rdev)
        mock_minor.assert_called_with(ptool._exists.return_value.st_rdev)

        reset()
        mock_verify.return_value = True
        entry = lxml.etree.Element("Path", name="/test", type="device",
                                   mode='0644', owner='root', group='root',
                                   dev_type="fifo")
        self.assertTrue(ptool.verify(entry, []))
        ptool._exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])
        self.assertFalse(mock_major.called)
        self.assertFalse(mock_minor.called)

    @patch("os.makedev")
    @patch("os.mknod")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    def test_install(self, mock_install, mock_mknod, mock_makedev):
        entry = lxml.etree.Element("Path", name="/test", type="device",
                                   mode='0644', owner='root', group='root',
                                   dev_type="block", major="0", minor="10")
        ptool = self.get_obj()
        ptool._exists = Mock()

        ptool._exists.return_value = False
        mock_makedev.return_value = Mock()
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        ptool._exists.assert_called_with(entry, remove=True)
        mock_makedev.assert_called_with(0, 10)
        mock_mknod.assert_called_with(entry.get("name"),               # 0o644
                                      device_map[entry.get("dev_type")] | 420,
                                      mock_makedev.return_value)
        mock_install.assert_called_with(ptool, entry)

        mock_makedev.reset_mock()
        mock_mknod.reset_mock()
        ptool._exists.reset_mock()
        mock_install.reset_mock()
        mock_makedev.side_effect = OSError
        self.assertFalse(ptool.install(entry))

        mock_makedev.reset_mock()
        mock_mknod.reset_mock()
        ptool._exists.reset_mock()
        mock_install.reset_mock()
        mock_mknod.side_effect = OSError
        self.assertFalse(ptool.install(entry))

        mock_makedev.reset_mock()
        mock_mknod.reset_mock()
        ptool._exists.reset_mock()
        mock_install.reset_mock()
        mock_mknod.side_effect = None
        entry = lxml.etree.Element("Path", name="/test", type="device",
                                   mode='0644', owner='root', group='root',
                                   dev_type="fifo")

        self.assertTrue(ptool.install(entry))
        ptool._exists.assert_called_with(entry, remove=True)
        mock_mknod.assert_called_with(entry.get("name"),               # 0o644
                                      device_map[entry.get("dev_type")] | 420)
        mock_install.assert_called_with(ptool, entry)
