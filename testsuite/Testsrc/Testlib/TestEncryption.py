# -*- coding: utf-8 -*-
import os
import sys
from Bcfg2.Compat import b64decode
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
    from Bcfg2.Encryption import *

    class TestEncryption(Bcfg2TestCase):
        plaintext = """foo bar
baz
ö
\t\tquux
""" + "a" * 16384  # 16K is completely arbitrary
        iv = "0123456789ABCDEF"
        salt = "01234567"
        algo = "des_cbc"

        def test_str_crypt(self):
            """ test str_encrypt/str_decrypt """
            key = "a simple key"

            # simple symmetrical test with no options
            crypted = str_encrypt(self.plaintext, key)
            self.assertEqual(self.plaintext, str_decrypt(crypted, key))

            # symmetrical test with lots of options
            crypted = str_encrypt(self.plaintext, key,
                                  iv=self.iv, salt=self.salt,
                                  algorithm=self.algo)
            self.assertEqual(self.plaintext,
                             str_decrypt(crypted, key, iv=self.iv,
                                         algorithm=self.algo))

            # test that different algorithms are actually used
            self.assertNotEqual(str_encrypt(self.plaintext, key),
                                str_encrypt(self.plaintext, key,
                                            algorithm=self.algo))

            # test that different keys are actually used
            self.assertNotEqual(str_encrypt(self.plaintext, key),
                                str_encrypt(self.plaintext, "different key"))

            # test that different IVs are actually used
            self.assertNotEqual(str_encrypt(self.plaintext, key, iv=self.iv),
                                str_encrypt(self.plaintext, key))

            # test that errors are raised on bad decrypts
            crypted = str_encrypt(self.plaintext, key, algorithm=self.algo)
            self.assertRaises(EVPError, str_decrypt,
                              crypted, "bogus key", algorithm=self.algo)
            self.assertRaises(EVPError, str_decrypt,
                              crypted, key)  # bogus algorithm

        def test_ssl_crypt(self):
            """ test ssl_encrypt/ssl_decrypt """
            passwd = "a simple passphrase"

            # simple symmetrical test
            crypted = ssl_encrypt(self.plaintext, passwd)
            self.assertEqual(self.plaintext, ssl_decrypt(crypted, passwd))

            # more complex symmetrical test
            crypted = ssl_encrypt(self.plaintext, passwd, algorithm=self.algo,
                                  salt=self.salt)
            self.assertEqual(self.plaintext,
                             ssl_decrypt(crypted, passwd, algorithm=self.algo))

            # test that different algorithms are actually used
            self.assertNotEqual(ssl_encrypt(self.plaintext, passwd),
                                ssl_encrypt(self.plaintext, passwd,
                                            algorithm=self.algo))

            # test that different passwords are actually used
            self.assertNotEqual(ssl_encrypt(self.plaintext, passwd),
                                ssl_encrypt(self.plaintext, "different pass"))

            # there's no reasonable test we can do to see if the
            # output is base64-encoded, unfortunately, but if it's
            # obviously not we fail
            crypted = ssl_encrypt(self.plaintext, passwd)
            self.assertRegexpMatches(crypted, r'^[A-Za-z0-9+/]+[=]{0,2}$')

            # test that errors are raised on bad decrypts
            crypted = ssl_encrypt(self.plaintext, passwd,
                                  algorithm=self.algo)
            self.assertRaises(EVPError, ssl_decrypt,
                              crypted, "bogus passwd", algorithm=self.algo)
            self.assertRaises(EVPError, ssl_decrypt,
                              crypted, passwd)  # bogus algorithm

        def test_get_algorithm(self):
            setup = Mock()
            # we don't care what the default is, as long as there is
            # one
            setup.cfp.get.return_value = ALGORITHM
            self.assertRegexpMatches(get_algorithm(setup),
                                     r'^[a-z0-9]+_[a-z0-9_]+$')
            setup.cfp.get.assert_called_with(CFG_SECTION, CFG_ALGORITHM,
                                             default=ALGORITHM)

            setup.cfp.get.return_value = self.algo
            self.assertEqual(get_algorithm(setup), self.algo)
            setup.cfp.get.assert_called_with(CFG_SECTION, CFG_ALGORITHM,
                                             default=ALGORITHM)

            # test that get_algorithm converts algorithms given in
            # OpenSSL style to M2Crypto style
            setup.cfp.get.return_value = "DES-EDE3-CFB8"
            self.assertEqual(get_algorithm(setup), "des_ede3_cfb8")
            setup.cfp.get.assert_called_with(CFG_SECTION, CFG_ALGORITHM,
                                             default=ALGORITHM)

        def test_get_passphrases(self):
            setup = Mock()
            setup.cfp.has_section.return_value = False
            self.assertEqual(get_passphrases(setup), dict())

            setup.cfp.has_section.return_value = True
            setup.cfp.options.return_value = ["foo", "bar", CFG_ALGORITHM]
            setup.cfp.get.return_value = "passphrase"
            self.assertItemsEqual(get_passphrases(setup),
                                  dict(foo="passphrase",
                                       bar="passphrase"))

        @patch("Bcfg2.Encryption.get_passphrases")
        def test_bruteforce_decrypt(self, mock_passphrases):
            passwd = "a simple passphrase"
            crypted = ssl_encrypt(self.plaintext, passwd)
            setup = Mock()

            # test with no passphrases given nor in config
            mock_passphrases.return_value = dict()
            self.assertRaises(EVPError,
                              bruteforce_decrypt,
                              crypted, setup=setup)
            mock_passphrases.assert_called_with(setup)

            # test with good passphrase given in function call
            mock_passphrases.reset_mock()
            self.assertEqual(self.plaintext,
                             bruteforce_decrypt(crypted,
                                                passphrases=["bogus pass",
                                                             passwd,
                                                             "also bogus"]))
            self.assertFalse(mock_passphrases.called)

            # test with no good passphrase given nor in config
            mock_passphrases.reset_mock()
            self.assertRaises(EVPError,
                              bruteforce_decrypt,
                              crypted, passphrases=["bogus", "also bogus"])
            self.assertFalse(mock_passphrases.called)

            # test with good passphrase in config file
            mock_passphrases.reset_mock()
            mock_passphrases.return_value = dict(bogus="bogus",
                                                 real=passwd,
                                                 bogus2="also bogus")
            self.assertEqual(self.plaintext,
                             bruteforce_decrypt(crypted, setup=setup))
            mock_passphrases.assert_called_with(setup)

            # test that passphrases given in function call take
            # precedence over config
            mock_passphrases.reset_mock()
            self.assertRaises(EVPError,
                              bruteforce_decrypt,
                              crypted, setup=setup,
                              passphrases=["bogus", "also bogus"])
            self.assertFalse(mock_passphrases.called)

            # test that different algorithms are used
            mock_passphrases.reset_mock()
            self.assertRaises(EVPError,
                              bruteforce_decrypt,
                              crypted, setup=setup, algorithm=self.algo)

            mock_passphrases.reset_mock()
            crypted = ssl_encrypt(self.plaintext, passwd, algorithm=self.algo)
            self.assertEqual(self.plaintext,
                             bruteforce_decrypt(crypted, setup=setup,
                                                algorithm=self.algo))

except ImportError:
    pass
