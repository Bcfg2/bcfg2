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

    def test__init(self):
        TestCfgGenerator.test__init(self)
        cgg = self.get_obj()
        self.assertIsInstance(cgg.loader, cgg.__loader_cls__)
        self.assertIsInstance(cgg.environment, cgg.__environment_cls__)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator.Environment")
    @patch("Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator.get_template_data")
    def test_get_data(self, mock_get_template_data, mock_Environment):
        cgg = self.get_obj()
        entry = lxml.etree.Element("Path", name="/test.txt")
        metadata = Mock()

        # self.template is currently None
        self.assertRaises(PluginExecutionError,
                          cgg.get_data, entry, metadata)

        cgg.template = mock_Environment.return_value.get_template.return_value

        template_vars = dict(name=entry.get("name"),
                             metadata=metadata,
                             path=cgg.name,
                             source_path=cgg.name,
                             repo=datastore)
        mock_get_template_data.return_value = template_vars

        tmpl = mock_Environment.return_value.get_template.return_value
        self.assertEqual(cgg.get_data(entry, metadata),
                         tmpl.render.return_value)
        tmpl.render.assert_called_with(template_vars)

    def test_handle_event(self):
        cgg = self.get_obj()
        cgg.environment = Mock()
        event = Mock()
        cgg.handle_event(event)
        cgg.environment.get_template.assert_called_with(
            cgg.name)

        cgg.environment.reset_mock()
        cgg.environment.get_template.side_effect = OSError
        self.assertRaises(PluginExecutionError,
                          cgg.handle_event, event)
        cgg.environment.get_template.assert_called_with(
            cgg.name)
