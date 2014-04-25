""" Bcfg2.Server.Encryption provides a number of convenience methods
for handling encryption in Bcfg2.  See :ref:`server-encryption` for
more details. """

import os
import sys
import copy
import logging
import lxml.etree
import Bcfg2.Logger
import Bcfg2.Options
from M2Crypto import Rand
from M2Crypto.EVP import Cipher, EVPError
from Bcfg2.Utils import safe_input
from Bcfg2.Server import XMLParser
from Bcfg2.Compat import md5, b64encode, b64decode, StringIO

#: Constant representing the encryption operation for
#: :class:`M2Crypto.EVP.Cipher`, which uses a simple integer.  This
#: makes our code more readable.
ENCRYPT = 1

#: Constant representing the decryption operation for
#: :class:`M2Crypto.EVP.Cipher`, which uses a simple integer.  This
#: makes our code more readable.
DECRYPT = 0

#: Default initialization vector.  For best security, you should use a
#: unique IV for each message.  :func:`ssl_encrypt` does this in an
#: automated fashion.
IV = r'\0' * 16


class _OptionContainer(object):
    """ Container for options loaded at import-time to configure
    encryption """
    options = [
        Bcfg2.Options.BooleanOption(
            cf=("encryption", "lax_decryption"),
            help="Decryption failures should cause warnings, not errors"),
        Bcfg2.Options.Option(
            cf=("encryption", "algorithm"), default="aes_256_cbc",
            type=lambda v: v.lower().replace("-", "_"),
            help="The encryption algorithm to use"),
        Bcfg2.Options.Option(
            cf=("encryption", "*"), dest='passphrases', default=dict(),
            help="Encryption passphrases")]


Bcfg2.Options.get_parser().add_component(_OptionContainer)

Rand.rand_seed(os.urandom(1024))


def _cipher_filter(cipher, instr):
    """ M2Crypto reads and writes file-like objects, so this uses
    StringIO to pass data through it """
    inbuf = StringIO(instr)
    outbuf = StringIO()
    while 1:
        buf = inbuf.read()
        if not buf:
            break
        outbuf.write(cipher.update(buf))
    outbuf.write(cipher.final())
    rv = outbuf.getvalue()
    inbuf.close()
    outbuf.close()
    return rv


def str_encrypt(plaintext, key, iv=IV, algorithm=None, salt=None):
    """ Encrypt a string with a key.  For a higher-level encryption
    interface, see :func:`ssl_encrypt`.

    :param plaintext: The plaintext data to encrypt
    :type plaintext: string
    :param key: The key to encrypt the data with
    :type key: string
    :param iv: The initialization vector
    :type iv: string
    :param algorithm: The cipher algorithm to use
    :type algorithm: string
    :param salt: The salt to use
    :type salt: string
    :returns: string - The decrypted data
    """
    if algorithm is None:
        algorithm = Bcfg2.Options.setup.algorithm
    cipher = Cipher(alg=algorithm, key=key, iv=iv, op=ENCRYPT, salt=salt)
    return _cipher_filter(cipher, plaintext)


def str_decrypt(crypted, key, iv=IV, algorithm=None):
    """ Decrypt a string with a key.  For a higher-level decryption
    interface, see :func:`ssl_decrypt`.

    :param crypted: The raw binary encrypted data
    :type crypted: string
    :param key: The encryption key to decrypt with
    :type key: string
    :param iv: The initialization vector
    :type iv: string
    :param algorithm: The cipher algorithm to use
    :type algorithm: string
    :returns: string - The decrypted data
    """
    if algorithm is None:
        algorithm = Bcfg2.Options.setup.algorithm
    cipher = Cipher(alg=algorithm, key=key, iv=iv, op=DECRYPT)
    return _cipher_filter(cipher, crypted)


def ssl_decrypt(data, passwd, algorithm=None):
    """ Decrypt openssl-encrypted data.  This can decrypt data
    encrypted by :func:`ssl_encrypt`, or ``openssl enc``.  It performs
    a base64 decode first if the data is base64 encoded, and
    automatically determines the salt and initialization vector (both
    of which are embedded in the encrypted data).

    :param data: The encrypted data (either base64-encoded or raw
                 binary) to decrypt
    :type data: string
    :param passwd: The password to use to decrypt the data
    :type passwd: string
    :param algorithm: The cipher algorithm to use
    :type algorithm: string
    :returns: string - The decrypted data
    """
    # base64-decode the data
    data = b64decode(data)
    salt = data[8:16]
    # pylint: disable=E1101,E1121
    hashes = [md5(passwd + salt).digest()]
    for i in range(1, 3):
        hashes.append(md5(hashes[i - 1] + passwd + salt).digest())
    # pylint: enable=E1101,E1121
    key = hashes[0] + hashes[1]
    iv = hashes[2]

    return str_decrypt(data[16:], key=key, iv=iv, algorithm=algorithm)


def ssl_encrypt(plaintext, passwd, algorithm=None, salt=None):
    """ Encrypt data in a format that is openssl compatible.

    :param plaintext: The plaintext data to encrypt
    :type plaintext: string
    :param passwd: The password to use to encrypt the data
    :type passwd: string
    :param algorithm: The cipher algorithm to use
    :type algorithm: string
    :param salt: The salt to use.  If none is provided, one will be
                 randomly generated.
    :type salt: bytes
    :returns: string - The base64-encoded, salted, encrypted string.
              The string includes a trailing newline to make it fully
              compatible with openssl command-line tools.
    """
    if salt is None:
        salt = Rand.rand_bytes(8)

    # pylint: disable=E1101,E1121
    hashes = [md5(passwd + salt).digest()]
    for i in range(1, 3):
        hashes.append(md5(hashes[i - 1] + passwd + salt).digest())
    # pylint: enable=E1101,E1121
    key = hashes[0] + hashes[1]
    iv = hashes[2]

    crypted = str_encrypt(plaintext, key=key, salt=salt, iv=iv,
                          algorithm=algorithm)
    return b64encode("Salted__" + salt + crypted) + "\n"


def is_encrypted(val):
    """ Make a best guess if the value is encrypted or not.  This just
    checks to see if ``val`` is a base64-encoded string whose content
    starts with "Salted__", so it may have (rare) false positives.  It
    will not have false negatives. """
    try:
        return b64decode(val).startswith("Salted__")
    except:  # pylint: disable=W0702
        return False


def bruteforce_decrypt(crypted, passphrases=None, algorithm=None):
    """ Convenience method to decrypt the given encrypted string by
    trying the given passphrases or all passphrases sequentially until
    one is found that works.

    :param crypted: The data to decrypt
    :type crypted: string
    :param passphrases: The passphrases to try.
    :type passphrases: list
    :param algorithm: The cipher algorithm to use
    :type algorithm: string
    :returns: string - The decrypted data
    :raises: :class:`M2Crypto.EVP.EVPError`, if the data cannot be decrypted
    """
    if passphrases is None:
        passphrases = Bcfg2.Options.setup.passphrases.values()
    for passwd in passphrases:
        try:
            return ssl_decrypt(crypted, passwd, algorithm=algorithm)
        except EVPError:
            pass
    raise EVPError("Failed to decrypt")


def print_xml(element, keep_text=False):
    """ Render an XML element for error output.  This prefixes the
    line number and removes children for nicer display.

    :param element: The element to render
    :type element: lxml.etree._Element
    :param keep_text: Do not discard text content from the element for
                      display
    :type keep_text: boolean
    """
    xml = None
    if len(element) or element.text:
        el = copy.copy(element)
        if el.text and not keep_text:
            el.text = '...'
        for child in el.iterchildren():
            el.remove(child)
        xml = lxml.etree.tostring(
            el,
            xml_declaration=False).decode("UTF-8").strip()
    else:
        xml = lxml.etree.tostring(
            element,
            xml_declaration=False).decode("UTF-8").strip()
    return "%s (line %s)" % (xml, element.sourceline)


class PassphraseError(Exception):
    """ Exception raised when there's a problem determining the
    passphrase to encrypt or decrypt with """


class DecryptError(Exception):
    """ Exception raised when decryption fails. """


class EncryptError(Exception):
    """ Exception raised when encryption fails. """


class CryptoTool(object):
    """ Generic decryption/encryption interface base object """

    def __init__(self, filename):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.filename = filename
        self.data = open(self.filename).read()
        self.pname, self.passphrase = self._get_passphrase()

    def _get_passphrase(self):
        """ get the passphrase for the current file """
        if not Bcfg2.Options.setup.passphrases:
            raise PassphraseError("No passphrases available in %s" %
                                  Bcfg2.Options.setup.config)

        pname = None
        if Bcfg2.Options.setup.passphrase:
            pname = Bcfg2.Options.setup.passphrase

        if pname:
            try:
                passphrase = Bcfg2.Options.setup.passphrases[pname]
                self.logger.debug("Using passphrase %s specified on command "
                                  "line" % pname)
                return (pname, passphrase)
            except KeyError:
                raise PassphraseError("Could not find passphrase %s in %s" %
                                      (pname, Bcfg2.Options.setup.config))
        else:
            if len(Bcfg2.Options.setup.passphrases) == 1:
                pname, passphrase = Bcfg2.Options.setup.passphrases.items()[0]
                self.logger.info("Using passphrase %s" % pname)
                return (pname, passphrase)
            elif len(Bcfg2.Options.setup.passphrases) > 1:
                return (None, None)
        raise PassphraseError("No passphrase could be determined")

    def get_destination_filename(self, original_filename):
        """ Get the filename where data should be written """
        return original_filename

    def write(self, data):
        """ write data to disk """
        new_fname = self.get_destination_filename(self.filename)
        try:
            self._write(new_fname, data)
            self.logger.info("Wrote data to %s" % new_fname)
            return True
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Error writing data from %s to %s: %s" %
                              (self.filename, new_fname, err))
            return False

    def _write(self, filename, data):
        """ Perform the actual write of data.  This is separate from
        :func:`CryptoTool.write` so it can be easily
        overridden. """
        open(filename, "wb").write(data)


class Decryptor(CryptoTool):
    """ Decryptor interface """
    def decrypt(self):
        """ decrypt the file, returning the encrypted data """
        raise NotImplementedError


class Encryptor(CryptoTool):
    """ encryptor interface """
    def encrypt(self):
        """ encrypt the file, returning the encrypted data """
        raise NotImplementedError


class CfgEncryptor(Encryptor):
    """ encryptor class for Cfg files """

    def __init__(self, filename):
        Encryptor.__init__(self, filename)
        if self.passphrase is None:
            raise PassphraseError("Multiple passphrases found in %s, "
                                  "specify one on the command line with -p" %
                                  Bcfg2.Options.setup.config)

    def encrypt(self):
        if is_encrypted(self.data):
            raise EncryptError("Data is alraedy encrypted")
        return ssl_encrypt(self.data, self.passphrase)

    def get_destination_filename(self, original_filename):
        return original_filename + ".crypt"


class CfgDecryptor(Decryptor):
    """ Decrypt Cfg files """

    def decrypt(self):
        """ decrypt the given file, returning the plaintext data """
        if self.passphrase:
            try:
                return ssl_decrypt(self.data, self.passphrase)
            except EVPError:
                raise DecryptError("Could not decrypt %s with the "
                                   "specified passphrase" % self.filename)
            except:
                raise DecryptError("Error decrypting %s: %s" %
                                   (self.filename, sys.exc_info()[1]))
        else:  # no passphrase given, brute force
            try:
                return bruteforce_decrypt(self.data)
            except EVPError:
                raise DecryptError("Could not decrypt %s with any passphrase" %
                                   self.filename)

    def get_destination_filename(self, original_filename):
        if original_filename.endswith(".crypt"):
            return original_filename[:-6]
        else:
            return Decryptor.get_destination_filename(self, original_filename)


class PropertiesCryptoMixin(object):
    """ Mixin to provide some common methods for Properties crypto """
    default_xpath = '//*[@encrypted]'

    def _get_elements(self, xdata):
        """ Get the list of elements to encrypt or decrypt """
        if Bcfg2.Options.setup.xpath:
            elements = xdata.xpath(Bcfg2.Options.setup.xpath)
            if not elements:
                self.logger.warning("XPath expression %s matched no elements" %
                                    Bcfg2.Options.setup.xpath)
        else:
            elements = xdata.xpath(self.default_xpath)
            if not elements:
                elements = list(xdata.getiterator(tag=lxml.etree.Element))

        # filter out elements without text data
        for el in elements[:]:
            if not el.text:
                elements.remove(el)

        if Bcfg2.Options.setup.interactive:
            for element in elements[:]:
                if len(element):
                    elt = copy.copy(element)
                    for child in elt.iterchildren():
                        elt.remove(child)
                else:
                    elt = element
                print(lxml.etree.tostring(
                    elt,
                    xml_declaration=False).decode("UTF-8").strip())
                ans = safe_input("Encrypt this element? [y/N] ")
                if not ans.lower().startswith("y"):
                    elements.remove(element)
        return elements

    def _get_element_passphrase(self, element):
        """ Get the passphrase to use to encrypt or decrypt a given
        element """
        pname = element.get("encrypted")
        if pname in Bcfg2.Options.setup.passphrases:
            passphrase = Bcfg2.Options.setup.passphrases[pname]
        else:
            if pname:
                self.logger.warning("Passphrase %s not found in %s, "
                                    "using passphrase given on command line" %
                                    (pname, Bcfg2.Options.setup.config))
            if self.passphrase:
                passphrase = self.passphrase
                pname = self.pname
            else:
                self.logger.warning("No passphrase specified for %s element" %
                                    element.tag)
                raise PassphraseError("Multiple passphrases found in %s, "
                                      "specify one on the command line with "
                                      "-p" % Bcfg2.Options.setup.config)
        return (pname, passphrase)

    def _write(self, filename, data):
        """ Write the data """
        data.getroottree().write(filename,
                                 xml_declaration=False,
                                 pretty_print=True)


class PropertiesEncryptor(Encryptor, PropertiesCryptoMixin):
    """ encryptor class for Properties files """

    def encrypt(self):
        xdata = lxml.etree.XML(self.data, parser=XMLParser)
        for elt in self._get_elements(xdata):
            if is_encrypted(elt.text):
                raise EncryptError("Element is already encrypted: %s" %
                                   print_xml(elt))
            try:
                pname, passphrase = self._get_element_passphrase(elt)
            except PassphraseError:
                raise EncryptError(str(sys.exc_info()[1]))
            self.logger.debug("Encrypting %s" % print_xml(elt))
            elt.text = ssl_encrypt(elt.text, passphrase).strip()
            elt.set("encrypted", pname)
        return xdata

    def _write(self, filename, data):
        PropertiesCryptoMixin._write(self, filename, data)


class PropertiesDecryptor(Decryptor, PropertiesCryptoMixin):
    """ decryptor class for Properties files """

    def decrypt(self):
        decrypted_any = False
        xdata = lxml.etree.XML(self.data, parser=XMLParser)
        for elt in self._get_elements(xdata):
            try:
                pname, passphrase = self._get_element_passphrase(elt)
            except PassphraseError:
                raise DecryptError(str(sys.exc_info()[1]))
            self.logger.debug("Decrypting %s" % print_xml(elt))
            try:
                decrypted = ssl_decrypt(elt.text, passphrase).strip()
                elt.text = decrypted.encode('ascii', 'xmlcharrefreplace')
                elt.set("encrypted", pname)
                decrypted_any = True
            except (EVPError, TypeError):
                self.logger.error("Could not decrypt %s, skipping" %
                                  print_xml(elt))
            except UnicodeDecodeError:
                # we managed to decrypt the value, but it contains
                # content that can't even be encoded into xml
                # entities.  what probably happened here is that we
                # coincidentally could decrypt a value encrypted with
                # a different key, and wound up with gibberish.
                self.logger.warning("Decrypted %s to gibberish, skipping" %
                                    elt.tag)
        if decrypted_any:
            return xdata
        else:
            raise DecryptError("Failed to decrypt any data in %s" %
                               self.filename)

    def _write(self, filename, data):
        PropertiesCryptoMixin._write(self, filename, data)


class CLI(object):
    """ The bcfg2-crypt CLI """

    options = [
        Bcfg2.Options.ExclusiveOptionGroup(
            Bcfg2.Options.BooleanOption(
                "--encrypt", help='Encrypt the specified file'),
            Bcfg2.Options.BooleanOption(
                "--decrypt", help='Decrypt the specified file')),
        Bcfg2.Options.BooleanOption(
            "--stdout",
            help='Decrypt or encrypt the specified file to stdout'),
        Bcfg2.Options.Option(
            "-p", "--passphrase", metavar="NAME",
            help='Encryption passphrase name'),
        Bcfg2.Options.ExclusiveOptionGroup(
            Bcfg2.Options.BooleanOption(
                "--properties",
                help='Encrypt the specified file as a Properties file'),
            Bcfg2.Options.BooleanOption(
                "--cfg", help='Encrypt the specified file as a Cfg file')),
        Bcfg2.Options.OptionGroup(
            Bcfg2.Options.Common.interactive,
            Bcfg2.Options.Option(
                "--xpath",
                help='XPath expression to select elements to encrypt'),
            title="Options for handling Properties files"),
        Bcfg2.Options.OptionGroup(
            Bcfg2.Options.BooleanOption(
                "--remove", help='Remove the plaintext file after encrypting'),
            title="Options for handling Cfg files"),
        Bcfg2.Options.PathOption(
            "files", help="File(s) to encrypt or decrypt", nargs='+')]

    def __init__(self, argv=None):
        parser = Bcfg2.Options.get_parser(
            description="Encrypt and decrypt Bcfg2 data",
            components=[self, _OptionContainer])
        parser.parse(argv=argv)
        self.logger = logging.getLogger(parser.prog)

        if Bcfg2.Options.setup.decrypt:
            if Bcfg2.Options.setup.remove:
                self.logger.error("--remove cannot be used with --decrypt, "
                                  "ignoring --remove")
                Bcfg2.Options.setup.remove = False
            elif Bcfg2.Options.setup.interactive:
                self.logger.error("Cannot decrypt interactively")
                Bcfg2.Options.setup.interactive = False

    def _is_properties(self, filename):
        """ Determine if a given file is a Properties file or not """
        if Bcfg2.Options.setup.properties:
            return True
        elif Bcfg2.Options.setup.cfg:
            return False
        elif filename.endswith(".xml"):
            try:
                xroot = lxml.etree.parse(filename).getroot()
                return xroot.tag == "Properties"
            except lxml.etree.XMLSyntaxError:
                return False
        else:
            return False

    def run(self):  # pylint: disable=R0912,R0915
        """ Run bcfg2-crypt """
        for fname in Bcfg2.Options.setup.files:
            if not os.path.exists(fname):
                self.logger.error("%s does not exist, skipping" % fname)
                continue

            # figure out if we need to encrypt this as a Properties file
            # or as a Cfg file
            try:
                props = self._is_properties(fname)
            except IOError:
                err = sys.exc_info()[1]
                self.logger.error("Error reading %s, skipping: %s" %
                                  (fname, err))
                continue

            if props:
                ftype = "Properties"
                if Bcfg2.Options.setup.remove:
                    self.logger.info("Cannot use --remove with Properties "
                                     "file %s, ignoring for this file" % fname)
                tools = (PropertiesEncryptor, PropertiesDecryptor)
            else:
                ftype = "Cfg"
                if Bcfg2.Options.setup.xpath:
                    self.logger.error("Specifying --xpath with --cfg is "
                                      "nonsensical, ignoring --xpath")
                    Bcfg2.Options.setup.xpath = None
                if Bcfg2.Options.setup.interactive:
                    self.logger.error("Cannot use interactive mode with "
                                      "--cfg, ignoring --interactive")
                    Bcfg2.Options.setup.interactive = False
                tools = (CfgEncryptor, CfgDecryptor)

            data = None
            mode = None
            if Bcfg2.Options.setup.encrypt:
                try:
                    tool = tools[0](fname)
                except PassphraseError:
                    self.logger.error(str(sys.exc_info()[1]))
                    continue
                except IOError:
                    self.logger.error("Error reading %s, skipping: %s" %
                                      (fname, err))
                    continue
                mode = "encrypt"
                self.logger.debug("Encrypting %s file %s" % (ftype, fname))
            elif Bcfg2.Options.setup.decrypt:
                try:
                    tool = tools[1](fname)
                except PassphraseError:
                    self.logger.error(str(sys.exc_info()[1]))
                    continue
                except IOError:
                    self.logger.error("Error reading %s, skipping: %s" %
                                      (fname, err))
                    continue
                mode = "decrypt"
                self.logger.debug("Decrypting %s file %s" % (ftype, fname))
            else:
                self.logger.info("Neither --encrypt nor --decrypt specified, "
                                 "determining mode")
                try:
                    tool = tools[1](fname)
                except PassphraseError:
                    self.logger.error(str(sys.exc_info()[1]))
                    continue
                except IOError:
                    self.logger.error("Error reading %s, skipping: %s" %
                                      (fname, err))
                    continue
                try:
                    self.logger.debug("Trying to decrypt %s file %s" % (ftype,
                                                                        fname))
                    data = tool.decrypt()
                    mode = "decrypt"
                    self.logger.debug("Decrypted %s file %s" % (ftype, fname))
                except DecryptError:
                    self.logger.info("Failed to decrypt %s, trying encryption"
                                     % fname)
                    try:
                        tool = tools[0](fname)
                    except PassphraseError:
                        self.logger.error(str(sys.exc_info()[1]))
                        continue
                    except IOError:
                        self.logger.error("Error reading %s, skipping: %s" %
                                          (fname, err))
                        continue
                    mode = "encrypt"
                    self.logger.debug("Encrypting %s file %s" % (ftype, fname))

            if data is None:
                try:
                    data = getattr(tool, mode)()
                except (EncryptError, DecryptError):
                    self.logger.error("Failed to %s %s, skipping: %s" %
                                      (mode, fname, sys.exc_info()[1]))
                    continue
            if Bcfg2.Options.setup.stdout:
                if len(Bcfg2.Options.setup.files) > 1:
                    print("----- %s -----" % fname)
                print(data)
                if len(Bcfg2.Options.setup.files) > 1:
                    print("")
            else:
                tool.write(data)

            if (Bcfg2.Options.setup.remove and
                    tool.get_destination_filename(fname) != fname):
                try:
                    os.unlink(fname)
                except IOError:
                    err = sys.exc_info()[1]
                    self.logger.error("Error removing %s: %s" % (fname, err))
                    continue
