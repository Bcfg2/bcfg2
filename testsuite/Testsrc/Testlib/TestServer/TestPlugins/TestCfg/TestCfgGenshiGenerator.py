import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
import Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator
from Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator import *
from Bcfg2.Server.Plugin import PluginExecutionError

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


class TestCfgGenshiGenerator(TestCfgGenerator):
    test_obj = CfgGenshiGenerator

    def setUp(self):
        TestCfgGenerator.setUp(self)
        set_setup_default("repository", datastore)

    def test__init(self):
        TestCfgGenerator.test__init(self)
        cgg = self.get_obj()
        self.assertIsInstance(cgg.loader, cgg.__loader_cls__)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator.get_template_data")
    def test_get_data(self, mock_get_template_data):
        cgg = self.get_obj()
        cgg._handle_genshi_exception = Mock()
        cgg.template = Mock()
        fltr = Mock()
        cgg.template.generate.return_value = fltr
        stream = Mock()
        fltr.filter.return_value = stream
        entry = lxml.etree.Element("Path", name="/test.txt")
        metadata = Mock()

        def reset():
            cgg.template.reset_mock()
            cgg._handle_genshi_exception.reset_mock()
            mock_get_template_data.reset_mock()

        template_vars = dict(name=entry.get("name"),
                             metadata=metadata,
                             path=cgg.name,
                             source_path=cgg.name,
                             repo=datastore)
        mock_get_template_data.return_value = template_vars

        self.assertEqual(cgg.get_data(entry, metadata),
                         stream.render.return_value)
        cgg.template.generate.assert_called_with(**template_vars)
        self.assertItemsEqual(mock_get_template_data.call_args[0],
                              [entry, metadata, cgg.name])
        self.assertIsInstance(mock_get_template_data.call_args[1]['default'],
                              DefaultGenshiDataProvider)
        fltr.filter.assert_called_with(removecomment)
        stream.render.assert_called_with(
            "text",
            encoding=Bcfg2.Options.setup.encoding,
            strip_whitespace=False)

        reset()
        def render(fmt, **kwargs):
            stream.render.side_effect = None
            raise TypeError
        stream.render.side_effect = render
        self.assertEqual(cgg.get_data(entry, metadata),
                         stream.render.return_value)
        cgg.template.generate.assert_called_with(**template_vars)
        self.assertItemsEqual(mock_get_template_data.call_args[0],
                              [entry, metadata, cgg.name])
        self.assertIsInstance(mock_get_template_data.call_args[1]['default'],
                              DefaultGenshiDataProvider)
        fltr.filter.assert_called_with(removecomment)
        self.assertEqual(stream.render.call_args_list,
                         [call("text",
                               encoding=Bcfg2.Options.setup.encoding,
                               strip_whitespace=False),
                          call("text",
                               encoding=Bcfg2.Options.setup.encoding)])

        reset()
        stream.render.side_effect = UndefinedError("test")
        self.assertRaises(UndefinedError,
                          cgg.get_data, entry, metadata)
        cgg.template.generate.assert_called_with(**template_vars)
        self.assertItemsEqual(mock_get_template_data.call_args[0],
                              [entry, metadata, cgg.name])
        self.assertIsInstance(mock_get_template_data.call_args[1]['default'],
                              DefaultGenshiDataProvider)
        fltr.filter.assert_called_with(removecomment)
        stream.render.assert_called_with("text",
                                         encoding=Bcfg2.Options.setup.encoding,
                                         strip_whitespace=False)

        reset()
        stream.render.side_effect = ValueError
        cgg._handle_genshi_exception.side_effect = ValueError
        self.assertRaises(ValueError,
                          cgg.get_data, entry, metadata)
        cgg.template.generate.assert_called_with(**template_vars)
        self.assertItemsEqual(mock_get_template_data.call_args[0],
                              [entry, metadata, cgg.name])
        self.assertIsInstance(mock_get_template_data.call_args[1]['default'],
                              DefaultGenshiDataProvider)
        fltr.filter.assert_called_with(removecomment)
        stream.render.assert_called_with("text",
                                         encoding=Bcfg2.Options.setup.encoding,
                                         strip_whitespace=False)
        self.assertTrue(cgg._handle_genshi_exception.called)

    def test_handle_event(self):
        cgg = self.get_obj()
        cgg.loader = Mock()
        event = Mock()
        cgg.handle_event(event)
        cgg.loader.load.assert_called_with(
            cgg.name,
            cls=NewTextTemplate,
            encoding=Bcfg2.Options.setup.encoding)

        cgg.loader.reset_mock()
        cgg.loader.load.side_effect = TemplateError("test")
        self.assertRaises(PluginExecutionError,
                          cgg.handle_event, event)
        cgg.loader.load.assert_called_with(
            cgg.name,
            cls=NewTextTemplate,
            encoding=Bcfg2.Options.setup.encoding)
