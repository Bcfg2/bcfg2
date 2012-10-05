import os
import sys
import Bcfg2.Server.Plugin
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.TemplateHelper import *

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
from TestPlugin import TestDirectoryBacked, TestConnector, TestPlugin, \
    TestFileBacked


class TestHelperModule(TestFileBacked):
    test_obj = HelperModule
    path = os.path.join(datastore, "test.py")

    def test__init(self):
        hm = self.get_obj()
        self.assertEqual(hm._module_name, "test")
        self.assertEqual(hm._attrs, [])

    @patch("imp.load_source")
    def test_Index(self, mock_load_source):
        hm = self.get_obj()

        mock_load_source.side_effect = ImportError
        attrs = dir(hm)
        hm.Index()
        mock_load_source.assert_called_with(hm._module_name, hm.name)
        self.assertEqual(attrs, dir(hm))
        self.assertEqual(hm._attrs, [])
        
        mock_load_source.reset()
        mock_load_source.side_effect = None
        # a regular Mock (not a MagicMock) won't automatically create
        # __export__, so this triggers a failure condition in Index
        mock_load_source.return_value = Mock()
        attrs = dir(hm)
        hm.Index()
        mock_load_source.assert_called_with(hm._module_name, hm.name)
        self.assertEqual(attrs, dir(hm))
        self.assertEqual(hm._attrs, [])

        # test reserved attributes
        module = Mock()
        module.__export__ = ["_attrs", "Index", "__init__"]
        mock_load_source.reset()
        mock_load_source.return_value = module
        attrs = dir(hm)
        hm.Index()
        mock_load_source.assert_called_with(hm._module_name, hm.name)
        self.assertEqual(attrs, dir(hm))
        self.assertEqual(hm._attrs, [])

        # test adding attributes
        module = Mock()
        module.__export__ = ["foo", "bar", "baz", "Index"]
        mock_load_source.reset()
        mock_load_source.return_value = module
        hm.Index()
        mock_load_source.assert_called_with(hm._module_name, hm.name)
        self.assertTrue(hasattr(hm, "foo"))
        self.assertTrue(hasattr(hm, "bar"))
        self.assertTrue(hasattr(hm, "baz"))
        self.assertEqual(hm._attrs, ["foo", "bar", "baz"])

        # test removing attributes
        module = Mock()
        module.__export__ = ["foo", "bar", "quux", "Index"]
        mock_load_source.reset()
        mock_load_source.return_value = module
        hm.Index()
        mock_load_source.assert_called_with(hm._module_name, hm.name)
        self.assertTrue(hasattr(hm, "foo"))
        self.assertTrue(hasattr(hm, "bar"))
        self.assertTrue(hasattr(hm, "quux"))
        self.assertFalse(hasattr(hm, "baz"))
        self.assertEqual(hm._attrs, ["foo", "bar", "quux"])
        


class TestHelperSet(TestDirectoryBacked):
    test_obj = HelperSet
    testfiles = ['foo.py', 'foo_bar.py', 'foo.bar.py']
    ignore = ['fooo.py~', 'fooo.pyc', 'fooo.pyo']
    badevents = ['foo']


class TestTemplateHelper(TestPlugin, TestConnector):
    test_obj = TemplateHelper

    def test__init(self):
        TestPlugin.test__init(self)

        th = self.get_obj()
        self.assertIsInstance(th.helpers, HelperSet)

    def test_get_additional_data(self):
        TestConnector.test_get_additional_data(self)

        th = self.get_obj()
        modules = ['foo', 'bar']
        rv = dict()
        for mname in modules:
            module = Mock()
            module._module_name = mname
            rv[mname] = module
            th.helpers.entries['%s.py' % mname] = module
        actual = th.get_additional_data(Mock())
        self.assertItemsEqual(actual, rv)
