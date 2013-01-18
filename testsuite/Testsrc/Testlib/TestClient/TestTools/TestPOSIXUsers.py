import os
import sys
import copy
import lxml.etree
import subprocess
from mock import Mock, MagicMock, patch
import Bcfg2.Client.Tools
from Bcfg2.Client.Tools.POSIXUsers import *

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


class TestIDRangeSet(Bcfg2TestCase):
    def test_ranges(self):
        # test cases.  tuples of (ranges, included numbers, excluded
        # numbers)
        # tuples of (range description, numbers that are included,
        # numebrs that are excluded)
        tests = [(["0-3"], ["0", 1, "2", 3], [4]),
                 (["1"], [1], [0, "2"]),
                 (["10-11"], [10, 11], [0, 1]),
                 (["9-9"], [9], [8, 10]),
                 (["0-100"], [0, 10, 99, 100], []),
                 (["1", "3", "5"], [1, 3, 5], [0, 2, 4, 6]),
                 (["1-5", "7"], [1, 3, 5, 7], [0, 6, 8]),
                 (["1-5", 7, "9-11"], [1, 3, 5, 7, 9, 11], [0, 6, 8, 12]),
                 (["852-855", "321-497", 763], [852, 855, 321, 400, 497, 763],
                  [851, 320, 766, 999]),
                 (["0-"], [0, 1, 100, 100000], []),
                 ([1, "5-10", "1000-"], [1, 5, 10, 1000, 10000000],
                  [4, 11, 999])]
        for ranges, inc, exc in tests:
            rng = IDRangeSet(*ranges)
            for test in inc:
                self.assertIn(test, rng)
            for test in exc:
                self.assertNotIn(test, rng)


class TestExecutor(Bcfg2TestCase):
    test_obj = Executor

    def get_obj(self, logger=None):
        if not logger:
            def print_msg(msg):
                print(msg)
            logger = Mock()
            logger.error = Mock(side_effect=print_msg)
            logger.warning = Mock(side_effect=print_msg)
            logger.info = Mock(side_effect=print_msg)
            logger.debug = Mock(side_effect=print_msg)
        return self.test_obj(logger)

    @patch("subprocess.Popen")
    def test_run(self, mock_Popen):
        exc = self.get_obj()
        cmd = ["/bin/test", "-a", "foo"]
        proc = Mock()
        proc.wait = Mock()
        proc.wait.return_value = 0
        proc.communicate = Mock()
        proc.communicate.return_value = (MagicMock(), MagicMock())
        mock_Popen.return_value = proc

        self.assertTrue(exc.run(cmd))
        args = mock_Popen.call_args
        self.assertEqual(args[0][0], cmd)
        self.assertEqual(args[1]['shell'], False)
        self.assertEqual(args[1]['stdin'], subprocess.PIPE)
        self.assertEqual(args[1]['stdout'], subprocess.PIPE)
        self.assertEqual(args[1]['stderr'], subprocess.PIPE)
        proc.communicate.assert_called_with()
        proc.wait.assert_called_with()
        self.assertEqual(proc.communicate.return_value,
                         (exc.stdout, exc.stderr))
        self.assertEqual(proc.wait.return_value,
                         exc.retval)

        mock_Popen.reset_mock()
        inputdata = "foo\n\nbar"
        self.assertTrue(exc.run(cmd, inputdata=inputdata, shell=True))
        args = mock_Popen.call_args
        self.assertEqual(args[0][0], cmd)
        self.assertEqual(args[1]['shell'], True)
        self.assertEqual(args[1]['stdin'], subprocess.PIPE)
        self.assertEqual(args[1]['stdout'], subprocess.PIPE)
        self.assertEqual(args[1]['stderr'], subprocess.PIPE)
        proc.communicate.assert_called_with(inputdata)
        proc.wait.assert_called_with()
        self.assertEqual(proc.communicate.return_value,
                         (exc.stdout, exc.stderr))
        self.assertEqual(proc.wait.return_value,
                         exc.retval)

        mock_Popen.reset_mock()
        proc.wait.return_value = 1
        self.assertRaises(ExecutionError, exc.run, cmd)
        args = mock_Popen.call_args
        self.assertEqual(args[0][0], cmd)
        self.assertEqual(args[1]['shell'], False)
        self.assertEqual(args[1]['stdin'], subprocess.PIPE)
        self.assertEqual(args[1]['stdout'], subprocess.PIPE)
        self.assertEqual(args[1]['stderr'], subprocess.PIPE)
        proc.communicate.assert_called_with()
        proc.wait.assert_called_with()
        self.assertEqual(proc.communicate.return_value,
                         (exc.stdout, exc.stderr))
        self.assertEqual(proc.wait.return_value,
                         exc.retval)


class TestPOSIXUsers(Bcfg2TestCase):
    test_obj = POSIXUsers

    def get_obj(self, logger=None, setup=None, config=None):
        if config is None:
            config = lxml.etree.Element("Configuration")

        if logger is None:
            def print_msg(msg):
                print(msg)
            logger = Mock()
            logger.error = Mock(side_effect=print_msg)
            logger.warning = Mock(side_effect=print_msg)
            logger.info = Mock(side_effect=print_msg)
            logger.debug = Mock(side_effect=print_msg)

        if setup is None:
            setup = MagicMock()
            setup.__getitem__.return_value = []
        return self.test_obj(logger, setup, config)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_existing(self, mock_getgrall, mock_getpwall):
        users = self.get_obj()
        mock_getgrall.return_value = MagicMock()
        mock_getpwall.return_value = MagicMock()

        def reset():
            mock_getgrall.reset_mock()
            mock_getpwall.reset_mock()

        # make sure we start clean
        self.assertIsNone(users._existing)
        self.assertIsInstance(users.existing, dict)
        self.assertIn("POSIXUser", users.existing)
        self.assertIn("POSIXGroup", users.existing)
        mock_getgrall.assert_called_with()
        mock_getpwall.assert_called_with()

        reset()
        self.assertIsInstance(users._existing, dict)
        self.assertIsInstance(users.existing, dict)
        self.assertEqual(users.existing, users._existing)
        self.assertIn("POSIXUser", users.existing)
        self.assertIn("POSIXGroup", users.existing)
        self.assertFalse(mock_getgrall.called)
        self.assertFalse(mock_getpwall.called)

        reset()
        users._existing = None
        self.assertIsInstance(users.existing, dict)
        self.assertIn("POSIXUser", users.existing)
        self.assertIn("POSIXGroup", users.existing)
        mock_getgrall.assert_called_with()
        mock_getpwall.assert_called_with()

    def test__in_managed_range(self):
        users = self.get_obj()
        users._whitelist = dict(POSIXGroup=IDRangeSet("1-10"))
        users._blacklist = dict(POSIXGroup=IDRangeSet("8-100"))
        self.assertTrue(users._in_managed_range("POSIXGroup", "9"))

        users._whitelist = dict(POSIXGroup=None)
        users._blacklist = dict(POSIXGroup=IDRangeSet("8-100"))
        self.assertFalse(users._in_managed_range("POSIXGroup", "9"))

        users._whitelist = dict(POSIXGroup=None)
        users._blacklist = dict(POSIXGroup=IDRangeSet("100-"))
        self.assertTrue(users._in_managed_range("POSIXGroup", "9"))

        users._whitelist = dict(POSIXGroup=IDRangeSet("1-10"))
        users._blacklist = dict(POSIXGroup=None)
        self.assertFalse(users._in_managed_range("POSIXGroup", "25"))

    @patch("Bcfg2.Client.Tools.Tool.canInstall")
    def test_canInstall(self, mock_canInstall):
        users = self.get_obj()
        users._in_managed_range = Mock()
        users._in_managed_range.return_value = False
        mock_canInstall.return_value = False

        def reset():
            users._in_managed_range.reset()
            mock_canInstall.reset()

        # test failure of inherited method
        entry = lxml.etree.Element("POSIXUser", name="test")
        self.assertFalse(users.canInstall(entry))
        mock_canInstall.assertCalledWith(users, entry)

        # test with no uid specified
        reset()
        mock_canInstall.return_value = True
        self.assertTrue(users.canInstall(entry))
        mock_canInstall.assertCalledWith(users, entry)

        # test with uid specified, not in managed range
        reset()
        entry.set("uid", "1000")
        self.assertFalse(users.canInstall(entry))
        mock_canInstall.assertCalledWith(users, entry)
        users._in_managed_range.assert_called_with(entry.tag, "1000")

        # test with uid specified, in managed range
        reset()
        users._in_managed_range.return_value = True
        self.assertTrue(users.canInstall(entry))
        mock_canInstall.assertCalledWith(users, entry)
        users._in_managed_range.assert_called_with(entry.tag, "1000")

    @patch("Bcfg2.Client.Tools.Tool.Inventory")
    def test_Inventory(self, mock_Inventory):
        config = lxml.etree.Element("Configuration")
        bundle = lxml.etree.SubElement(config, "Bundle", name="test")
        lxml.etree.SubElement(bundle, "POSIXUser", name="test", group="test")
        lxml.etree.SubElement(bundle, "POSIXUser", name="test2", group="test2")
        lxml.etree.SubElement(bundle, "POSIXGroup", name="test2")

        orig_bundle = copy.deepcopy(bundle)

        users = self.get_obj(config=config)
        users.set_defaults['POSIXUser'] = Mock()
        users.set_defaults['POSIXUser'].side_effect = lambda e: e

        states = dict()
        self.assertEqual(users.Inventory(states),
                         mock_Inventory.return_value)
        mock_Inventory.assert_called_with(users, states, config.getchildren())
        lxml.etree.SubElement(orig_bundle, "POSIXGroup", name="test")
        self.assertXMLEqual(orig_bundle, bundle)

    def test_FindExtra(self):
        users = self.get_obj()
        users._in_managed_range = Mock()
        users._in_managed_range.side_effect = lambda t, i: i < 100

        def getSupportedEntries():
            return [lxml.etree.Element("POSIXUser", name="test1"),
                    lxml.etree.Element("POSIXGroup", name="test1")]

        users.getSupportedEntries = Mock()
        users.getSupportedEntries.side_effect = getSupportedEntries

        users._existing = dict(POSIXUser=dict(test1=("test1", "x", 15),
                                              test2=("test2", "x", 25),
                                              test3=("test3", "x", 115)),
                               POSIXGroup=dict(test2=("test2", "x", 25)))
        extra = users.FindExtra()
        self.assertEqual(len(extra), 2)
        self.assertItemsEqual([e.tag for e in extra],
                              ["POSIXUser", "POSIXGroup"])
        self.assertItemsEqual([e.get("name") for e in extra],
                              ["test2", "test2"])
        self.assertItemsEqual(users._in_managed_range.call_args_list,
                              [call("POSIXUser", 25),
                               call("POSIXUser", 115),
                               call("POSIXGroup", 25)])

    def test_populate_user_entry(self):
        users = self.get_obj()
        users._existing = dict(POSIXUser=dict(),
                               POSIXGroup=dict(root=('root', 'x', 0, [])))

        cases = [(lxml.etree.Element("POSIXUser", name="test"),
                  lxml.etree.Element("POSIXUser", name="test", group="test",
                                     gecos="test", shell="/bin/bash",
                                     home="/home/test")),
                 (lxml.etree.Element("POSIXUser", name="root", gecos="Root",
                                     shell="/bin/zsh"),
                  lxml.etree.Element("POSIXUser", name="root", group='root',
                                     gid='0', gecos="Root", shell="/bin/zsh",
                                     home='/root')),
                 (lxml.etree.Element("POSIXUser", name="test2", gecos="",
                                     shell="/bin/zsh"),
                  lxml.etree.Element("POSIXUser", name="test2", group='test2',
                                     gecos="", shell="/bin/zsh",
                                     home='/home/test2'))]

        for initial, expected in cases:
            actual = users.populate_user_entry(initial)
            self.assertXMLEqual(actual, expected)

    def test_user_supplementary_groups(self):
        users = self.get_obj()
        users._existing = \
            dict(POSIXUser=dict(),
                 POSIXGroup=dict(root=('root', 'x', 0, []),
                                 wheel=('wheel', 'x', 10, ['test']),
                                 users=('users', 'x', 100, ['test'])))
        entry = lxml.etree.Element("POSIXUser", name="test")
        self.assertItemsEqual(users.user_supplementary_groups(entry),
                              [users.existing['POSIXGroup']['wheel'],
                               users.existing['POSIXGroup']['users']])
        entry.set('name', 'test2')
        self.assertItemsEqual(users.user_supplementary_groups(entry), [])

    def test_VerifyPOSIXUser(self):
        users = self.get_obj()
        users._verify = Mock()
        users._verify.return_value = True
        users.populate_user_entry = Mock()
        users.user_supplementary_groups = Mock()
        users.user_supplementary_groups.return_value = \
            [('wheel', 'x', 10, ['test']), ('users', 'x', 100, ['test'])]

        def reset():
            users._verify.reset_mock()
            users.populate_user_entry.reset_mock()
            users.user_supplementary_groups.reset_mock()

        entry = lxml.etree.Element("POSIXUser", name="test")
        self.assertFalse(users.VerifyPOSIXUser(entry, []))
        users.populate_user_entry.assert_called_with(entry)
        users._verify.assert_called_with(users.populate_user_entry.return_value)
        users.user_supplementary_groups.assert_called_with(entry)

        reset()
        m1 = lxml.etree.SubElement(entry, "MemberOf")
        m1.text = "wheel"
        m2 = lxml.etree.SubElement(entry, "MemberOf")
        m2.text = "users"
        self.assertTrue(users.VerifyPOSIXUser(entry, []))
        users.populate_user_entry.assert_called_with(entry)
        users._verify.assert_called_with(users.populate_user_entry.return_value)
        users.user_supplementary_groups.assert_called_with(entry)

        reset()
        m3 = lxml.etree.SubElement(entry, "MemberOf")
        m3.text = "extra"
        self.assertFalse(users.VerifyPOSIXUser(entry, []))
        users.populate_user_entry.assert_called_with(entry)
        users._verify.assert_called_with(users.populate_user_entry.return_value)
        users.user_supplementary_groups.assert_called_with(entry)

        reset()
        def _verify(entry):
            entry.set("current_exists", "false")
            return False

        users._verify.side_effect = _verify
        self.assertFalse(users.VerifyPOSIXUser(entry, []))
        users.populate_user_entry.assert_called_with(entry)
        users._verify.assert_called_with(users.populate_user_entry.return_value)

    def test_VerifyPOSIXGroup(self):
        users = self.get_obj()
        users._verify = Mock()
        entry = lxml.etree.Element("POSIXGroup", name="test")
        self.assertEqual(users._verify.return_value,
                         users.VerifyPOSIXGroup(entry, []))

    def test__verify(self):
        users = self.get_obj()
        users._existing = \
            dict(POSIXUser=dict(test=('test', 'x', 1000, 1000, 'Test McTest',
                                      '/home/test', '/bin/zsh')),
                 POSIXGroup=dict(test=('test', 'x', 1000, [])))

        entry = lxml.etree.Element("POSIXUser", name="nonexistent")
        self.assertFalse(users._verify(entry))
        self.assertEqual(entry.get("current_exists"), "false")

        entry = lxml.etree.Element("POSIXUser", name="test", group="test",
                                   gecos="Bogus", shell="/bin/bash",
                                   home="/home/test")
        self.assertFalse(users._verify(entry))

        entry = lxml.etree.Element("POSIXUser", name="test", group="test",
                                   gecos="Test McTest", shell="/bin/zsh",
                                   home="/home/test")
        self.assertTrue(users._verify(entry))

        entry = lxml.etree.Element("POSIXUser", name="test", group="test",
                                   gecos="Test McTest", shell="/bin/zsh",
                                   home="/home/test", uid="1000", gid="1000")
        self.assertTrue(users._verify(entry))

        entry = lxml.etree.Element("POSIXUser", name="test", group="test",
                                   gecos="Test McTest", shell="/bin/zsh",
                                   home="/home/test", uid="1001")
        self.assertFalse(users._verify(entry))

    def test_Install(self):
        users = self.get_obj()
        users._install = Mock()
        users._existing = MagicMock()


        entries = [lxml.etree.Element("POSIXUser", name="test"),
                   lxml.etree.Element("POSIXGroup", name="test"),
                   lxml.etree.Element("POSIXUser", name="test2")]
        states = dict()

        users.Install(entries, states)
        self.assertItemsEqual(entries, states.keys())
        for state in states.values():
            self.assertEqual(state, users._install.return_value)
        # need to verify two things about _install calls:
        # 1) _install was called for each entry;
        # 2) _install was called for all groups before any users
        self.assertItemsEqual(users._install.call_args_list,
                              [call(e) for e in entries])
        users_started = False
        for args in users._install.call_args_list:
            if args[0][0].tag == "POSIXUser":
                users_started = True
            elif users_started:
                assert False, "_install() called on POSIXGroup after installing one or more POSIXUsers"

    def test__install(self):
        users = self.get_obj()
        users._get_cmd = Mock()
        users.cmd = Mock()
        users.set_defaults = dict(POSIXUser=Mock(), POSIXGroup=Mock())
        users._existing = \
            dict(POSIXUser=dict(test=('test', 'x', 1000, 1000, 'Test McTest',
                                      '/home/test', '/bin/zsh')),
                 POSIXGroup=dict(test=('test', 'x', 1000, [])))

        def reset():
            users._get_cmd.reset_mock()
            users.cmd.reset_mock()
            for setter in users.set_defaults.values():
                setter.reset_mock()
            users.modified = []

        reset()
        entry = lxml.etree.Element("POSIXUser", name="test2")
        self.assertTrue(users._install(entry))
        users.set_defaults[entry.tag].assert_called_with(entry)
        users._get_cmd.assert_called_with("add",
                                          users.set_defaults[entry.tag].return_value)
        users.cmd.run.assert_called_with(users._get_cmd.return_value)
        self.assertIn(entry, users.modified)

        reset()
        entry = lxml.etree.Element("POSIXUser", name="test")
        self.assertTrue(users._install(entry))
        users.set_defaults[entry.tag].assert_called_with(entry)
        users._get_cmd.assert_called_with("mod",
                                          users.set_defaults[entry.tag].return_value)
        users.cmd.run.assert_called_with(users._get_cmd.return_value)
        self.assertIn(entry, users.modified)

        reset()
        users.cmd.run.side_effect = ExecutionError(None)
        self.assertFalse(users._install(entry))
        users.set_defaults[entry.tag].assert_called_with(entry)
        users._get_cmd.assert_called_with("mod",
                                          users.set_defaults[entry.tag].return_value)
        users.cmd.run.assert_called_with(users._get_cmd.return_value)
        self.assertNotIn(entry, users.modified)

    def test__get_cmd(self):
        users = self.get_obj()

        entry = lxml.etree.Element("POSIXUser", name="test", group="test",
                                   home="/home/test", shell="/bin/zsh",
                                   gecos="Test McTest")
        m1 = lxml.etree.SubElement(entry, "MemberOf")
        m1.text = "wheel"
        m2 = lxml.etree.SubElement(entry, "MemberOf")
        m2.text = "users"

        cases = [(lxml.etree.Element("POSIXGroup", name="test"), []),
                 (lxml.etree.Element("POSIXGroup", name="test", gid="1001"),
                  ["-g", "1001"]),
                 (lxml.etree.Element("POSIXUser", name="test", group="test",
                                     home="/home/test", shell="/bin/zsh",
                                     gecos="Test McTest"),
                  ["-m", "-g", "test", "-d", "/home/test", "-s", "/bin/zsh",
                   "-c", "Test McTest"]),
                 (lxml.etree.Element("POSIXUser", name="test", group="test",
                                     home="/home/test", shell="/bin/zsh",
                                     gecos="Test McTest", uid="1001"),
                  ["-m", "-u", "1001", "-g", "test", "-d", "/home/test",
                   "-s", "/bin/zsh", "-c", "Test McTest"]),
                 (entry,
                  ["-m", "-g", "test", "-G", "wheel,users", "-d", "/home/test",
                   "-s", "/bin/zsh", "-c", "Test McTest"])]
        for entry, expected in cases:
            for action in ["add", "mod", "del"]:
                actual = users._get_cmd(action, entry)
                if entry.tag == "POSIXGroup":
                    etype = "group"
                else:
                    etype = "user"
                self.assertEqual(actual[0], "/usr/sbin/%s%s" % (etype, action))
                self.assertEqual(actual[-1], entry.get("name"))
                if action != "del":
                    self.assertItemsEqual(actual[1:-1], expected)

    @patch("grp.getgrnam")
    def test_Remove(self, mock_getgrnam):
        users = self.get_obj()
        users._remove = Mock()
        users.FindExtra = Mock()
        users._existing = MagicMock()
        users.extra = MagicMock()

        def reset():
            users._remove.reset_mock()
            users.FindExtra.reset_mock()
            users._existing = MagicMock()
            users.extra = MagicMock()
            mock_getgrnam.reset_mock()

        entries = [lxml.etree.Element("POSIXUser", name="test"),
                   lxml.etree.Element("POSIXGroup", name="test"),
                   lxml.etree.Element("POSIXUser", name="test2")]

        users.Remove(entries)
        self.assertIsNone(users._existing)
        users.FindExtra.assert_called_with()
        self.assertEqual(users.extra, users.FindExtra.return_value)
        mock_getgrnam.assert_called_with("test")
        # need to verify two things about _remove calls:
        # 1) _remove was called for each entry;
        # 2) _remove was called for all users before any groups
        self.assertItemsEqual(users._remove.call_args_list,
                              [call(e) for e in entries])
        groups_started = False
        for args in users._remove.call_args_list:
            if args[0][0].tag == "POSIXGroup":
                groups_started = True
            elif groups_started:
                assert False, "_remove() called on POSIXUser after removing one or more POSIXGroups"

        reset()
        mock_getgrnam.side_effect = KeyError
        users.Remove(entries)
        self.assertIsNone(users._existing)
        users.FindExtra.assert_called_with()
        self.assertEqual(users.extra, users.FindExtra.return_value)
        mock_getgrnam.assert_called_with("test")
        self.assertItemsEqual(users._remove.call_args_list,
                              [call(e) for e in entries
                               if e.tag == "POSIXUser"])

    def test__remove(self):
        users = self.get_obj()
        users._get_cmd = Mock()
        users.cmd = Mock()

        def reset():
            users._get_cmd.reset_mock()
            users.cmd.reset_mock()


        entry = lxml.etree.Element("POSIXUser", name="test2")
        self.assertTrue(users._remove(entry))
        users._get_cmd.assert_called_with("del", entry)
        users.cmd.run.assert_called_with(users._get_cmd.return_value)

        reset()
        users.cmd.run.side_effect = ExecutionError(None)
        self.assertFalse(users._remove(entry))
        users._get_cmd.assert_called_with("del", entry)
        users.cmd.run.assert_called_with(users._get_cmd.return_value)
