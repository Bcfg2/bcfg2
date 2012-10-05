import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
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


if can_skip or HAS_GENSHI:
    class TestCfgGenshiGenerator(TestCfgGenerator):
        test_obj = CfgGenshiGenerator

        @skipUnless(HAS_GENSHI, "Genshi libraries not found, skipping")
        def setUp(self):
            pass

        def test_removecomment(self):
            data = [(None, "test", 1),
                    (None, "test2", 2)]
            stream = [(genshi.core.COMMENT, "test", 0),
                      data[0],
                      (genshi.core.COMMENT, "test3", 0),
                      data[1]]
            self.assertItemsEqual(list(removecomment(stream)), data)

        def test__init(self):
            TestCfgGenerator.test__init(self)
            cgg = self.get_obj()
            self.assertIsInstance(cgg.loader, cgg.__loader_cls__)

        def test_get_data(self):
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

            self.assertEqual(cgg.get_data(entry, metadata),
                             stream.render.return_value)
            cgg.template.generate.assert_called_with(name=entry.get("name"),
                                                     metadata=metadata,
                                                     path=cgg.name)
            fltr.filter.assert_called_with(removecomment)
            stream.render.assert_called_with("text", encoding=cgg.encoding,
                                             strip_whitespace=False)

            reset()
            def render(fmt, **kwargs):
                stream.render.side_effect = None
                raise TypeError
            stream.render.side_effect = render
            self.assertEqual(cgg.get_data(entry, metadata),
                             stream.render.return_value)
            cgg.template.generate.assert_called_with(name=entry.get("name"),
                                                     metadata=metadata,
                                                     path=cgg.name)
            fltr.filter.assert_called_with(removecomment)
            self.assertEqual(stream.render.call_args_list,
                             [call("text", encoding=cgg.encoding,
                                  strip_whitespace=False),
                              call("text", encoding=cgg.encoding)])

            reset()
            stream.render.side_effect = UndefinedError("test")
            self.assertRaises(UndefinedError,
                              cgg.get_data, entry, metadata)
            cgg.template.generate.assert_called_with(name=entry.get("name"),
                                                     metadata=metadata,
                                                     path=cgg.name)
            fltr.filter.assert_called_with(removecomment)
            stream.render.assert_called_with("text", encoding=cgg.encoding,
                                             strip_whitespace=False)

            reset()
            stream.render.side_effect = ValueError
            cgg._handle_genshi_exception.side_effect = ValueError
            self.assertRaises(ValueError,
                              cgg.get_data, entry, metadata)
            cgg.template.generate.assert_called_with(name=entry.get("name"),
                                                     metadata=metadata,
                                                     path=cgg.name)
            fltr.filter.assert_called_with(removecomment)
            stream.render.assert_called_with("text", encoding=cgg.encoding,
                                             strip_whitespace=False)
            self.assertTrue(cgg._handle_genshi_exception.called)

        def test_handle_event(self):
            @patch("Bcfg2.Server.Plugins.Cfg.CfgGenerator.handle_event")
            def inner(mock_handle_event):
                cgg = self.get_obj()
                cgg.loader = Mock()
                cgg.data = "template data"
                event = Mock()
                cgg.handle_event(event)
                cgg.loader.load.assert_called_with(cgg.name,
                                                   cls=NewTextTemplate,
                                                   encoding=cgg.encoding)

                cgg.loader.reset_mock()
                cgg.loader.load.side_effect = OSError
                self.assertRaises(PluginExecutionError,
                                  cgg.handle_event, event)
                cgg.loader.load.assert_called_with(cgg.name,
                                                   cls=NewTextTemplate,
                                                   encoding=cgg.encoding)

            inner()
            loader_cls = self.test_obj.__loader_cls__
            self.test_obj.__loader_cls__ = Mock
            TestCfgGenerator.test_handle_event(self)
            self.test_obj.__loader_cls__ = loader_cls
