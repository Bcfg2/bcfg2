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


class EncryptionChunkingError(Exception):
    """ error raised when Encryptor cannot break a file up into chunks
    to be encrypted, or cannot reassemble the chunks """
    pass


class Encryptor(object):
    """ Generic encryptor for all files """

    def __init__(self):
        self.passphrase = None
        self.pname = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_encrypted_filename(self, plaintext_filename):
        """ get the name of the file encrypted data should be written to """
        return plaintext_filename

    def get_plaintext_filename(self, encrypted_filename):
        """ get the name of the file decrypted data should be written to """
        return encrypted_filename

    def chunk(self, data):
        """ generator to break the file up into smaller chunks that
        will each be individually encrypted or decrypted """
        yield data

    def unchunk(self, data, original):  # pylint: disable=W0613
        """ given chunks of a file, reassemble then into the whole file """
        try:
            return data[0]
        except IndexError:
            raise EncryptionChunkingError("No data to unchunk")

    def set_passphrase(self):
        """ set the passphrase for the current file """
        if not Bcfg2.Options.setup.passphrases:
            self.logger.error("No passphrases available in %s" %
                              Bcfg2.Options.setup.config)
            return False

        if self.passphrase:
            self.logger.debug("Using previously determined passphrase %s" %
                              self.pname)
            return True

        if Bcfg2.Options.setup.passphrase:
            self.pname = Bcfg2.Options.setup.passphrase

        if self.pname:
            try:
                self.passphrase = Bcfg2.Options.setup.passphrases[self.pname]
                self.logger.debug("Using passphrase %s specified on command "
                                  "line" % self.pname)
                return True
            except KeyError:
                self.logger.error("Could not find passphrase %s in %s" %
                                  (self.pname, Bcfg2.Options.setup.config))
                return False
        else:
            pnames = Bcfg2.Options.setup.passphrases
            if len(pnames) == 1:
                self.pname = pnames.keys()[0]
                self.passphrase = pnames[self.pname]
                self.logger.info("Using passphrase %s" % self.pname)
                return True
            elif len(pnames) > 1:
                self.logger.warning("Multiple passphrases found in %s, "
                                    "specify one on the command line with -p" %
                                    Bcfg2.Options.setup.config)
        self.logger.info("No passphrase could be determined")
        return False

    def encrypt(self, fname):
        """ encrypt the given file, returning the encrypted data """
        try:
            plaintext = open(fname).read()
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Error reading %s, skipping: %s" % (fname, err))
            return False

        if not self.set_passphrase():
            return False

        crypted = []
        try:
            for chunk in self.chunk(plaintext):
                try:
                    passphrase, pname = self.get_passphrase(chunk)
                except TypeError:
                    return False

                crypted.append(self._encrypt(chunk, passphrase, name=pname))
        except EncryptionChunkingError:
            err = sys.exc_info()[1]
            self.logger.error("Error getting data to encrypt from %s: %s" %
                              (fname, err))
            return False
        return self.unchunk(crypted, plaintext)

    #  pylint: disable=W0613
    def _encrypt(self, plaintext, passphrase, name=None):
        """ encrypt a single chunk of a file """
        return ssl_encrypt(plaintext, passphrase)
    #  pylint: enable=W0613

    def decrypt(self, fname):
        """ decrypt the given file, returning the plaintext data """
        try:
            crypted = open(fname).read()
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Error reading %s, skipping: %s" % (fname, err))
            return False

        self.set_passphrase()

        plaintext = []
        try:
            for chunk in self.chunk(crypted):
                try:
                    passphrase, pname = self.get_passphrase(chunk)
                    try:
                        plaintext.append(self._decrypt(chunk, passphrase))
                    except EVPError:
                        self.logger.info("Could not decrypt %s with the "
                                         "specified passphrase" % fname)
                        continue
                    except:
                        err = sys.exc_info()[1]
                        self.logger.error("Error decrypting %s: %s" %
                                          (fname, err))
                        continue
                except TypeError:
                    pchunk = None
                    for pname, passphrase in \
                            Bcfg2.Options.setup.passphrases.items():
                        self.logger.debug("Trying passphrase %s" % pname)
                        try:
                            pchunk = self._decrypt(chunk, passphrase)
                            break
                        except EVPError:
                            pass
                        except:
                            err = sys.exc_info()[1]
                            self.logger.error("Error decrypting %s: %s" %
                                              (fname, err))
                    if pchunk is not None:
                        plaintext.append(pchunk)
                    else:
                        self.logger.error("Could not decrypt %s with any "
                                          "passphrase in %s" %
                                          (fname, Bcfg2.Options.setup.config))
                        continue
        except EncryptionChunkingError:
            err = sys.exc_info()[1]
            self.logger.error("Error getting encrypted data from %s: %s" %
                              (fname, err))
            return False

        try:
            return self.unchunk(plaintext, crypted)
        except EncryptionChunkingError:
            err = sys.exc_info()[1]
            self.logger.error("Error assembling plaintext data from %s: %s" %
                              (fname, err))
            return False

    def _decrypt(self, crypted, passphrase):
        """ decrypt a single chunk """
        return ssl_decrypt(crypted, passphrase)

    def write_encrypted(self, fname, data=None):
        """ write encrypted data to disk """
        if data is None:
            data = self.decrypt(fname)
        new_fname = self.get_encrypted_filename(fname)
        try:
            open(new_fname, "wb").write(data)
            self.logger.info("Wrote encrypted data to %s" % new_fname)
            return True
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Error writing encrypted data from %s to %s: %s"
                              % (fname, new_fname, err))
            return False
        except EncryptionChunkingError:
            err = sys.exc_info()[1]
            self.logger.error("Error assembling encrypted data from %s: %s" %
                              (fname, err))
            return False

    def write_decrypted(self, fname, data=None):
        """ write decrypted data to disk """
        if data is None:
            data = self.decrypt(fname)
        new_fname = self.get_plaintext_filename(fname)
        try:
            open(new_fname, "wb").write(data)
            self.logger.info("Wrote decrypted data to %s" % new_fname)
            return True
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Error writing encrypted data from %s to %s: %s"
                              % (fname, new_fname, err))
            return False

    def get_passphrase(self, chunk):
        """ get the passphrase for a chunk of a file """
        pname = self._get_passphrase(chunk)
        if not self.pname:
            if not pname:
                self.logger.info("No passphrase given on command line or "
                                 "found in file")
                return False
            elif pname in Bcfg2.Options.setup.passphrases:
                passphrase = Bcfg2.Options.setup.passphrases[pname]
            else:
                self.logger.error("Could not find passphrase %s in %s" %
                                  (pname, Bcfg2.Options.setup.config))
                return False
        else:
            pname = self.pname
            passphrase = self.passphrase
            if self.pname != pname:
                self.logger.warning("Passphrase given on command line (%s) "
                                    "differs from passphrase embedded in "
                                    "file (%s), using command-line option" %
                                    (self.pname, pname))
        return (passphrase, pname)

    def _get_passphrase(self, chunk):  # pylint: disable=W0613
        """ get the passphrase for a chunk of a file """
        return None


class CfgEncryptor(Encryptor):
    """ encryptor class for Cfg files """

    def get_encrypted_filename(self, plaintext_filename):
        return plaintext_filename + ".crypt"

    def get_plaintext_filename(self, encrypted_filename):
        if encrypted_filename.endswith(".crypt"):
            return encrypted_filename[:-6]
        else:
            return Encryptor.get_plaintext_filename(self, encrypted_filename)


class PropertiesEncryptor(Encryptor):
    """ encryptor class for Properties files """

    def _encrypt(self, plaintext, passphrase, name=None):
        # plaintext is an lxml.etree._Element
        if name is None:
            name = "true"
        if plaintext.text and plaintext.text.strip():
            plaintext.text = ssl_encrypt(plaintext.text, passphrase).strip()
            plaintext.set("encrypted", name)
        return plaintext

    def chunk(self, data):
        xdata = lxml.etree.XML(data, parser=XMLParser)
        if Bcfg2.Options.setup.xpath:
            elements = xdata.xpath(Bcfg2.Options.setup.xpath)
            if not elements:
                raise EncryptionChunkingError(
                    "XPath expression %s matched no elements" %
                    Bcfg2.Options.setup.xpath)
        else:
            elements = xdata.xpath('//*[@encrypted]')
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

        # this is not a good use of a generator, but we need to
        # generate the full list of elements in order to ensure that
        # some exist before we know what to return
        for elt in elements:
            yield elt

    def unchunk(self, data, original):
        # Properties elements are modified in-place, so we don't
        # actually need to unchunk anything
        xdata = Encryptor.unchunk(self, data, original)
        # find root element
        while xdata.getparent() is not None:
            xdata = xdata.getparent()
        return lxml.etree.tostring(xdata,
                                   xml_declaration=False,
                                   pretty_print=True).decode('UTF-8')

    def _get_passphrase(self, chunk):
        pname = chunk.get("encrypted")
        if pname and pname.lower() != "true":
            return pname
        return None

    def _decrypt(self, crypted, passphrase):
        # crypted is in lxml.etree._Element
        if not crypted.text or not crypted.text.strip():
            self.logger.warning("Skipping empty element %s" % crypted.tag)
            return crypted
        decrypted = ssl_decrypt(crypted.text, passphrase).strip()
        try:
            crypted.text = decrypted.encode('ascii', 'xmlcharrefreplace')
        except UnicodeDecodeError:
            # we managed to decrypt the value, but it contains content
            # that can't even be encoded into xml entities.  what
            # probably happened here is that we coincidentally could
            # decrypt a value encrypted with a different key, and
            # wound up with gibberish.
            self.logger.warning("Decrypted %s to gibberish, skipping" %
                                crypted.tag)
        return crypted


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

    def __init__(self):
        parser = Bcfg2.Options.get_parser(
            description="Encrypt and decrypt Bcfg2 data",
            components=[self, OptionContainer])
        parser.parse()
        self.logger = logging.getLogger(parser.prog)

        if Bcfg2.Options.setup.decrypt:
            if Bcfg2.Options.setup.remove:
                self.logger.error("--remove cannot be used with --decrypt, "
                                  "ignoring --remove")
                Bcfg2.Options.setup.remove = False
            elif Bcfg2.Options.setup.interactive:
                self.logger.error("Cannot decrypt interactively")
                Bcfg2.Options.setup.interactive = False

        if Bcfg2.Options.setup.cfg:
            if Bcfg2.Options.setup.xpath:
                self.logger.error("Specifying --xpath with --cfg is "
                                  "nonsensical, ignoring --xpath")
                Bcfg2.Options.setup.xpath = None
            if Bcfg2.Options.setup.interactive:
                self.logger.error("Cannot use interactive mode with --cfg, "
                                  "ignoring --interactive")
                Bcfg2.Options.setup.interactive = False
        elif Bcfg2.Options.setup.properties:
            if Bcfg2.Options.setup.remove:
                self.logger.error("--remove cannot be used with --properties, "
                                  "ignoring --remove")
                Bcfg2.Options.setup.remove = False

        self.props_crypt = PropertiesEncryptor()
        self.cfg_crypt = CfgEncryptor()

    def _is_properties(self, filename):
        """ Determine if a given file is a Properties file or not """
        if Bcfg2.Options.setup.properties:
            return True
        elif Bcfg2.Options.setup.cfg:
            return False
        elif fname.endswith(".xml"):
            try:
                xroot = lxml.etree.parse(fname).getroot()
                return xroot.tag == "Properties"
            except lxml.etree.XMLSyntaxError:
                return False
        else:
            return False

    def run(self):  # pylint: disable=R0912,R0915
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
                encryptor = self.props_crypt
                if Bcfg2.Options.setup.remove:
                    self.logger.warning("Cannot use --remove with Properties "
                                        "file %s, ignoring for this file" %
                                        fname)
            else:
                if Bcfg2.Options.setup.xpath:
                    self.logger.warning("Cannot use xpath with Cfg file %s, "
                                        "ignoring xpath for this file" % fname)
                if Bcfg2.Options.setup.interactive:
                    self.logger.warning("Cannot use interactive mode with Cfg "
                                        "file %s, ignoring --interactive for "
                                        "this file" % fname)
                encryptor = self.cfg_crypt

            data = None
            if Bcfg2.Options.setup.encrypt:
                xform = encryptor.encrypt
                write = encryptor.write_encrypted
            elif Bcfg2.Options.setup.decrypt:
                xform = encryptor.decrypt
                write = encryptor.write_decrypted
            else:
                self.logger.warning("Neither --encrypt nor --decrypt "
                                    "specified, determining mode")
                data = encryptor.decrypt(fname)
                if data:
                    write = encryptor.write_decrypted
                else:
                    self.logger.warning("Failed to decrypt %s, trying "
                                        "encryption" % fname)
                    data = None
                    xform = encryptor.encrypt
                    write = encryptor.write_encrypted

            if data is None:
                data = xform(fname)
            if not data:
                self.logger.error("Failed to %s %s, skipping" %
                                  (xform.__name__, fname))
                continue
            if Bcfg2.Options.setup.stdout:
                if len(Bcfg2.Options.setup.files) > 1:
                    print("----- %s -----" % fname)
                print(data)
                if len(Bcfg2.Options.setup.files) > 1:
                    print("")
            else:
                write(fname, data=data)

            if (Bcfg2.Options.setup.remove and
                encryptor.get_encrypted_filename(fname) != fname):
                try:
                    os.unlink(fname)
                except IOError:
                    err = sys.exc_info()[1]
                    self.logger.error("Error removing %s: %s" % (fname, err))
                    continue
