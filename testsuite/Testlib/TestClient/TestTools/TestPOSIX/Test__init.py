import os
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
import Bcfg2.Client.Tools
import Bcfg2.Client.Tools.POSIX

def call(*args, **kwargs):
    """ the Mock call object is a fairly recent addition, but it's
    very very useful, so we create our own function to create Mock
    calls """
    return (args, kwargs)

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
    

class TestPOSIX(unittest.TestCase):
    def test__init(self):
        entries = [lxml.etree.Element("Path", name="test", type="file")]
        p = get_posix_object(config=get_config(entries))
        self.assertIsInstance(p, Bcfg2.Client.Tools.Tool)
        self.assertIsInstance(p, Bcfg2.Client.Tools.POSIX.POSIX)
        self.assertIn('Path', p.__req__)
        self.assertGreater(len(p.__req__['Path']), 0)
        self.assertGreater(len(p.__handles__), 0)
        self.assertItemsEqual(p.handled, entries)
    
    @patch("Bcfg2.Client.Tools.Tool.canVerify")
    def test_canVerify(self, mock_canVerify):
        entry = lxml.etree.Element("Path", name="test", type="file")
        p = get_posix_object()

        # first, test superclass canVerify failure
        mock_canVerify.return_value = False
        self.assertFalse(p.canVerify(entry))
        mock_canVerify.assert_called_with(p, entry)
        
        # next, test fully_specified failure
        p.logger.error.reset_mock()
        mock_canVerify.reset_mock()
        mock_canVerify.return_value = True
        mock_fully_spec = Mock()
        mock_fully_spec.return_value = False
        p._handlers[entry.get("type")].fully_specified = mock_fully_spec
        self.assertFalse(p.canVerify(entry))
        mock_canVerify.assert_called_with(p, entry)
        mock_fully_spec.assert_called_with(entry)
        self.assertTrue(p.logger.error.called)
        
        # finally, test success
        p.logger.error.reset_mock()
        mock_canVerify.reset_mock()
        mock_fully_spec.reset_mock()
        mock_fully_spec.return_value = True
        self.assertTrue(p.canVerify(entry))
        mock_canVerify.assert_called_with(p, entry)
        mock_fully_spec.assert_called_with(entry)
        self.assertFalse(p.logger.error.called)

    @patch("Bcfg2.Client.Tools.Tool.canInstall")
    def test_canInstall(self, mock_canInstall):
        entry = lxml.etree.Element("Path", name="test", type="file")
        p = get_posix_object()

        # first, test superclass canInstall failure
        mock_canInstall.return_value = False
        self.assertFalse(p.canInstall(entry))
        mock_canInstall.assert_called_with(p, entry)
        
        # next, test fully_specified failure
        p.logger.error.reset_mock()
        mock_canInstall.reset_mock()
        mock_canInstall.return_value = True
        mock_fully_spec = Mock()
        mock_fully_spec.return_value = False
        p._handlers[entry.get("type")].fully_specified = mock_fully_spec
        self.assertFalse(p.canInstall(entry))
        mock_canInstall.assert_called_with(p, entry)
        mock_fully_spec.assert_called_with(entry)
        self.assertTrue(p.logger.error.called)
        
        # finally, test success
        p.logger.error.reset_mock()
        mock_canInstall.reset_mock()
        mock_fully_spec.reset_mock()
        mock_fully_spec.return_value = True
        self.assertTrue(p.canInstall(entry))
        mock_canInstall.assert_called_with(p, entry)
        mock_fully_spec.assert_called_with(entry)
        self.assertFalse(p.logger.error.called)

    def test_InstallPath(self):
        entry = lxml.etree.Element("Path", name="test", type="file")
        p = get_posix_object()

        mock_install = Mock()
        mock_install.return_value = True
        p._handlers[entry.get("type")].install = mock_install
        self.assertTrue(p.InstallPath(entry))
        mock_install.assert_called_with(entry)

    def test_VerifyPath(self):
        entry = lxml.etree.Element("Path", name="test", type="file")
        modlist = []
        p = get_posix_object()

        mock_verify = Mock()
        mock_verify.return_value = True
        p._handlers[entry.get("type")].verify = mock_verify
        self.assertTrue(p.VerifyPath(entry, modlist))
        mock_verify.assert_called_with(entry, modlist)

        mock_verify.reset_mock()
        mock_verify.return_value = False
        p.setup.__getitem__.return_value = True
        self.assertFalse(p.VerifyPath(entry, modlist))
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

        with patch('os.listdir') as mock_listdir:
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

    @patch("shutil.copy")
    @patch("Bcfg2.Client.Tools.POSIX.POSIX._prune_old_backups")
    def test_paranoid_backup(self, mock_prune, mock_copy):
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

        with patch("os.path.isdir") as mock_isdir:
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
            # exactly because the destination includes microseconds,
            # so we just test it good enough
            self.assertEqual(mock_copy.call_args[0][0],
                             entry.get("name"))
            bkupnam = os.path.join(setup['ppath'],
                                   entry.get('name').replace('/', '_')) + '_'
            self.assertEqual(bkupnam,
                             mock_copy.call_args[0][1][:len(bkupnam)])
