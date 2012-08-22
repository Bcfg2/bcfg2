import os
import copy
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Hardlink import *
from .Test__init import get_posix_object
from .Testbase import TestPOSIXTool
# python 2.5 can't import * from relative imports
from .....common import XI_NAMESPACE, XI, inPy3k, call, builtins, u, can_skip, \
    skip, skipIf, skipUnless, Bcfg2TestCase, DBModelTestCase, syncdb, \
    patchIf, datastore

class TestPOSIXHardlink(TestPOSIXTool):
    test_obj = POSIXHardlink

    @patch("os.path.samefile")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    def test_verify(self, mock_verify, mock_samefile):
        entry = lxml.etree.Element("Path", name="/test", type="hardlink",
                                   to="/dest")
        ptool = self.get_obj()

        mock_samefile.return_value = True
        mock_verify.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        mock_samefile.assert_called_with(entry.get("name"),
                                         entry.get("to"))
        mock_verify.assert_called_with(ptool, entry, [])

        mock_samefile.reset_mock()
        mock_verify.reset_mock()
        mock_verify.return_value = True
        self.assertTrue(ptool.verify(entry, []))
        mock_samefile.assert_called_with(entry.get("name"),
                                         entry.get("to"))
        mock_verify.assert_called_with(ptool, entry, [])

        mock_samefile.reset_mock()
        mock_verify.reset_mock()
        mock_samefile.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        mock_samefile.assert_called_with(entry.get("name"),
                                         entry.get("to"))
        mock_verify.assert_called_with(ptool, entry, [])
        
        mock_samefile.reset_mock()
        mock_verify.reset_mock()
        mock_samefile.side_effect = OSError
        self.assertFalse(ptool.verify(entry, []))
        mock_samefile.assert_called_with(entry.get("name"),
                                         entry.get("to"))

    @patch("os.link")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    @patch("Bcfg2.Client.Tools.POSIX.Hardlink.%s._exists" % test_obj.__name__)
    def test_install(self, mock_exists, mock_install, mock_link):
        entry = lxml.etree.Element("Path", name="/test", type="hardlink",
                                   to="/dest")
        ptool = self.get_obj()

        mock_exists.return_value = False
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_exists.assert_called_with(entry, remove=True)
        mock_link.assert_called_with(entry.get("to"), entry.get("name"))
        mock_install.assert_called_with(ptool, entry)

        mock_link.reset_mock()
        mock_exists.reset_mock()
        mock_install.reset_mock()
        mock_link.side_effect = OSError
        self.assertFalse(ptool.install(entry))
        mock_exists.assert_called_with(entry, remove=True)
        mock_link.assert_called_with(entry.get("to"), entry.get("name"))
        mock_install.assert_called_with(ptool, entry)
