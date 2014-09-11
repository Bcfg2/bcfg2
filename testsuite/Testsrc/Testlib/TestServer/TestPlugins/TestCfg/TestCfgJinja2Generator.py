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


class TestCfgJinja2Generator(TestCfgGenerator):
    test_obj = CfgJinja2Generator

    @skipUnless(HAS_JINJA2, "Jinja2 libraries not found, skipping")
    def setUp(self):
        TestCfgGenerator.setUp(self)
        set_setup_default("repository", datastore)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator.Template")
    @patch("Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator.get_template_data")
    def test_get_data(self, mock_get_template_data, mock_Template):
        ccg = self.get_obj()
        ccg.data = "data"
        entry = lxml.etree.Element("Path", name="/test.txt")
        metadata = Mock()

        template_vars = dict(name=entry.get("name"),
                             metadata=metadata,
                             path=ccg.name,
                             source_path=ccg.name,
                             repo=datastore)
        mock_get_template_data.return_value = template_vars

        self.assertEqual(ccg.get_data(entry, metadata),
                         mock_Template.return_value.render.return_value)
        mock_Template.assert_called_with("data".decode(Bcfg2.Options.setup.encoding))
        tmpl = mock_Template.return_value
        tmpl.render.assert_called_with(template_vars)
