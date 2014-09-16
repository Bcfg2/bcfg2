import os
import sys
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugin.base import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != '/':
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import *
from TestLogger import TestDebuggable


class TestPlugin(TestDebuggable):
    test_obj = Plugin

    def setUp(self):
        TestDebuggable.setUp(self)
        set_setup_default("filemonitor", MagicMock())
        set_setup_default("repository", datastore)

    def get_obj(self, core=None):
        if core is None:
            core = Mock()

        @patchIf(not isinstance(os.makedirs, Mock), "os.makedirs", Mock())
        def inner():
            return self.test_obj(core)
        return inner()

    @patch("os.makedirs")
    @patch("os.path.exists")
    def test__init(self, mock_exists, mock_makedirs):
        if self.test_obj.create:
            core = Mock()
            core.setup = MagicMock()

            mock_exists.return_value = True
            p = self.get_obj(core=core)
            self.assertEqual(p.data, os.path.join(datastore, p.name))
            self.assertEqual(p.core, core)
            mock_exists.assert_any_call(p.data)
            self.assertFalse(mock_makedirs.called)

            mock_exists.reset_mock()
            mock_makedirs.reset_mock()
            mock_exists.return_value = False
            p = self.get_obj(core=core)
            self.assertEqual(p.data, os.path.join(datastore, p.name))
            self.assertEqual(p.core, core)
            mock_exists.assert_any_call(p.data)
            mock_makedirs.assert_any_call(p.data)

    @patch("os.makedirs")
    def test_init_repo(self, mock_makedirs):
        self.test_obj.init_repo(datastore)
        mock_makedirs.assert_called_with(os.path.join(datastore,
                                                      self.test_obj.name))
