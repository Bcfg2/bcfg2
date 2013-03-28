""" Bcfg2.Encryption provides a number of convenience methods for
handling encryption in Bcfg2.  See :ref:`server-encryption` for more
details. """

import os
from M2Crypto import Rand
from M2Crypto.EVP import Cipher, EVPError
from Bcfg2.Compat import StringIO, md5, b64encode, b64decode

#: Constant representing the encryption operation for
#: :class:`M2Crypto.EVP.Cipher`, which uses a simple integer.  This
#: makes our code more readable.
ENCRYPT = 1

#: Constant representing the decryption operation for
#: :class:`M2Crypto.EVP.Cipher`, which uses a simple integer.  This
#: makes our code more readable.
DECRYPT = 0

#: Default cipher algorithm.  To get a full list of valid algorithms,
#: you can run::
#:
#:     openssl list-cipher-algorithms | grep -v ' => ' | \
#:         tr 'A-Z-' 'a-z_' | sort -u
ALGORITHM = "aes_256_cbc"

#: Default initialization vector.  For best security, you should use a
#: unique IV for each message.  :func:`ssl_encrypt` does this in an
#: automated fashion.
IV = r'\0' * 16

#: The config file section encryption options and passphrases are
#: stored in
CFG_SECTION = "encryption"

#: The config option used to store the algorithm
CFG_ALGORITHM = "algorithm"

#: The config option used to store the decryption strictness
CFG_DECRYPT = "decrypt"

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


def str_encrypt(plaintext, key, iv=IV, algorithm=ALGORITHM, salt=None):
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
    cipher = Cipher(alg=algorithm, key=key, iv=iv, op=ENCRYPT, salt=salt)
    return _cipher_filter(cipher, plaintext)


def str_decrypt(crypted, key, iv=IV, algorithm=ALGORITHM):
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
    cipher = Cipher(alg=algorithm, key=key, iv=iv, op=DECRYPT)
    return _cipher_filter(cipher, crypted)


def ssl_decrypt(data, passwd, algorithm=ALGORITHM):
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
    # pylint: disable=E1101
    hashes = [md5(passwd + salt).digest()]
    for i in range(1, 3):
        hashes.append(md5(hashes[i - 1] + passwd + salt).digest())
    # pylint: enable=E1101
    key = hashes[0] + hashes[1]
    iv = hashes[2]

    return str_decrypt(data[16:], key=key, iv=iv, algorithm=algorithm)


def ssl_encrypt(plaintext, passwd, algorithm=ALGORITHM, salt=None):
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

    # pylint: disable=E1101
    hashes = [md5(passwd + salt).digest()]
    for i in range(1, 3):
        hashes.append(md5(hashes[i - 1] + passwd + salt).digest())
    # pylint: enable=E1101
    key = hashes[0] + hashes[1]
    iv = hashes[2]

    crypted = str_encrypt(plaintext, key=key, salt=salt, iv=iv,
                          algorithm=algorithm)
    return b64encode("Salted__" + salt + crypted) + "\n"


def get_algorithm(setup):
    """ Get the cipher algorithm from the config file.  This is used
    in case someone uses the OpenSSL algorithm name (e.g.,
    "AES-256-CBC") instead of the M2Crypto name (e.g., "aes_256_cbc"),
    and to handle errors in a sensible way and deduplicate this code.

    :param setup: The Bcfg2 option set to extract passphrases from
    :type setup: Bcfg2.Options.OptionParser
    :returns: dict - a dict of ``<passphrase name>``: ``<passphrase>``
    """
    return setup.cfp.get(CFG_SECTION, CFG_ALGORITHM,
                         default=ALGORITHM).lower().replace("-", "_")


def get_passphrases(setup):
    """ Get all candidate encryption passphrases from the config file.

    :param setup: The Bcfg2 option set to extract passphrases from
    :type setup: Bcfg2.Options.OptionParser
    :returns: dict - a dict of ``<passphrase name>``: ``<passphrase>``
    """
    section = CFG_SECTION
    if setup.cfp.has_section(section):
        return dict([(o, setup.cfp.get(section, o))
                     for o in setup.cfp.options(section)
                     if o not in [CFG_ALGORITHM, CFG_DECRYPT]])
    else:
        return dict()


def bruteforce_decrypt(crypted, passphrases=None, setup=None,
                       algorithm=ALGORITHM):
    """ Convenience method to decrypt the given encrypted string by
    trying the given passphrases or all passphrases (as returned by
    :func:`get_passphrases`) sequentially until one is found that
    works.

    Either ``passphrases`` or ``setup`` must be provided.

    :param crypted: The data to decrypt
    :type crypted: string
    :param passphrases: The passphrases to try.
    :type passphrases: list
    :param setup: A Bcfg2 option set to extract passphrases from
    :type setup: Bcfg2.Options.OptionParser
    :param algorithm: The cipher algorithm to use
    :type algorithm: string
    :returns: string - The decrypted data
    :raises: :class:`M2Crypto.EVP.EVPError`, if the data cannot be decrypted
    """
    if passphrases is None:
        passphrases = get_passphrases(setup).values()
    for passwd in passphrases:
        try:
            return ssl_decrypt(crypted, passwd, algorithm=algorithm)
        except EVPError:
            pass
    raise EVPError("Failed to decrypt")
