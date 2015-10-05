import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Properties import *
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
from TestPlugin import TestStructFile, TestFileBacked, TestConnector, \
    TestPlugin, TestDirectoryBacked

try:
    import json
    JSON = "json"
except ImportError:
    JSON = "simplejson"


class TestPropertyFile(Bcfg2TestCase):
    test_obj = PropertyFile
    path = os.path.join(datastore, "test")

    def get_obj(self, path=None, core=None, *args, **kwargs):
        set_setup_default("writes_enabled", False)
        if path is None:
            path = self.path
        if core is None:
            core = Mock()
            core.metadata_cache_mode = 'none'
        return self.test_obj(path, core, *args, **kwargs)

    def test_write(self):
        pf = self.get_obj()
        pf.validate_data = Mock()
        pf._write = Mock()

        xstr = u("<Properties/>\n")
        pf.xdata = lxml.etree.XML(xstr)

        def reset():
            pf.validate_data.reset_mock()
            pf._write.reset_mock()

        # test writes disabled
        Bcfg2.Options.setup.writes_enabled = False
        self.assertRaises(PluginExecutionError, pf.write)
        self.assertFalse(pf.validate_data.called)
        self.assertFalse(pf._write.called)

        # test successful write
        reset()
        Bcfg2.Options.setup.writes_enabled = True
        self.assertEqual(pf.write(), pf._write.return_value)
        pf.validate_data.assert_called_with()
        pf._write.assert_called_with()

        # test error from _write
        reset()
        pf._write.side_effect = IOError
        self.assertRaises(PluginExecutionError, pf.write)
        pf.validate_data.assert_called_with()
        pf._write.assert_called_with()

        # test error from validate_data
        reset()
        pf.validate_data.side_effect = PluginExecutionError
        self.assertRaises(PluginExecutionError, pf.write)
        pf.validate_data.assert_called_with()

    def test__write(self):
        pf = self.get_obj()
        self.assertRaises(NotImplementedError, pf._write)

    def test_validate_data(self):
        pf = self.get_obj()
        self.assertRaises(NotImplementedError, pf.validate_data)

    @patch("copy.copy")
    def test_get_additional_data(self, mock_copy):
        pf = self.get_obj()
        self.assertEqual(pf.get_additional_data(Mock()),
                         mock_copy.return_value)
        mock_copy.assert_called_with(pf)


class TestJSONPropertyFile(TestFileBacked, TestPropertyFile):
    test_obj = JSONPropertyFile

    @skipUnless(HAS_JSON, "JSON libraries not found, skipping")
    def setUp(self):
        TestFileBacked.setUp(self)
        TestPropertyFile.setUp(self)

    def get_obj(self, *args, **kwargs):
        return TestPropertyFile.get_obj(self, *args, **kwargs)

    @patch("%s.loads" % JSON)
    def test_Index(self, mock_loads):
        pf = self.get_obj()
        pf.Index()
        mock_loads.assert_called_with(pf.data)
        self.assertEqual(pf.json, mock_loads.return_value)

        mock_loads.reset_mock()
        mock_loads.side_effect = ValueError
        self.assertRaises(PluginExecutionError, pf.Index)
        mock_loads.assert_called_with(pf.data)

    @patch("%s.dump" % JSON)
    @patch("%s.open" % builtins)
    def test__write(self, mock_open, mock_dump):
        pf = self.get_obj()
        self.assertTrue(pf._write())
        mock_open.assert_called_with(pf.name, 'wb')
        mock_dump.assert_called_with(pf.json, mock_open.return_value)

    @patch("%s.dumps" % JSON)
    def test_validate_data(self, mock_dumps):
        pf = self.get_obj()
        pf.validate_data()
        mock_dumps.assert_called_with(pf.json)

        mock_dumps.reset_mock()
        mock_dumps.side_effect = TypeError
        self.assertRaises(PluginExecutionError, pf.validate_data)
        mock_dumps.assert_called_with(pf.json)


class TestYAMLPropertyFile(TestFileBacked, TestPropertyFile):
    test_obj = YAMLPropertyFile

    @skipUnless(HAS_YAML, "YAML libraries not found, skipping")
    def setUp(self):
        TestFileBacked.setUp(self)
        TestPropertyFile.setUp(self)

    def get_obj(self, *args, **kwargs):
        return TestPropertyFile.get_obj(self, *args, **kwargs)

    @patch("yaml.load")
    def test_Index(self, mock_load):
        pf = self.get_obj()
        pf.Index()
        mock_load.assert_called_with(pf.data)
        self.assertEqual(pf.yaml, mock_load.return_value)

        mock_load.reset_mock()
        mock_load.side_effect = yaml.YAMLError
        self.assertRaises(PluginExecutionError, pf.Index)
        mock_load.assert_called_with(pf.data)

    @patch("yaml.dump")
    @patch("%s.open" % builtins)
    def test__write(self, mock_open, mock_dump):
        pf = self.get_obj()
        self.assertTrue(pf._write())
        mock_open.assert_called_with(pf.name, 'wb')
        mock_dump.assert_called_with(pf.yaml, mock_open.return_value)

    @patch("yaml.dump")
    def test_validate_data(self, mock_dump):
        pf = self.get_obj()
        pf.validate_data()
        mock_dump.assert_called_with(pf.yaml)

        mock_dump.reset_mock()
        mock_dump.side_effect = yaml.YAMLError
        self.assertRaises(PluginExecutionError, pf.validate_data)
        mock_dump.assert_called_with(pf.yaml)


class TestXMLPropertyFile(TestPropertyFile, TestStructFile):
    test_obj = XMLPropertyFile
    path = TestStructFile.path

    def setUp(self):
        TestPropertyFile.setUp(self)
        TestStructFile.setUp(self)
        set_setup_default("automatch", False)

    def get_obj(self, *args, **kwargs):
        return TestPropertyFile.get_obj(self, *args, **kwargs)

    @patch("%s.open" % builtins)
    def test__write(self, mock_open):
        pf = self.get_obj()
        pf.xdata = lxml.etree.Element("Test")
        self.assertTrue(pf._write())
        mock_open.assert_called_with(pf.name, "wb")
        self.assertXMLEqual(pf.xdata,
                            lxml.etree.XML(mock_open.return_value.write.call_args[0][0]))

    @patch("os.path.exists")
    @patch("lxml.etree.XMLSchema")
    def test_validate_data(self, mock_XMLSchema, mock_exists):
        pf = self.get_obj()
        pf.name = os.path.join(datastore, "Properties", "test.xml")
        schemafile = os.path.join(datastore, "Properties", "test.xsd")

        def reset():
            mock_XMLSchema.reset_mock()
            mock_exists.reset_mock()

        # test no schema file
        mock_exists.return_value = False
        self.assertTrue(pf.validate_data())
        mock_exists.assert_called_with(schemafile)

        # test schema file exists, valid data
        reset()
        mock_exists.return_value = True
        mock_XMLSchema.return_value = Mock()
        mock_XMLSchema.return_value.validate.return_value = True
        self.assertTrue(pf.validate_data())
        mock_exists.assert_called_with(schemafile)
        mock_XMLSchema.assert_called_with(file=schemafile)
        mock_XMLSchema.return_value.validate.assert_called_with(pf.xdata)

        # test schema file exists, invalid data
        reset()
        mock_XMLSchema.return_value = Mock()
        mock_XMLSchema.return_value.validate.return_value = False
        self.assertRaises(PluginExecutionError, pf.validate_data)
        mock_exists.assert_called_with(schemafile)
        mock_XMLSchema.assert_called_with(file=schemafile)
        mock_XMLSchema.return_value.validate.assert_called_with(pf.xdata)

        # test invalid schema file
        reset()
        mock_XMLSchema.side_effect = lxml.etree.XMLSchemaParseError(pf.xdata)
        self.assertRaises(PluginExecutionError, pf.validate_data)
        mock_exists.assert_called_with(schemafile)
        mock_XMLSchema.assert_called_with(file=schemafile)

    @patch("copy.copy")
    def test_get_additional_data(self, mock_copy):
        pf = self.get_obj()
        pf.setup = Mock()
        pf.XMLMatch = Mock()
        metadata = Mock()

        def reset():
            mock_copy.reset_mock()
            pf.XMLMatch.reset_mock()
            pf.setup.reset_mock()

        pf.xdata = lxml.etree.Element("Properties", automatch="true")
        for Bcfg2.Options.setup.automatch in [True, False]:
            reset()
            self.assertEqual(pf.get_additional_data(metadata),
                             pf.XMLMatch.return_value)
            pf.XMLMatch.assert_called_with(metadata)
            self.assertFalse(mock_copy.called)

        pf.xdata = lxml.etree.Element("Properties", automatch="false")
        for Bcfg2.Options.setup.automatch in [True, False]:
            reset()
            self.assertEqual(pf.get_additional_data(metadata),
                             mock_copy.return_value)
            mock_copy.assert_called_with(pf)
            self.assertFalse(pf.XMLMatch.called)

        pf.xdata = lxml.etree.Element("Properties")
        reset()
        Bcfg2.Options.setup.automatch = False
        self.assertEqual(pf.get_additional_data(metadata),
                         mock_copy.return_value)
        mock_copy.assert_called_with(pf)
        self.assertFalse(pf.XMLMatch.called)

        reset()
        Bcfg2.Options.setup.automatch = True
        self.assertEqual(pf.get_additional_data(metadata),
                         pf.XMLMatch.return_value)
        pf.XMLMatch.assert_called_with(metadata)
        self.assertFalse(mock_copy.called)


class TestProperties(TestPlugin, TestConnector, TestDirectoryBacked):
    test_obj = Properties
    testfiles = ['foo.xml', 'bar.baz.xml']
    if HAS_JSON:
        testfiles.extend(["foo.json", "foo.xml.json"])
    if HAS_YAML:
        testfiles.extend(["foo.yaml", "foo.yml", "foo.xml.yml"])
    ignore = ['foo.xsd', 'bar.baz.xsd', 'quux.xml.xsd']
    badevents = ['bogus.txt']

    def get_obj(self, core=None):
        @patch("%s.%s.add_directory_monitor" % (self.test_obj.__module__,
                                                self.test_obj.__name__),
               Mock())
        def inner():
            return TestPlugin.get_obj(self, core=core)
        return inner()

    @patch("copy.copy")
    def test_get_additional_data(self, mock_copy):
        TestConnector.test_get_additional_data(self)

        p = self.get_obj()
        metadata = Mock()
        p.entries = {"foo.xml": Mock(),
                     "foo.yml": Mock()}
        rv = p.get_additional_data(metadata)
        expected = dict()
        for name, entry in p.entries.items():
            entry.get_additional_data.assert_called_with(metadata)
            expected[name] = entry.get_additional_data.return_value
        self.assertItemsEqual(rv, expected)
