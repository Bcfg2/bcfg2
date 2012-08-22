import sys

try:
    from email.Utils import formatdate
except ImportError:
    from email.utils import formatdate

# urllib imports
try:
    from urlparse import urljoin, urlparse
    from urllib2 import HTTPBasicAuthHandler
    from urllib2 import HTTPPasswordMgrWithDefaultRealm
    from urllib2 import build_opener
    from urllib2 import install_opener
    from urllib2 import urlopen
    from urllib2 import HTTPError
    from urllib2 import URLError
except ImportError:
    from urllib.parse import urljoin, urlparse
    from urllib.request import HTTPBasicAuthHandler
    from urllib.request import HTTPPasswordMgrWithDefaultRealm
    from urllib.request import build_opener
    from urllib.request import install_opener
    from urllib.request import urlopen
    from urllib.error import HTTPError
    from urllib.error import URLError

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

try:
    import cPickle
except ImportError:
    import pickle as cPickle

try:
    from Queue import Queue, Empty, Full
except ImportError:
    from queue import Queue, Empty, Full

# xmlrpc imports
try:
    import xmlrpclib, SimpleXMLRPCServer
except ImportError:
    import xmlrpc.client as xmlrpclib
    import xmlrpc.server as SimpleXMLRPCServer

# socketserver import
try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer

# httplib imports
try:
    import httplib
except ImportError:
    import http.client as httplib

# py3k compatibility
if sys.hexversion >= 0x03000000:
    unicode = str
else:
    unicode = unicode

# print to file compatibility
def u_str(string, encoding=None):
    if sys.hexversion >= 0x03000000:
        if encoding is not None:
            return string.encode(encoding)
        else:
            return string
    else:
        if encoding is not None:
            return unicode(string, encoding)
        else:
            return unicode(string)

try:
    unicode = unicode
except:
    unicode = str

# base64 compat
from base64 import b64encode as _b64encode, b64decode as _b64decode
b64encode = lambda s: _b64encode(s.encode('ascii')).decode('ascii')
b64decode = lambda s: _b64decode(s.encode('ascii')).decode('ascii')

try:
    input = raw_input
except:
    input = input

try:
    reduce = reduce
except NameError:
    import functools
    reduce = functools.reduce

try:
    from collections import MutableMapping
except ImportError:
    from UserDict import DictMixin as MutableMapping


# in py3k __cmp__ is no longer magical, so we define a mixin that can
# be used to define the rich comparison operators from __cmp__
class CmpMixin(object):
    def __lt__(self, other):
        return self.__cmp__(other) < 0
    
    def __gt__(self, other):
        return self.__cmp__(other) > 0
    
    def __eq__(self, other):
        return self.__cmp__(other) == 0
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)
    
    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)
