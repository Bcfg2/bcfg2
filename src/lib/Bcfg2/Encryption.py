#!/usr/bin/python -Ott

import os
import base64
from M2Crypto import Rand
from M2Crypto.EVP import Cipher, EVPError
from Bcfg2.Compat import StringIO

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

ENCRYPT = 1
DECRYPT = 0
ALGORITHM = "aes_256_cbc"
IV = '\0' * 16

Rand.rand_seed(os.urandom(1024))

def _cipher_filter(cipher, instr):
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
    """ encrypt a string """
    cipher = Cipher(alg=algorithm, key=key, iv=iv, op=ENCRYPT, salt=salt)
    return _cipher_filter(cipher, plaintext)
    
def str_decrypt(crypted, key, iv=IV, algorithm=ALGORITHM):
    """ decrypt a string """
    cipher = Cipher(alg=algorithm, key=key, iv=iv, op=DECRYPT)
    return _cipher_filter(cipher, crypted)
    
def ssl_decrypt(data, passwd, algorithm=ALGORITHM):
    """ decrypt openssl-encrypted data """
    # base64-decode the data if necessary
    try:
        data = base64.b64decode(data)
    except TypeError:
        # already decoded
        pass
    
    salt = data[8:16]
    hashes = [md5(passwd + salt).digest()]
    for i in range(1,3):
        hashes.append(md5(hashes[i-1] + passwd + salt).digest())
    key = hashes[0] + hashes[1]
    iv = hashes[2]
    
    return str_decrypt(data[16:], key=key, iv=iv)

def ssl_encrypt(plaintext, passwd, algorithm=ALGORITHM, salt=None):
    """ encrypt data in a format that is openssl compatible """
    if salt is None:
        salt = Rand.rand_bytes(8)
    
    hashes = [md5(passwd + salt).digest()]
    for i in range(1,3):
        hashes.append(md5(hashes[i-1] + passwd + salt).digest())
    key = hashes[0] + hashes[1]
    iv = hashes[2]
    
    crypted = str_encrypt(plaintext, key=key, salt=salt, iv=iv)
    return base64.b64encode("Salted__" + salt + crypted) + "\n"
