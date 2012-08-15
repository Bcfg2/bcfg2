import os
import copy
import binascii
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.File import *
from Test__init import get_posix_object

def call(*args, **kwargs):
    """ the Mock call object is a fairly recent addition, but it's
    very very useful, so we create our own function to create Mock
    calls """
    return (args, kwargs)

def get_file_object(posix=None):
    if posix is None:
        posix = get_posix_object()
    return POSIXFile(posix.logger, posix.setup, posix.config)

class TestPOSIXFile(unittest.TestCase):
    def test_fully_specified(self):
        entry = lxml.etree.Element("Path", name="/test", type="file")
        ptool = get_file_object()
        self.assertFalse(ptool.fully_specified(entry))

        entry.set("empty", "true")
        self.assertTrue(ptool.fully_specified(entry))

        entry.set("empty", "false")
        entry.text = "text"
        self.assertTrue(ptool.fully_specified(entry))
    
    def test_is_string(self):
        ptool = get_file_object()
        for char in range(8) + range(14, 32):
            self.assertFalse(ptool._is_string("foo" + chr(char) + "bar",
                                              'utf_8'))
        for char in range(9, 14) + range(33, 128):
            self.assertTrue(ptool._is_string("foo" + chr(char) + "bar",
                                             'utf_8'))
        self.assertFalse(ptool._is_string("foo" + chr(128) + "bar",
                                          'ascii'))
        ustr = '\xef\xa3\x91 + \xef\xa3\x92'
        self.assertTrue(ptool._is_string(ustr, 'utf_8'))
        self.assertFalse(ptool._is_string(ustr, 'ascii'))

    def test_get_data(self):
        orig_entry = lxml.etree.Element("Path", name="/test", type="file")
        setup = dict(encoding="ascii", ppath='/', max_copies=5)
        ptool = get_file_object(posix=get_posix_object(setup=setup))

        entry = copy.deepcopy(orig_entry)
        entry.text = binascii.b2a_base64("test")
        entry.set("encoding", "base64")
        self.assertEqual(ptool._get_data(entry), ("test", True))

        entry = copy.deepcopy(orig_entry)
        entry.set("empty", "true")
        self.assertEqual(ptool._get_data(entry), ("", False))

        entry = copy.deepcopy(orig_entry)
        entry.text = "test"
        self.assertEqual(ptool._get_data(entry), ("test", False))

        ustr = u'\uf8d1 + \uf8d2'
        entry = copy.deepcopy(orig_entry)
        entry.text = ustr
        self.assertEqual(ptool._get_data(entry), (ustr, False))

        setup['encoding'] = "utf_8"
        ptool = get_file_object(posix=get_posix_object(setup=setup))
        entry = copy.deepcopy(orig_entry)
        entry.text = ustr
        self.assertEqual(ptool._get_data(entry),
                         ('\xef\xa3\x91 + \xef\xa3\x92', False))

    @patch("__builtin__.open")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    @patch("Bcfg2.Client.Tools.POSIX.File.POSIXFile._exists")
    @patch("Bcfg2.Client.Tools.POSIX.File.POSIXFile._get_data")
    @patch("Bcfg2.Client.Tools.POSIX.File.POSIXFile._get_diffs")
    def test_verify(self, mock_get_diffs, mock_get_data, mock_exists,
                    mock_verify, mock_open):
        entry = lxml.etree.Element("Path", name="/test", type="file")
        setup = dict(interactive=False, ppath='/', max_copies=5)
        ptool = get_file_object(posix=get_posix_object(setup=setup))

        def reset():
            mock_get_diffs.reset_mock()
            mock_get_data.reset_mock()
            mock_exists.reset_mock()
            mock_verify.reset_mock()
            mock_open.reset_mock()

        mock_get_data.return_value = ("test", False)
        mock_exists.return_value = False
        mock_verify.return_value = True
        self.assertFalse(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])
        mock_get_diffs.assert_called_with(entry, interactive=False,
                                          sensitive=False,
                                          is_binary=False,
                                          content="")

        reset()
        exists_rv = MagicMock()
        exists_rv.__getitem__.return_value = 5
        mock_exists.return_value = exists_rv
        mock_get_data.return_value = ("test", True)
        self.assertFalse(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])
        mock_get_diffs.assert_called_with(entry, interactive=False,
                                          sensitive=False,
                                          is_binary=True,
                                          content=None)
        
        reset()
        mock_get_data.return_value = ("test", False)
        exists_rv.__getitem__.return_value = 4
        entry.set("sensitive", "true")
        open_rv = Mock()
        open_rv.read.return_value = "tart"
        mock_open.return_value = open_rv
        self.assertFalse(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])
        mock_open.assert_called_with(entry.get("name"))
        open_rv.assert_any_call()
        mock_get_diffs.assert_called_with(entry, interactive=False,
                                          sensitive=True,
                                          is_binary=False,
                                          content="tart")

        reset()
        open_rv.read.return_value = "test"
        mock_open.return_value = open_rv
        self.assertTrue(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])
        mock_open.assert_called_with(entry.get("name"))
        open_rv.assert_any_call()
        self.assertFalse(mock_get_diffs.called)

        reset()
        mock_open.side_effect = IOError
        self.assertFalse(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)
        mock_open.assert_called_with(entry.get("name"))
    
    @patch("os.fdopen")
    @patch("tempfile.mkstemp")
    @patch("Bcfg2.Client.Tools.POSIX.File.POSIXFile._get_data")
    def test_write_tmpfile(self, mock_get_data, mock_mkstemp, mock_fdopen):
        entry = lxml.etree.Element("Path", name="/test", type="file",
                                   perms='0644', owner='root', group='root')
        ptool = get_file_object()
        newfile = "/foo/bar"

        def reset():
            mock_get_data.reset_mock()
            mock_mkstemp.reset_mock()
            mock_fdopen.reset_mock()

        mock_get_data.return_value = ("test", False)
        mock_mkstemp.return_value = (5, newfile)
        self.assertEqual(ptool._write_tmpfile(entry), newfile)
        mock_get_data.assert_called_with(entry)
        mock_mkstemp.assert_called_with(prefix='test', dir='/')
        mock_fdopen.assert_called_with(5, 'w')
        mock_fdopen.return_value.write.assert_called_with("test")

        reset()
        mock_mkstemp.side_effect = OSError
        self.assertFalse(ptool._write_tmpfile(entry))
        mock_mkstemp.assert_called_with(prefix='test', dir='/')

        reset()
        mock_mkstemp.side_effect = None
        mock_fdopen.side_effect = OSError
        self.assertFalse(ptool._write_tmpfile(entry))
        mock_mkstemp.assert_called_with(prefix='test', dir='/')
        mock_get_data.assert_called_with(entry)
        mock_fdopen.assert_called_with(5, 'w')
        
    @patch("os.rename")
    @patch("os.unlink")
    def test_rename_tmpfile(self, mock_unlink, mock_rename):
        entry = lxml.etree.Element("Path", name="/test", type="file",
                                   perms='0644', owner='root', group='root')
        ptool = get_file_object()
        newfile = "/foo/bar"

        self.assertTrue(ptool._rename_tmpfile(newfile, entry))
        mock_rename.assert_called_with(newfile, entry.get("name"))
        
        mock_rename.reset_mock()
        mock_unlink.reset_mock()
        mock_rename.side_effect = OSError
        self.assertFalse(ptool._rename_tmpfile(newfile, entry))
        mock_rename.assert_called_with(newfile, entry.get("name"))
        mock_unlink.assert_called_with(newfile)

        # even if the unlink fails, return false gracefully
        mock_rename.reset_mock()
        mock_unlink.reset_mock()
        mock_unlink.side_effect = OSError
        self.assertFalse(ptool._rename_tmpfile(newfile, entry))
        mock_rename.assert_called_with(newfile, entry.get("name"))
        mock_unlink.assert_called_with(newfile)

    @patch("os.path.exists")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    @patch("Bcfg2.Client.Tools.POSIX.File.POSIXFile._makedirs")
    @patch("Bcfg2.Client.Tools.POSIX.File.POSIXFile._set_perms")
    @patch("Bcfg2.Client.Tools.POSIX.File.POSIXFile._write_tmpfile")
    @patch("Bcfg2.Client.Tools.POSIX.File.POSIXFile._rename_tmpfile")
    def test_install(self, mock_rename, mock_write, mock_set_perms,
                     mock_makedirs, mock_install, mock_exists):
        entry = lxml.etree.Element("Path", name="/test", type="file",
                                   perms='0644', owner='root', group='root')
        ptool = get_file_object()

        def reset():
            mock_rename.reset_mock()
            mock_write.reset_mock()
            mock_set_perms.reset_mock()
            mock_makedirs.reset_mock()
            mock_install.reset_mock()
            mock_exists.reset_mock()

        mock_exists.return_value = False
        mock_makedirs.return_value = False
        self.assertFalse(ptool.install(entry))
        mock_exists.assert_called_with("/")
        mock_makedirs.assert_called_with(entry, path="/")
        
        reset()
        mock_makedirs.return_value = True
        mock_write.return_value = False
        self.assertFalse(ptool.install(entry))
        mock_exists.assert_called_with("/")
        mock_makedirs.assert_called_with(entry, path="/")
        mock_write.assert_called_with(entry)

        reset()
        newfile = '/test.X987yS'
        mock_write.return_value = newfile
        mock_set_perms.return_value = False
        mock_rename.return_value = False
        self.assertFalse(ptool.install(entry))
        mock_exists.assert_called_with("/")
        mock_makedirs.assert_called_with(entry, path="/")
        mock_write.assert_called_with(entry)
        mock_set_perms.assert_called_with(entry, path=newfile)
        mock_rename.assert_called_with(newfile, entry)

        reset()
        mock_rename.return_value = True
        mock_install.return_value = False
        self.assertFalse(ptool.install(entry))
        mock_exists.assert_called_with("/")
        mock_makedirs.assert_called_with(entry, path="/")
        mock_write.assert_called_with(entry)
        mock_set_perms.assert_called_with(entry, path=newfile)
        mock_rename.assert_called_with(newfile, entry)
        mock_install.assert_called_with(ptool, entry)

        reset()
        mock_install.return_value = True
        self.assertFalse(ptool.install(entry))
        mock_exists.assert_called_with("/")
        mock_makedirs.assert_called_with(entry, path="/")
        mock_write.assert_called_with(entry)
        mock_set_perms.assert_called_with(entry, path=newfile)
        mock_rename.assert_called_with(newfile, entry)
        mock_install.assert_called_with(ptool, entry)

        reset()
        mock_set_perms.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_exists.assert_called_with("/")
        mock_makedirs.assert_called_with(entry, path="/")
        mock_write.assert_called_with(entry)
        mock_set_perms.assert_called_with(entry, path=newfile)
        mock_rename.assert_called_with(newfile, entry)
        mock_install.assert_called_with(ptool, entry)

        reset()
        mock_exists.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_exists.assert_called_with("/")
        self.assertFalse(mock_makedirs.called)
        mock_write.assert_called_with(entry)
        mock_set_perms.assert_called_with(entry, path=newfile)
        mock_rename.assert_called_with(newfile, entry)
        mock_install.assert_called_with(ptool, entry)

    def test_diff(self):
        ptool = get_file_object()
        content1 = "line1\nline2"
        content2 = "line3"
        rv = ["line1", "line2", "line3"]
        func = Mock()
        func.return_value = rv
        self.assertItemsEqual(ptool._diff(content1, content2, func), rv)
        func.assert_called_with(["line1", "line2"], ["line3"])

        func.reset_mock()
        def slow_diff(content1, content2):
            for i in range(1, 10):
                time.sleep(5)
                yield "line%s" % i
        func.side_effect = slow_diff
        self.assertFalse(ptool._diff(content1, content2, func), rv)
        func.assert_called_with(["line1", "line2"], ["line3"])
