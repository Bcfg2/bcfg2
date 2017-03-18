import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator import *

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


if HAS_JINJA2 or can_skip:
    class TestCfgJinja2Generator(TestCfgGenerator):
        test_obj = CfgJinja2Generator

        @skipUnless(HAS_JINJA2, "Jinja2 libraries not found, skipping")
        def setUp(self):
            pass

        @patch("Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator.Template")
        def test_get_data(self, mock_Template):
            ccg = self.get_obj(encoding='UTF-8')
            ccg.data = "data"
            entry = lxml.etree.Element("Path", name="/test.txt")
            metadata = Mock()
            Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator.SETUP = MagicMock()

            self.assertEqual(ccg.get_data(entry, metadata),
                             mock_Template.return_value.render.return_value)
            Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator.SETUP.__getitem__.assert_called_with("repo")
            mock_Template.assert_called_with("data".decode(ccg.encoding))
            tmpl = mock_Template.return_value
            name = entry.get("name")
            tmpl.render.assert_called_with(metadata=metadata, name=name, path=name,
                                           source_path=name,
                                           repo=Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator.SETUP.__getitem__.return_value)
