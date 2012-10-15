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

    def get_obj(self, path=None):
        if path is None:
            path = self.path
        return self.test_obj(path)

    def test_write(self):
        Bcfg2.Server.Plugins.Properties.SETUP = Mock()
        pf = self.get_obj()
        pf.validate_data = Mock()
        pf._write = Mock()

        xstr = u("<Properties/>\n")
        pf.xdata = lxml.etree.XML(xstr)

        def reset():
            pf.validate_data.reset_mock()
            pf._write.reset_mock()
            Bcfg2.Server.Plugins.Properties.SETUP.reset_mock()

        # test writes disabled
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.return_value = False
        self.assertRaises(PluginExecutionError, pf.write)
        self.assertFalse(pf.validate_data.called)
        self.assertFalse(pf._write.called)
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.assert_called_with("properties",
                                                "writes_enabled",
                                                default=True)

        # test successful write
        reset()
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.return_value = True
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


if can_skip or HAS_JSON:
    class TestJSONPropertyFile(TestFileBacked, TestPropertyFile):
        test_obj = JSONPropertyFile

        def get_obj(self, *args, **kwargs):
            return TestFileBacked.get_obj(self, *args, **kwargs)

        @skipUnless(HAS_JSON, "JSON libraries not found, skipping")
        def setUp(self):
            pass

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
            mock_dumps.side_effect = ValueError
            self.assertRaises(PluginExecutionError, pf.validate_data)
            mock_dumps.assert_called_with(pf.json)


if can_skip or HAS_YAML:
    class TestYAMLPropertyFile(TestFileBacked, TestPropertyFile):
        test_obj = YAMLPropertyFile

        def get_obj(self, *args, **kwargs):
            return TestFileBacked.get_obj(self, *args, **kwargs)

        @skipUnless(HAS_YAML, "YAML libraries not found, skipping")
        def setUp(self):
            pass

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

    def get_obj(self, *args, **kwargs):
        return TestStructFile.get_obj(self, *args, **kwargs)

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

    def test_Index(self):
        TestStructFile.test_Index(self)

        pf = self.get_obj()
        pf.xdata = lxml.etree.Element("Properties", encryption="true")
        pf.data = lxml.etree.tostring(pf.xdata)
        # extra test: crypto is not available, but properties file is
        # encrypted
        has_crypto = Bcfg2.Server.Plugins.Properties.HAS_CRYPTO
        Bcfg2.Server.Plugins.Properties.HAS_CRYPTO = False
        self.assertRaises(PluginExecutionError, pf.Index)
        Bcfg2.Server.Plugins.Properties.HAS_CRYPTO = has_crypto

    @skipUnless(HAS_CRYPTO, "No crypto libraries found, skipping")
    def test_Index_crypto(self):
        pf = self.get_obj()
        pf._decrypt = Mock()
        pf._decrypt.return_value = 'plaintext'
        pf.data = '''
<Properties encryption="true">
  <Crypted encrypted="foo">
    crypted
    <Plain foo="bar">plain</Plain>
  </Crypted>
  <Crypted encrypted="bar">crypted</Crypted>
  <Plain bar="baz">plain</Plain>
  <Plain>
    <Crypted encrypted="foo">crypted</Crypted>
  </Plain>
</Properties>'''

        # test successful decryption
        pf.Index()
        self.assertItemsEqual(pf._decrypt.call_args_list,
                              [call(el) for el in pf.xdata.xpath("//Crypted")])
        for el in pf.xdata.xpath("//Crypted"):
            self.assertEqual(el.text, pf._decrypt.return_value)

        # test failed decryption
        pf._decrypt.reset_mock()
        pf._decrypt.side_effect = EVPError
        self.assertRaises(PluginExecutionError, pf.Index)

    @skipUnless(HAS_CRYPTO, "No crypto libraries found, skipping")
    def test_decrypt(self):

        @patch("Bcfg2.Encryption.ssl_decrypt")
        @patch("Bcfg2.Encryption.get_algorithm")
        @patch("Bcfg2.Encryption.get_passphrases")
        @patch("Bcfg2.Encryption.bruteforce_decrypt")
        def inner(mock_bruteforce, mock_get_passphrases, mock_get_algorithm,
                  mock_ssl):
            pf = self.get_obj()

            def reset():
                mock_bruteforce.reset_mock()
                mock_get_algorithm.reset_mock()
                mock_get_passphrases.reset_mock()
                mock_ssl.reset_mock()

            # test element without text contents
            self.assertIsNone(pf._decrypt(lxml.etree.Element("Test")))
            self.assertFalse(mock_bruteforce.called)
            self.assertFalse(mock_get_passphrases.called)
            self.assertFalse(mock_ssl.called)

            # test element with a passphrase in the config file
            reset()
            el = lxml.etree.Element("Test", encrypted="foo")
            el.text = "crypted"
            mock_get_passphrases.return_value = dict(foo="foopass",
                                                     bar="barpass")
            mock_get_algorithm.return_value = "bf_cbc"
            mock_ssl.return_value = "decrypted with ssl"
            self.assertEqual(pf._decrypt(el), mock_ssl.return_value)
            mock_get_passphrases.assert_called_with(SETUP)
            mock_get_algorithm.assert_called_with(SETUP)
            mock_ssl.assert_called_with(el.text, "foopass",
                                        algorithm="bf_cbc")
            self.assertFalse(mock_bruteforce.called)

            # test failure to decrypt element with a passphrase in the config
            reset()
            mock_ssl.side_effect = EVPError
            self.assertRaises(EVPError, pf._decrypt, el)
            mock_get_passphrases.assert_called_with(SETUP)
            mock_get_algorithm.assert_called_with(SETUP)
            mock_ssl.assert_called_with(el.text, "foopass",
                                        algorithm="bf_cbc")
            self.assertFalse(mock_bruteforce.called)

            # test element without valid passphrase
            reset()
            el.set("encrypted", "true")
            mock_bruteforce.return_value = "decrypted with bruteforce"
            self.assertEqual(pf._decrypt(el), mock_bruteforce.return_value)
            mock_get_passphrases.assert_called_with(SETUP)
            mock_get_algorithm.assert_called_with(SETUP)
            mock_bruteforce.assert_called_with(el.text,
                                               passphrases=["foopass",
                                                            "barpass"],
                                               algorithm="bf_cbc")
            self.assertFalse(mock_ssl.called)

            # test failure to decrypt element without valid passphrase
            reset()
            mock_bruteforce.side_effect = EVPError
            self.assertRaises(EVPError, pf._decrypt, el)
            mock_get_passphrases.assert_called_with(SETUP)
            mock_get_algorithm.assert_called_with(SETUP)
            mock_bruteforce.assert_called_with(el.text,
                                               passphrases=["foopass",
                                                            "barpass"],
                                               algorithm="bf_cbc")
            self.assertFalse(mock_ssl.called)

    @patch("copy.copy")
    def test_get_additional_data(self, mock_copy):
        Bcfg2.Server.Plugins.Properties.SETUP = Mock()
        pf = self.get_obj()
        pf.XMLMatch = Mock()
        metadata = Mock()

        def reset():
            mock_copy.reset_mock()
            pf.XMLMatch.reset_mock()
            Bcfg2.Server.Plugins.Properties.SETUP.reset_mock()

        pf.xdata = lxml.etree.Element("Properties", automatch="true")
        for automatch in [True, False]:
            reset()
            Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.return_value = automatch
            self.assertEqual(pf.get_additional_data(metadata),
                             pf.XMLMatch.return_value)
            pf.XMLMatch.assert_called_with(metadata)
            Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.assert_called_with("properties", "automatch", default=False)
            self.assertFalse(mock_copy.called)

        pf.xdata = lxml.etree.Element("Properties", automatch="false")
        for automatch in [True, False]:
            reset()
            Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.return_value = automatch
            self.assertEqual(pf.get_additional_data(metadata),
                             mock_copy.return_value)
            mock_copy.assert_called_with(pf)
            self.assertFalse(pf.XMLMatch.called)
            Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.assert_called_with("properties", "automatch", default=False)

        pf.xdata = lxml.etree.Element("Properties")
        reset()
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.return_value = False
        self.assertEqual(pf.get_additional_data(metadata),
                         mock_copy.return_value)
        mock_copy.assert_called_with(pf)
        self.assertFalse(pf.XMLMatch.called)
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.assert_called_with("properties", "automatch", default=False)

        reset()
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.return_value = True
        self.assertEqual(pf.get_additional_data(metadata),
                         pf.XMLMatch.return_value)
        pf.XMLMatch.assert_called_with(metadata)
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.assert_called_with("properties", "automatch", default=False)
        self.assertFalse(mock_copy.called)


class TestPropDirectoryBacked(TestDirectoryBacked):
    test_obj = PropDirectoryBacked
    testfiles = ['foo.xml', 'bar.baz.xml']
    if HAS_JSON:
        testfiles.extend(["foo.json", "foo.xml.json"])
    if HAS_YAML:
        testfiles.extend(["foo.yaml", "foo.yml", "foo.xml.yml"])
    ignore = ['foo.xsd', 'bar.baz.xsd', 'quux.xml.xsd']
    badevents = ['bogus.txt']


class TestProperties(TestPlugin, TestConnector):
    test_obj = Properties

    def test__init(self):
        TestPlugin.test__init(self)

        core = Mock()
        p = self.get_obj(core=core)
        self.assertIsInstance(p.store, PropDirectoryBacked)
        self.assertEqual(Bcfg2.Server.Plugins.Properties.SETUP, core.setup)

    @patch("copy.copy")
    def test_get_additional_data(self, mock_copy):
        TestConnector.test_get_additional_data(self)

        p = self.get_obj()
        metadata = Mock()
        p.store.entries = {"foo.xml": Mock(),
                           "foo.yml": Mock()}
        rv = p.get_additional_data(metadata)
        expected = dict()
        for name, entry in p.store.entries.items():
            entry.get_additional_data.assert_called_with(metadata)
            expected[name] = entry.get_additional_data.return_value
        self.assertItemsEqual(rv, expected)
