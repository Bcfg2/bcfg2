# -*- coding: utf-8 -*-
import os
import sys
import shutil
import difflib
import tempfile
import lxml.etree
import Bcfg2.Options
from Bcfg2.Compat import StringIO, b64decode, u_str
from mock import Mock, MagicMock, patch

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

try:
    from Bcfg2.Server.Encryption import CLI
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class TestEncryption(Bcfg2TestCase):
    cfg_plaintext = None
    known_files = None
    basedir = None

    @classmethod
    def setUpClass(cls):
        basedir = os.path.join(os.path.dirname(__file__), "bcfg2-crypt")
        cls.basedir = tempfile.mkdtemp()
        for fname in os.listdir(basedir):
            shutil.copy(os.path.join(basedir, fname), cls.basedir)
        cls.known_files = os.listdir(cls.basedir)
        cls.cfg_plaintext = open(os.path.join(cls.basedir, "plaintext")).read()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.basedir)

    @skipUnless(HAS_CRYPTO, "Encryption libraries not found")
    def setUp(self):
        set_setup_default("lax_decryption", False)

    def set_options(self):
        Bcfg2.Options.setup.algorithm = "aes_256_cbc"
        Bcfg2.Options.setup.passphrases = dict(
            basic="basic",
            complex="1234567890əùíÿł¢€ñû⸘" * 10)

    def tearDown(self):
        # clean up stray files created by tests
        for fname in os.listdir(self.basedir):
            if fname not in self.known_files:
                os.unlink(os.path.join(self.basedir, fname))

    def assertExists(self, fname):
        fpath = os.path.join(self.basedir, fname)
        self.assertTrue(os.path.exists(fpath),
                        "%s does not exist" % fpath)

    def assertNotExists(self, fname):
        fpath = os.path.join(self.basedir, fname)
        self.assertFalse(os.path.exists(fpath),
                        "%s exists, but shouldn't" % fpath)

    def assertFilesEqual(self, fname1, fname2):
        self.assertExists(fname1)
        self.assertExists(fname2)
        contents1 = open(os.path.join(self.basedir, fname1)).read().strip()
        contents2 = open(os.path.join(self.basedir, fname2)).read().strip()
        diff = "\n".join(
            difflib.unified_diff(contents1.splitlines(),
                                 contents2.splitlines(),
                                 fname1, fname2)).replace("\n\n", "\n")
        self.assertEqual(contents1, contents2,
                         "Contents of %s and %s do not match:\n%s" %
                         (fname1, fname2, diff))

    def assertFilesNotEqual(self, fname1, fname2):
        self.assertExists(fname1)
        self.assertExists(fname2)
        self.assertNotEqual(
            open(os.path.join(self.basedir, fname1)).read(),
            open(os.path.join(self.basedir, fname2)).read(),
            "Contents of %s and %s are unexpectedly identical")

    def _is_encrypted(self, data):
        """ Pretty crappy check for whether or not data is encrypted:
        just see if it's a valid base64-encoded string whose contents
        start with "Salted__".  But without decrypting, which rather
        begs the question in a set of crypto unit tests, I'm not sure
        how to do a better test."""
        try:
            return b64decode(data).startswith("Salted__")
        except UnicodeDecodeError:
            # decoded base64, resulting value contained non-ASCII text
            return True
        except TypeError:
            # couldn't decode base64
            return False

    def assertIsEncrypted(self, data):
        if not self._is_encrypted(data):
            self.fail("Data is not encrypted: %s" % data)

    def assertNotEncrypted(self, data):
        if self._is_encrypted(data):
            self.fail("Data is unexpectedly encrypted: %s" % data)

    def _decrypt(self, cli, outfile, expected=None):
        self.set_options()
        cli.run()
        if expected is None:
            self.assertExists(outfile)
            actual = open(os.path.join(self.basedir, outfile)).read()
            self.assertEqual(self.cfg_plaintext, actual)
            self.assertNotEncrypted(actual)
        else:
            self.assertFilesEqual(outfile, expected)

    def _encrypt(self, cli, outfile, original=None):
        self.set_options()
        cli.run()
        if original is None:
            self.assertExists(outfile)
            actual = open(os.path.join(self.basedir, outfile)).read()
            self.assertNotEqual(self.cfg_plaintext, actual)
            self.assertIsEncrypted(actual)
        else:
            self.assertFilesNotEqual(outfile, original)

    def _cfg_decrypt(self, opts, encrypted):
        if encrypted.endswith(".crypt"):
            decrypted = encrypted[:-6]
        else:
            self.fail("Could not determine decrypted filename for %s" %
                      encrypted)
        cli = CLI(opts + [os.path.join(self.basedir, encrypted)])
        self._decrypt(cli, decrypted)

    def _cfg_encrypt(self, opts, plaintext):
        cli = CLI(opts + [os.path.join(self.basedir, plaintext)])
        self._encrypt(cli, plaintext + ".crypt")

    def _props_decrypt(self, opts, encrypted, expected):
        test = os.path.join(self.basedir, "test.xml")
        shutil.copy(os.path.join(self.basedir, encrypted), test)
        cli = CLI(opts + [test])
        self._decrypt(cli, "test.xml", expected)
        try:
            xdata = lxml.etree.parse(test)
        except:
            self.fail("Could not parse decrypted Properties file: %s" %
                      sys.exc_info()[1])
        for el in xdata.iter():
            if el.tag is not lxml.etree.Comment and el.text.strip():
                self.assertNotEncrypted(el.text)

    def _props_encrypt(self, opts, plaintext, check_all=True):
        test = os.path.join(self.basedir, "test.xml")
        shutil.copy(os.path.join(self.basedir, plaintext), test)
        cli = CLI(opts + [test])
        self._encrypt(cli, "test.xml", plaintext)
        try:
            xdata = lxml.etree.parse(test)
        except:
            self.fail("Could not parse encrypted Properties file: %s" %
                      sys.exc_info()[1])
        if check_all:
            for el in xdata.iter():
                if el.tag is not lxml.etree.Comment and el.text.strip():
                    self.assertIsEncrypted(el.text)

    def test_decrypt_cfg(self):
        """ Decrypt a Cfg file """
        self._cfg_decrypt(["--decrypt", "--cfg", "-p", "basic"],
                          "basic.crypt")

    def test_decrypt_cfg_complex(self):
        """ Decrypt a Cfg file with a passphrase with special characters """
        self._cfg_decrypt(["--decrypt", "--cfg", "-p", "complex"],
                          "complex.crypt")

    def test_decrypt_cfg_algorithm(self):
        """ Decrypt a Cfg file with a non-default algorithm """
        # this can't be done with self._cfg_decrypt or even
        # self._decrypt because we have to set the algorithm after
        # other options are set, but before the decrypt is performed
        cli = CLI(["--decrypt", "--cfg", "-p", "basic",
                   os.path.join(self.basedir, "basic-des-cbc.crypt")])
        self.set_options()
        Bcfg2.Options.setup.algorithm = "des_cbc"
        cli.run()
        self.assertExists("basic-des-cbc")
        actual = open(os.path.join(self.basedir, "basic-des-cbc")).read()
        self.assertEqual(self.cfg_plaintext, actual)
        self.assertNotEncrypted(actual)

    def test_cfg_auto_passphrase(self):
        """ Discover the passphrase to decrypt a Cfg file"""
        self._cfg_decrypt(["--decrypt", "--cfg"], "complex.crypt")

    def test_cfg_auto_mode(self):
        """ Discover whether to encrypt or decrypt a Cfg file """
        self._cfg_decrypt(["--cfg", "-p", "basic"], "basic.crypt")
        self._cfg_encrypt(["--cfg", "-p", "basic"], "plaintext")

    def test_cfg_auto_type(self):
        """ Discover a file is a Cfg file """
        self._cfg_decrypt(["--decrypt", "-p", "basic"], "basic.crypt")
        self._cfg_encrypt(["--encrypt", "-p", "basic"], "plaintext")

    def test_cfg_multiple(self):
        """ Decrypt multiple Cfg files """
        cli = CLI(["--decrypt", "--cfg", "-p", "basic",
                   os.path.join(self.basedir, "basic.crypt"),
                   os.path.join(self.basedir, "basic2.crypt")])
        self.set_options()
        cli.run()
        self.assertExists("basic")
        self.assertExists("basic2")
        actual1 = open(os.path.join(self.basedir, "basic")).read()
        actual2 = open(os.path.join(self.basedir, "basic2")).read()
        self.assertEqual(self.cfg_plaintext, actual1)
        self.assertEqual(self.cfg_plaintext, actual2)
        self.assertNotEncrypted(actual1)
        self.assertNotEncrypted(actual2)

    def test_cfg_auto_all(self):
        """ Discover all options to encrypt/decrypt Cfg files """
        self._cfg_decrypt([], "complex.crypt")
        self._cfg_encrypt(["-p", "basic"], "plaintext")

    def test_cfg_stdout(self):
        """ Decrypt a Cfg file to stdout """
        cli = CLI(["--decrypt", "--cfg", "-p", "basic", "--stdout",
                   os.path.join(self.basedir, "basic.crypt")])
        self.set_options()
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        cli.run()
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        self.assertNotExists("basic")
        self.assertEqual(self.cfg_plaintext.strip(), output.strip())
        self.assertNotEncrypted(output)

    def test_encrypt_cfg(self):
        """ Encrypt a Cfg file """
        self._cfg_encrypt(["--encrypt", "--cfg", "-p", "basic"], "plaintext")
        os.rename(os.path.join(self.basedir, "plaintext.crypt"),
                  os.path.join(self.basedir, "test.crypt"))
        self._cfg_decrypt(["--decrypt", "--cfg", "-p", "basic"],
                          "test.crypt")

    def test_encrypt_props_as_cfg(self):
        """ Encrypt an XML file as a Cfg file """
        cli = CLI(["--encrypt", "--cfg", "-p", "basic",
                   os.path.join(self.basedir, "plaintext.xml")])
        self._encrypt(cli, "plaintext.xml.crypt", "plaintext.xml")

        os.rename(os.path.join(self.basedir, "plaintext.xml.crypt"),
                  os.path.join(self.basedir, "test.xml.crypt"))
        cli = CLI(["--decrypt", "--cfg", "-p", "basic",
                   os.path.join(self.basedir, "test.xml.crypt")])
        self._decrypt(cli, "test.xml", "plaintext.xml")

    def test_cfg_remove(self):
        """ Encrypt and remove a Cfg file """
        test = os.path.join(self.basedir, "test")
        shutil.copy(os.path.join(self.basedir, "plaintext"), test)
        self._cfg_encrypt(["--encrypt", "--remove", "--cfg", "-p", "basic"],
                          test)
        self.assertNotExists("test")

    def test_decrypt_props(self):
        """ Decrypt a Properties file """
        self._props_decrypt(["--decrypt", "--properties", "-p", "basic"],
                            "all-basic.xml", "plaintext2.xml")

    def test_props_decrypt_multiple_passphrases(self):
        """ Decrypt a Properties file with multiple passphrases"""
        self._props_decrypt(["--decrypt", "--properties"],
                            "plaintext-all.xml", "plaintext.xml")

    def test_props_decrypt_mixed(self):
        """ Decrypt a Properties file with mixed encrypted content"""
        self._props_decrypt(["--decrypt", "--properties"],
                            "plaintext-xpath.xml", "plaintext.xml")

    def test_props_decrypt_bogus(self):
        """ Decrypt a malformed Properties file """
        self._props_decrypt(["--decrypt", "--properties"],
                            "bogus-forced.xml", "bogus.xml")

    def test_props_decrypt_auto_type(self):
        """ Discover an encrypted file is a Properties file """
        self._props_decrypt(["--decrypt"],
                            "all-basic.xml", "plaintext2.xml")

    def test_props_decrypt_auto_mode(self):
        """ Discover whether to encrypt or decrypt an encrypted Properties file """
        self._props_decrypt(["--properties"],
                            "all-basic.xml", "plaintext2.xml")

    def test_props_decrypt_auto_all(self):
        """ Discover all options to decrypt a Properties file """
        self._props_decrypt([], "all-basic.xml", "plaintext2.xml")

    def test_props_encrypt_cli_passphrase(self):
        """ Encrypt a Properties file with passphrase on the CLI"""
        self._props_encrypt(["--encrypt", "--properties", "-p", "basic"],
                            "plaintext2.xml")
        os.rename(os.path.join(self.basedir, "test.xml"),
                  os.path.join(self.basedir, "encrypted.xml"))
        self._props_decrypt(["--decrypt", "--properties", "-p", "basic"],
                            "encrypted.xml", "plaintext2.xml")

    def test_props_encrypt_file_passphrase(self):
        """ Encrypt a Properties file with passphrase in the file """
        self._props_encrypt(["--encrypt", "--properties"], "plaintext2.xml")
        os.rename(os.path.join(self.basedir, "test.xml"),
                  os.path.join(self.basedir, "encrypted.xml"))
        self._props_decrypt(["--decrypt", "--properties"],
                            "encrypted.xml", "plaintext2.xml")

    def test_props_encrypt_multiple_passphrases(self):
        """ Encrypt a Properties file with multiple passphrases """
        self._props_encrypt(["--encrypt", "--properties"], "plaintext.xml")
        os.rename(os.path.join(self.basedir, "test.xml"),
                  os.path.join(self.basedir, "encrypted.xml"))
        self._props_decrypt(["--decrypt", "--properties"],
                            "encrypted.xml", "plaintext.xml")

    def test_props_encrypt_xpath(self):
        """ Encrypt a Properties file with --xpath """
        test = os.path.join(self.basedir, "test.xml")
        self._props_encrypt(["--encrypt", "--properties", "--xpath", "//Foo"],
                            "plaintext.xml", check_all=False)
        xdata = lxml.etree.parse(test)
        for el in xdata.iter():
            if el.tag is not lxml.etree.Comment and el.text.strip():
                if el.tag == "Foo":
                    self.assertIsEncrypted(el.text)
                else:
                    self.assertNotEncrypted(el.text)

        os.rename(test, os.path.join(self.basedir, "encrypted.xml"))
        self._props_decrypt(["--decrypt", "--properties"],
                            "encrypted.xml", "plaintext.xml")

    def test_props_encrypt_bogus(self):
        """ Decrypt a malformed Properties file """
        self._props_encrypt(["--encrypt", "--properties"], "bogus.xml")
        os.rename(os.path.join(self.basedir, "test.xml"),
                  os.path.join(self.basedir, "encrypted.xml"))
        self._props_decrypt(["--decrypt", "--properties"],
                            "encrypted.xml", "bogus.xml")

    def test_props_encrypt_auto_type(self):
        """ Discover if a file is a Properties file """
        self._props_encrypt(["--encrypt"], "plaintext2.xml")
        os.rename(os.path.join(self.basedir, "test.xml"),
                  os.path.join(self.basedir, "encrypted.xml"))
        self._props_decrypt(["--decrypt"],
                            "encrypted.xml", "plaintext2.xml")

    def test_props_encrypt_auto_mode(self):
        """ Discover whether to encrypt or decrypt a Properties file """
        self._props_encrypt(["--properties"], "plaintext2.xml")
        os.rename(os.path.join(self.basedir, "test.xml"),
                  os.path.join(self.basedir, "encrypted.xml"))
        self._props_decrypt(["--properties"],
                            "encrypted.xml", "plaintext2.xml")

    def test_props_encrypt_auto_all(self):
        """ Discover all options to encrypt a Properties file """
        self._props_encrypt([], "plaintext.xml")
        os.rename(os.path.join(self.basedir, "test.xml"),
                  os.path.join(self.basedir, "encrypted.xml"))
        self._props_decrypt([], "encrypted.xml", "plaintext.xml")
