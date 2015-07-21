import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg import CfgCheetahGenerator

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


if CfgCheetahGenerator.HAS_CHEETAH or can_skip:
    class TestCfgCheetahGenerator(TestCfgGenerator):
        test_obj = CfgCheetahGenerator.CfgCheetahGenerator

        @skipUnless(CfgCheetahGenerator.HAS_CHEETAH,
                    "Cheetah libraries not found, skipping")
        def setUp(self):
            pass

        @patch("Bcfg2.Server.Plugins.Cfg.CfgCheetahGenerator.Template")
        def test_get_data(self, mock_Template):
            ccg = self.get_obj(encoding='UTF-8')
            ccg.data = "data"
            entry = lxml.etree.Element("Path", name="/test.txt")
            metadata = Mock()
            CfgCheetahGenerator.SETUP = MagicMock()

            self.assertEqual(ccg.get_data(entry, metadata),
                             mock_Template.return_value.respond.return_value)
            CfgCheetahGenerator.SETUP.__getitem__.assert_called_with("repo")
            mock_Template.assert_called_with("data".decode(ccg.encoding),
                                             compilerSettings=ccg.settings)
            tmpl = mock_Template.return_value
            tmpl.respond.assert_called_with()
            self.assertEqual(tmpl.metadata, metadata)
            self.assertEqual(tmpl.name, entry.get("name"))
            self.assertEqual(tmpl.path, entry.get("name"))
            self.assertEqual(tmpl.source_path, ccg.name)
            self.assertEqual(
                tmpl.repo,
                CfgCheetahGenerator.SETUP.__getitem__.return_value)
