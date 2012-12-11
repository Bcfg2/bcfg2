import os
import sys
from mock import Mock, patch
from subprocess import PIPE
from Bcfg2.Server.Plugins.Trigger import *

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
from TestPlugin import TestDirectoryBacked, TestClientRunHooks, TestPlugin, \
    TestFileBacked


class TestTriggerFile(TestFileBacked):
    test_obj = TriggerFile

    def test_HandleEvent(self):
        pass


class TestTrigger(TestPlugin, TestClientRunHooks, TestDirectoryBacked):
    test_obj = Trigger

    def get_obj(self, core=None, fam=None):
        if core is None:
            core = Mock()
        if fam is not None:
            core.fam = fam

        @patch("%s.%s.add_directory_monitor" % (self.test_obj.__module__,
                                                self.test_obj.__name__),
               Mock())
        def inner():
            return TestPlugin.get_obj(self, core=core)
        return inner()

    @patch("os.fork")
    @patch("os._exit")
    @patch("os.waitpid")
    @patch("subprocess.Popen")
    @skip("Tests that call os.fork are broken, even when os.fork is mocked")
    def test_async_run(self, mock_Popen, mock_waitpid, mock_exit, mock_fork):
        trigger = self.get_obj()

        def reset():
            mock_Popen.reset_mock()
            mock_waitpid.reset_mock()
            mock_exit.reset_mock()
            mock_fork.reset_mock()

        mock_fork.return_value = 0
        trigger.async_run(["foo", "bar"])
        self.assertItemsEqual(mock_fork.call_args_list,
                              [call(), call()])
        mock_Popen.assert_called_with(["foo", "bar"], stdin=PIPE, stdout=PIPE,
                                      stderr=PIPE)
        mock_Popen.return_value.wait.assert_called_with()
        mock_exit.assert_called_with(0)

        reset()
        mock_fork.return_value = 123
        trigger.async_run(["foo", "bar"])
        mock_fork.assert_called_with()
        mock_waitpid.assert_called_with(123, 0)
        self.assertFalse(mock_Popen.called)

    def test_end_client_run(self):
        trigger = self.get_obj()
        trigger.async_run = Mock()
        trigger.entries = {'foo.sh': Mock(), 'bar': Mock()}

        metadata = Mock()
        metadata.hostname = "host"
        metadata.profile = "profile"
        metadata.groups = ['a', 'b', 'c']
        args = ['host', '-p', 'profile', '-g', 'a:b:c']

        trigger.end_client_run(metadata)
        self.assertItemsEqual([[os.path.join(trigger.data, 'foo.sh')] + args,
                               [os.path.join(trigger.data, 'bar')] + args],
                              [c[0][0]
                               for c in trigger.async_run.call_args_list])
