import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
import Bcfg2.Client.Tools
from Bcfg2.Client.Tools.POSIX import *

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
from TestTools.Test_init import TestTool


def get_config(entries):
    config = lxml.etree.Element("Configuration")
    bundle = lxml.etree.SubElement(config, "Bundle", name="test")
    bundle.extend(entries)
    return config


class TestPOSIX(TestTool):
    test_obj = POSIX

    def test__init(self):
        entries = [lxml.etree.Element("Path", name="test", type="file")]
        posix = self.get_obj(config=get_config(entries))
        self.assertIsInstance(posix, Bcfg2.Client.Tools.Tool)
        self.assertIsInstance(posix, POSIX)
        self.assertIn('Path', posix.__req__)
        self.assertGreater(len(posix.__req__['Path']), 0)
        self.assertGreater(len(posix.__handles__), 0)
        self.assertItemsEqual(posix.handled, entries)

    @patch("Bcfg2.Client.Tools.Tool.canVerify")
    def test_canVerify(self, mock_canVerify):
        posix = self.get_obj()
        entry = lxml.etree.Element("Path", name="test", type="file")

        # first, test superclass canVerify failure
        mock_canVerify.return_value = False
        self.assertFalse(posix.canVerify(entry))
        mock_canVerify.assert_called_with(posix, entry)

        # next, test fully_specified failure
        mock_canVerify.reset_mock()
        mock_canVerify.return_value = True
        mock_fully_spec = Mock()
        mock_fully_spec.return_value = False
        posix._handlers[entry.get("type")].fully_specified = \
            mock_fully_spec
        self.assertFalse(posix.canVerify(entry))
        mock_canVerify.assert_called_with(posix, entry)
        mock_fully_spec.assert_called_with(entry)

        # finally, test success
        mock_canVerify.reset_mock()
        mock_fully_spec.reset_mock()
        mock_fully_spec.return_value = True
        self.assertTrue(posix.canVerify(entry))
        mock_canVerify.assert_called_with(posix, entry)
        mock_fully_spec.assert_called_with(entry)

    @patch("Bcfg2.Client.Tools.Tool.canInstall")
    def test_canInstall(self, mock_canInstall):
        posix = self.get_obj()
        entry = lxml.etree.Element("Path", name="test", type="file")

        # first, test superclass canInstall failure
        mock_canInstall.return_value = False
        self.assertFalse(posix.canInstall(entry))
        mock_canInstall.assert_called_with(posix, entry)

        # next, test fully_specified failure
        mock_canInstall.reset_mock()
        mock_canInstall.return_value = True
        mock_fully_spec = Mock()
        mock_fully_spec.return_value = False
        posix._handlers[entry.get("type")].fully_specified = \
            mock_fully_spec
        self.assertFalse(posix.canInstall(entry))
        mock_canInstall.assert_called_with(posix, entry)
        mock_fully_spec.assert_called_with(entry)

        # finally, test success
        mock_canInstall.reset_mock()
        mock_fully_spec.reset_mock()
        mock_fully_spec.return_value = True
        self.assertTrue(posix.canInstall(entry))
        mock_canInstall.assert_called_with(posix, entry)
        mock_fully_spec.assert_called_with(entry)

    def test_InstallPath(self):
        posix = self.get_obj()
        entry = lxml.etree.Element("Path", name="test", type="file")

        mock_install = Mock()
        mock_install.return_value = True
        posix._handlers[entry.get("type")].install = mock_install
        self.assertTrue(posix.InstallPath(entry))
        mock_install.assert_called_with(entry)

    def test_VerifyPath(self):
        posix = self.get_obj()
        entry = lxml.etree.Element("Path", name="test", type="file")
        modlist = []

        mock_verify = Mock()
        mock_verify.return_value = True
        posix._handlers[entry.get("type")].verify = mock_verify
        self.assertTrue(posix.VerifyPath(entry, modlist))
        mock_verify.assert_called_with(entry, modlist)

        mock_verify.reset_mock()
        mock_verify.return_value = False
        Bcfg2.Options.setup.interactive = True
        self.assertFalse(posix.VerifyPath(entry, modlist))
        self.assertIsNotNone(entry.get('qtext'))

    @patch('os.remove')
    def test_prune_old_backups(self, mock_remove):
        entry = lxml.etree.Element("Path", name="/etc/foo", type="file")
        Bcfg2.Options.setup.paranoid_path = '/'
        Bcfg2.Options.setup.paranoid_copies = 5
        Bcfg2.Options.setup.paranoid = True
        posix = self.get_obj()

        remove = ["_etc_foo_2012-07-20T04:13:22.364989",
                  "_etc_foo_2012-07-31T04:13:23.894958",
                  "_etc_foo_2012-07-17T04:13:22.493316",]
        keep = ["_etc_foo_bar_2011-08-07T04:13:22.519978",
                "_etc_foo_2012-08-04T04:13:22.519978",
                "_etc_Foo_2011-08-07T04:13:22.519978",
                "_etc_foo_2012-08-06T04:13:22.519978",
                "_etc_foo_2012-08-03T04:13:22.191895",
                "_etc_test_2011-08-07T04:13:22.519978",
                "_etc_foo_2012-08-07T04:13:22.519978",]

        @patch('os.listdir')
        def inner(mock_listdir):
            mock_listdir.side_effect = OSError
            posix._prune_old_backups(entry)
            self.assertFalse(mock_remove.called)
            mock_listdir.assert_called_with(Bcfg2.Options.setup.paranoid_path)

            mock_listdir.reset_mock()
            mock_remove.reset_mock()
            mock_listdir.side_effect = None
            mock_listdir.return_value = keep + remove

            posix._prune_old_backups(entry)
            mock_listdir.assert_called_with(Bcfg2.Options.setup.paranoid_path)
            self.assertItemsEqual(mock_remove.call_args_list,
                                  [call(os.path.join(Bcfg2.Options.setup.paranoid_path,
                                                     p))
                                   for p in remove])

            mock_listdir.reset_mock()
            mock_remove.reset_mock()
            mock_remove.side_effect = OSError
            # test to ensure that we call os.remove() for all files that
            # need to be removed even if we get an error
            posix._prune_old_backups(entry)
            mock_listdir.assert_called_with(Bcfg2.Options.setup.paranoid_path)
            self.assertItemsEqual(mock_remove.call_args_list,
                                  [call(os.path.join(Bcfg2.Options.setup.paranoid_path,
                                                     p))
                                   for p in remove])

        inner()

    @patch("shutil.copy")
    @patch("os.path.isdir")
    def test_paranoid_backup(self, mock_isdir, mock_copy):
        entry = lxml.etree.Element("Path", name="/etc/foo", type="file")
        Bcfg2.Options.setup.paranoid_path = '/'
        Bcfg2.Options.setup.paranoid_copies = 5
        Bcfg2.Options.setup.paranoid = False
        posix = self.get_obj()
        posix._prune_old_backups = Mock()

        # paranoid false globally
        posix._paranoid_backup(entry)
        self.assertFalse(posix._prune_old_backups.called)
        self.assertFalse(mock_copy.called)

        # paranoid false on the entry
        Bcfg2.Options.setup.paranoid = True

        def reset():
            mock_isdir.reset_mock()
            mock_copy.reset_mock()
            posix._prune_old_backups.reset_mock()

        reset()
        posix._paranoid_backup(entry)
        self.assertFalse(posix._prune_old_backups.called)
        self.assertFalse(mock_copy.called)

        # entry does not exist on filesystem
        reset()
        entry.set("paranoid", "true")
        entry.set("current_exists", "false")
        posix._paranoid_backup(entry)
        self.assertFalse(posix._prune_old_backups.called)
        self.assertFalse(mock_copy.called)

        # entry is a directory on the filesystem
        reset()
        entry.set("current_exists", "true")
        mock_isdir.return_value = True
        posix._paranoid_backup(entry)
        self.assertFalse(posix._prune_old_backups.called)
        self.assertFalse(mock_copy.called)
        mock_isdir.assert_called_with(entry.get("name"))

        # test the actual backup now
        reset()
        mock_isdir.return_value = False
        posix._paranoid_backup(entry)
        mock_isdir.assert_called_with(entry.get("name"))
        posix._prune_old_backups.assert_called_with(entry)
        # it's basically impossible to test the shutil.copy() call
        # exactly because the destination includes microseconds, so we
        # just test it good enough
        self.assertEqual(mock_copy.call_args[0][0],
                         entry.get("name"))
        bkupnam = os.path.join(Bcfg2.Options.setup.paranoid_path,
                               entry.get('name').replace('/', '_')) + '_'
        self.assertEqual(bkupnam, mock_copy.call_args[0][1][:len(bkupnam)])
