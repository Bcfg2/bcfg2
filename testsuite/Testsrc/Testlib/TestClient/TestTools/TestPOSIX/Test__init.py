import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
import Bcfg2.Client.Tools
import Bcfg2.Client.Tools.POSIX

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

def get_config(entries):
    config = lxml.etree.Element("Configuration")
    bundle = lxml.etree.SubElement(config, "Bundle", name="test")
    bundle.extend(entries)
    return config

def get_posix_object(logger=None, setup=None, config=None):
    if config is None:
        config = lxml.etree.Element("Configuration")
    if not logger:
        def print_msg(msg):
            print(msg)
        logger = Mock()
        logger.error = Mock(side_effect=print_msg)
        logger.warning = Mock(side_effect=print_msg)
        logger.info = Mock(side_effect=print_msg)
        logger.debug = Mock(side_effect=print_msg)
    if not setup:
        setup = MagicMock()
    return Bcfg2.Client.Tools.POSIX.POSIX(logger, setup, config)
    

class TestPOSIX(Bcfg2TestCase):
    def setUp(self):
        self.posix = get_posix_object()

    def tearDown(self):
        # just to guarantee that we start fresh each time
        self.posix = None

    def test__init(self):
        entries = [lxml.etree.Element("Path", name="test", type="file")]
        posix = get_posix_object(config=get_config(entries))
        self.assertIsInstance(posix, Bcfg2.Client.Tools.Tool)
        self.assertIsInstance(posix, Bcfg2.Client.Tools.POSIX.POSIX)
        self.assertIn('Path', posix.__req__)
        self.assertGreater(len(posix.__req__['Path']), 0)
        self.assertGreater(len(posix.__handles__), 0)
        self.assertItemsEqual(posix.handled, entries)
    
    @patch("Bcfg2.Client.Tools.Tool.canVerify")
    def test_canVerify(self, mock_canVerify):
        entry = lxml.etree.Element("Path", name="test", type="file")

        # first, test superclass canVerify failure
        mock_canVerify.return_value = False
        self.assertFalse(self.posix.canVerify(entry))
        mock_canVerify.assert_called_with(self.posix, entry)
        
        # next, test fully_specified failure
        self.posix.logger.error.reset_mock()
        mock_canVerify.reset_mock()
        mock_canVerify.return_value = True
        mock_fully_spec = Mock()
        mock_fully_spec.return_value = False
        self.posix._handlers[entry.get("type")].fully_specified = \
            mock_fully_spec
        self.assertFalse(self.posix.canVerify(entry))
        mock_canVerify.assert_called_with(self.posix, entry)
        mock_fully_spec.assert_called_with(entry)
        self.assertTrue(self.posix.logger.error.called)
        
        # finally, test success
        self.posix.logger.error.reset_mock()
        mock_canVerify.reset_mock()
        mock_fully_spec.reset_mock()
        mock_fully_spec.return_value = True
        self.assertTrue(self.posix.canVerify(entry))
        mock_canVerify.assert_called_with(self.posix, entry)
        mock_fully_spec.assert_called_with(entry)
        self.assertFalse(self.posix.logger.error.called)

    @patch("Bcfg2.Client.Tools.Tool.canInstall")
    def test_canInstall(self, mock_canInstall):
        entry = lxml.etree.Element("Path", name="test", type="file")

        # first, test superclass canInstall failure
        mock_canInstall.return_value = False
        self.assertFalse(self.posix.canInstall(entry))
        mock_canInstall.assert_called_with(self.posix, entry)
        
        # next, test fully_specified failure
        self.posix.logger.error.reset_mock()
        mock_canInstall.reset_mock()
        mock_canInstall.return_value = True
        mock_fully_spec = Mock()
        mock_fully_spec.return_value = False
        self.posix._handlers[entry.get("type")].fully_specified = \
            mock_fully_spec
        self.assertFalse(self.posix.canInstall(entry))
        mock_canInstall.assert_called_with(self.posix, entry)
        mock_fully_spec.assert_called_with(entry)
        self.assertTrue(self.posix.logger.error.called)
        
        # finally, test success
        self.posix.logger.error.reset_mock()
        mock_canInstall.reset_mock()
        mock_fully_spec.reset_mock()
        mock_fully_spec.return_value = True
        self.assertTrue(self.posix.canInstall(entry))
        mock_canInstall.assert_called_with(self.posix, entry)
        mock_fully_spec.assert_called_with(entry)
        self.assertFalse(self.posix.logger.error.called)

    def test_InstallPath(self):
        entry = lxml.etree.Element("Path", name="test", type="file")

        mock_install = Mock()
        mock_install.return_value = True
        self.posix._handlers[entry.get("type")].install = mock_install
        self.assertTrue(self.posix.InstallPath(entry))
        mock_install.assert_called_with(entry)

    def test_VerifyPath(self):
        entry = lxml.etree.Element("Path", name="test", type="file")
        modlist = []

        mock_verify = Mock()
        mock_verify.return_value = True
        self.posix._handlers[entry.get("type")].verify = mock_verify
        self.assertTrue(self.posix.VerifyPath(entry, modlist))
        mock_verify.assert_called_with(entry, modlist)

        mock_verify.reset_mock()
        mock_verify.return_value = False
        self.posix.setup.__getitem__.return_value = True
        self.assertFalse(self.posix.VerifyPath(entry, modlist))
        self.assertIsNotNone(entry.get('qtext'))

    @patch('os.remove')
    def test_prune_old_backups(self, mock_remove):
        entry = lxml.etree.Element("Path", name="/etc/foo", type="file")
        setup = dict(ppath='/', max_copies=5, paranoid=True)
        posix = get_posix_object(setup=setup)

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
            self.assertTrue(posix.logger.error.called)
            self.assertFalse(mock_remove.called)
            mock_listdir.assert_called_with(setup['ppath'])

            mock_listdir.reset_mock()
            mock_remove.reset_mock()
            mock_listdir.side_effect = None
            mock_listdir.return_value = keep + remove

            posix._prune_old_backups(entry)
            mock_listdir.assert_called_with(setup['ppath'])
            self.assertItemsEqual(mock_remove.call_args_list, 
                                  [call(os.path.join(setup['ppath'], p))
                                   for p in remove])

            mock_listdir.reset_mock()
            mock_remove.reset_mock()
            mock_remove.side_effect = OSError
            posix.logger.error.reset_mock()
            # test to ensure that we call os.remove() for all files that
            # need to be removed even if we get an error
            posix._prune_old_backups(entry)
            mock_listdir.assert_called_with(setup['ppath'])
            self.assertItemsEqual(mock_remove.call_args_list, 
                                  [call(os.path.join(setup['ppath'], p))
                                   for p in remove])
            self.assertTrue(posix.logger.error.called)

        inner()

    @patch("shutil.copy")
    @patch("os.path.isdir")
    @patch("Bcfg2.Client.Tools.POSIX.POSIX._prune_old_backups")
    def test_paranoid_backup(self, mock_prune, mock_isdir, mock_copy):
        entry = lxml.etree.Element("Path", name="/etc/foo", type="file")
        setup = dict(ppath='/', max_copies=5, paranoid=False)
        posix = get_posix_object(setup=setup)
        
        # paranoid false globally
        posix._paranoid_backup(entry)
        self.assertFalse(mock_prune.called)
        self.assertFalse(mock_copy.called)

        # paranoid false on the entry
        mock_prune.reset_mock()
        setup['paranoid'] = True
        posix = get_posix_object(setup=setup)
        posix._paranoid_backup(entry)
        self.assertFalse(mock_prune.called)
        self.assertFalse(mock_copy.called)

        # entry does not exist on filesystem
        mock_prune.reset_mock()
        entry.set("paranoid", "true")
        entry.set("current_exists", "false")
        posix._paranoid_backup(entry)
        self.assertFalse(mock_prune.called)
        self.assertFalse(mock_copy.called)

        # entry is a directory on the filesystem
        mock_prune.reset_mock()
        entry.set("current_exists", "true")
        mock_isdir.return_value = True
        posix._paranoid_backup(entry)
        self.assertFalse(mock_prune.called)
        self.assertFalse(mock_copy.called)
        mock_isdir.assert_called_with(entry.get("name"))

        # test the actual backup now
        mock_prune.reset_mock()
        mock_isdir.return_value = False
        posix._paranoid_backup(entry)
        mock_isdir.assert_called_with(entry.get("name"))
        mock_prune.assert_called_with(entry)
        # it's basically impossible to test the shutil.copy() call
        # exactly because the destination includes microseconds, so we
        # just test it good enough
        self.assertEqual(mock_copy.call_args[0][0],
                         entry.get("name"))
        bkupnam = os.path.join(setup['ppath'],
                               entry.get('name').replace('/', '_')) + '_'
        self.assertEqual(bkupnam, mock_copy.call_args[0][1][:len(bkupnam)])
