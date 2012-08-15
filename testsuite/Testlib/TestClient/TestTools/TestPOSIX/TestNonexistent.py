import os
import copy
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Nonexistent import *
from Test__init import get_config, get_posix_object

def call(*args, **kwargs):
    """ the Mock call object is a fairly recent addition, but it's
    very very useful, so we create our own function to create Mock
    calls """
    return (args, kwargs)

def get_nonexistent_object(posix=None):
    if posix is None:
        posix = get_posix_object()
    return POSIXNonexistent(posix.logger, posix.setup, posix.config)

class TestPOSIXNonexistent(unittest.TestCase):
    @patch("os.path.lexists")
    def test_verify(self, mock_lexists):
        entry = lxml.etree.Element("Path", name="/test", type="nonexistent")
        ptool = get_nonexistent_object()

        for val in [True, False]:
            mock_lexists.reset_mock()
            mock_lexists.return_value = val
            self.assertEqual(ptool.verify(entry, []), not val)
            mock_lexists.assert_called_with(entry.get("name"))

    @patch("os.rmdir")
    @patch("os.remove")
    @patch("shutil.rmtree")
    def test_install(self, mock_rmtree, mock_remove, mock_rmdir):
        entry = lxml.etree.Element("Path", name="/test", type="nonexistent")
        ptool = get_nonexistent_object()

        with patch("os.path.isdir") as mock_isdir:
            def reset():
                mock_isdir.reset_mock()
                mock_remove.reset_mock()
                mock_rmdir.reset_mock()
                mock_rmtree.reset_mock()

            mock_isdir.return_value = False
            self.assertTrue(ptool.install(entry))
            mock_remove.assert_called_with(entry.get("name"))

            reset()
            mock_remove.side_effect = OSError
            self.assertFalse(ptool.install(entry))
            mock_remove.assert_called_with(entry.get("name"))

            reset()
            mock_isdir.return_value = True
            self.assertTrue(ptool.install(entry))
            mock_rmdir.assert_called_with(entry.get("name"))

            reset()
            mock_rmdir.side_effect = OSError
            self.assertFalse(ptool.install(entry))
            mock_rmdir.assert_called_with(entry.get("name"))
            
            reset()
            entry.set("recursive", "true")
            self.assertTrue(ptool.install(entry))
            mock_rmtree.assert_called_with(entry.get("name"))

            reset()
            mock_rmtree.side_effect = OSError
            self.assertFalse(ptool.install(entry))
            mock_rmtree.assert_called_with(entry.get("name"))
            
            reset()
            child_entry = lxml.etree.Element("Path", name="/test/foo",
                                             type="nonexistent")
            ptool = get_nonexistent_object(posix=get_posix_object(config=get_config([child_entry])))
            mock_rmtree.side_effect = None
            self.assertTrue(ptool.install(entry))
            mock_rmtree.assert_called_with(entry.get("name"))

            reset()
            child_entry = lxml.etree.Element("Path", name="/test/foo",
                                             type="file")
            ptool = get_nonexistent_object(posix=get_posix_object(config=get_config([child_entry])))
            mock_rmtree.side_effect = None
            self.assertFalse(ptool.install(entry))
