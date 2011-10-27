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
except ImportError:
    from urllib.parse import urljoin, urlparse
    from urllib.request import HTTPBasicAuthHandler
    from urllib.request import HTTPPasswordMgrWithDefaultRealm
    from urllib.request import build_opener
    from urllib.request import install_opener
    from urllib.request import urlopen
    from urllib.error import HTTPError

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

"""
In order to use the new syntax for printing to a file, we need to do
a conditional import because there is a syntax incompatibility between
the two versions of python.
"""
if sys.hexversion >= 0x03000000:
    from Bcfg2.Bcfg2Py3Incompat import fprint
else:
    def fprint(s, f):
        print >> f, s

if sys.hexversion >= 0x03000000:
    from io import FileIO as file
else:
    file = file
