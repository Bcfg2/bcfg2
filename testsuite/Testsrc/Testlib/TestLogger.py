import os
import sys
import logging
from mock import Mock
from Bcfg2.Logger import *

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


class TestDebuggable(Bcfg2TestCase):
    test_obj = Debuggable

    def setUp(self):
        set_setup_default('debug', False)

    def get_obj(self):
        return self.test_obj()

    def test__init(self):
        d = self.get_obj()
        self.assertIsInstance(d.logger, logging.Logger)
        self.assertFalse(d.debug_flag)

    def test_set_debug(self):
        d = self.get_obj()
        self.assertEqual(True, d.set_debug(True))
        self.assertEqual(d.debug_flag, True)

        self.assertEqual(False, d.set_debug(False))
        self.assertEqual(d.debug_flag, False)

    def test_toggle_debug(self):
        d = self.get_obj()
        d.set_debug = Mock()
        orig = d.debug_flag
        self.assertEqual(d.toggle_debug(),
                         d.set_debug.return_value)
        d.set_debug.assert_called_with(not orig)

    def test_debug_log(self):
        d = self.get_obj()
        d.logger = Mock()
        d.debug_flag = False
        d.debug_log("test")
        self.assertFalse(d.logger.error.called)

        d.logger.reset_mock()
        d.debug_log("test", flag=True)
        self.assertTrue(d.logger.error.called)

        d.logger.reset_mock()
        d.debug_flag = True
        d.debug_log("test")
        self.assertTrue(d.logger.error.called)
