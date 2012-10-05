import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg.CfgCheetahGenerator import *

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
from TestServer.TestPlugins.TestCfg.Test_init import TestCfgGenerator


if HAS_CHEETAH or can_skip:
    class TestCfgCheetahGenerator(TestCfgGenerator):
        test_obj = CfgCheetahGenerator

        @skipUnless(HAS_CHEETAH, "Cheetah libraries not found, skipping")
        def setUp(self):
            pass

        @patch("Bcfg2.Server.Plugins.Cfg.CfgCheetahGenerator.Template")
        def test_get_data(self, mock_Template):
            ccg = self.get_obj(encoding='UTF-8')
            ccg.data = "data"
            entry = lxml.etree.Element("Path", name="/test.txt")
            metadata = Mock()

            self.assertEqual(ccg.get_data(entry, metadata),
                             mock_Template.return_value.respond.return_value)
            mock_Template.assert_called_with("data".decode(ccg.encoding),
                                             compilerSettings=ccg.settings)
            mock_Template.return_value.respond.assert_called_with()
