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
from common import XI_NAMESPACE, XI, inPy3k, call, builtins, u, can_skip, \
    skip, skipIf, skipUnless, Bcfg2TestCase, DBModelTestCase, syncdb, \
    patchIf, datastore
from TestPlugin import TestStructFile, TestConnector, TestPlugin, \
    TestDirectoryBacked


class TestPropertyFile(TestStructFile):
    test_obj = PropertyFile

    @patch("%s.open" % builtins)
    def test_write(self, mock_open):
        Bcfg2.Server.Plugins.Properties.SETUP = Mock()
        pf = self.get_obj()
        pf.validate_data = Mock()

        xstr = u("<Properties/>\n")
        pf.xdata = lxml.etree.XML(xstr)

        def reset():
            pf.validate_data.reset_mock()
            Bcfg2.Server.Plugins.Properties.SETUP.reset_mock()
            mock_open.reset_mock()

        # test writes disabled
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.return_value = False
        self.assertRaises(PluginExecutionError, pf.write)
        self.assertFalse(pf.validate_data.called)
        self.assertFalse(mock_open.called)
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.assert_called_with("properties",
                                                "writes_enabled",
                                                default=True)

        # test successful write
        reset()
        Bcfg2.Server.Plugins.Properties.SETUP.cfp.getboolean.return_value = True
        self.assertTrue(pf.write())
        pf.validate_data.assert_called_with()
        mock_open.assert_called_with(pf.name, "wb")
        mock_open.return_value.write.assert_called_with(xstr)

        # test error from write
        reset()
        mock_open.side_effect = IOError
        self.assertRaises(PluginExecutionError, pf.write)
        pf.validate_data.assert_called_with()
        mock_open.assert_called_with(pf.name, "wb")

        # test error from validate_data
        reset()
        pf.validate_data.side_effect = PluginExecutionError
        self.assertRaises(PluginExecutionError, pf.write)
        pf.validate_data.assert_called_with()

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


class TestPropDirectoryBacked(TestDirectoryBacked):
    test_obj = PropDirectoryBacked
    testfiles = ['foo.xml', 'bar.baz.xml']
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
        automatch = Mock()
        automatch.xdata = lxml.etree.Element("Properties", automatch="true")
        automatch.XMLMatch.return_value = "automatch"
        raw = Mock()
        raw.xdata = lxml.etree.Element("Properties")
        raw.XMLMatch.return_value = "raw"
        nevermatch = Mock()
        nevermatch.xdata = lxml.etree.Element("Properties", automatch="false")
        nevermatch.XMLMatch.return_value = "nevermatch"
        p.store.entries = {
            "/foo/automatch.xml": automatch,
            "/foo/raw.xml": raw,
            "/foo/nevermatch.xml": nevermatch,
            }

        # we make copy just return the object it was asked to copy so
        # that we can test the return value of get_additional_data(),
        # which copies every object it doesn't XMLMatch()
        mock_copy.side_effect = lambda o: o

        # test with automatch default to false
        p.core.setup.cfp.getboolean.return_value = False
        metadata = Mock()
        self.assertItemsEqual(p.get_additional_data(metadata),
                              {
                "/foo/automatch.xml": automatch.XMLMatch.return_value,
                "/foo/raw.xml": raw,
                "/foo/nevermatch.xml": nevermatch})
        automatch.XMLMatch.assert_called_with(metadata)
        self.assertFalse(raw.XMLMatch.called)
        self.assertFalse(nevermatch.XMLMatch.called)

        # test with automatch default to true
        p.core.setup.cfp.getboolean.return_value = True
        self.assertItemsEqual(p.get_additional_data(metadata),
                              {
                "/foo/automatch.xml": automatch.XMLMatch.return_value,
                "/foo/raw.xml": raw.XMLMatch.return_value,
                "/foo/nevermatch.xml": nevermatch})
        automatch.XMLMatch.assert_called_with(metadata)
        raw.XMLMatch.assert_called_with(metadata)
        self.assertFalse(nevermatch.XMLMatch.called)
