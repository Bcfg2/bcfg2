""" Compatibility imports, mostly for Py3k support, but also for
Python 2.4 and such-like """

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
if sys.hexversion >= 0x03000000:
    from base64 import b64encode as _b64encode, b64decode as _b64decode
    b64encode = lambda s: _b64encode(s.encode('UTF-8')).decode('UTF-8')
    b64decode = lambda s: _b64decode(s.encode('UTF-8')).decode('UTF-8')
else:
    from base64 import b64encode, b64decode

try:
    input = raw_input
except:
    input = input

try:
    reduce = reduce
except NameError:
    from functools import reduce

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

try:
    from pkgutil import walk_packages
except ImportError:
    try:
        from pkgutil import iter_modules
        # iter_modules was added in python 2.5; use it to get an exact
        # re-implementation of walk_packages if possible
        def walk_packages(path=None, prefix='', onerror=None):
            def seen(p, m={}):
                if p in m:
                    return True
                m[p] = True

            for importer, name, ispkg in iter_modules(path, prefix):
                yield importer, name, ispkg

                if ispkg:
                    try:
                        __import__(name)
                    except ImportError:
                        if onerror is not None:
                            onerror(name)
                    except Exception:
                        if onerror is not None:
                            onerror(name)
                        else:
                            raise
                    else:
                        path = getattr(sys.modules[name], '__path__', [])

                        # don't traverse path items we've seen before
                        path = [p for p in path if not seen(p)]

                        for item in walk_packages(path, name + '.', onerror):
                            yield item
    except ImportError:
        import os

        def walk_packages(path=None, prefix='', onerror=None):
            """ imperfect, incomplete implementation of
            walk_packages() for python 2.4. Differences:
            
            * requires a full path, not a path relative to something
              in sys.path.  anywhere we care about that shouldn't be
              an issue

            * the first element of each tuple is None instead of an
              importer object
            """
            def seen(p, m={}):
                if p in m:
                    return True
                m[p] = True

            if path is None:
                path = sys.path
            rv = []
            for mpath in path:
                for fname in os.listdir(mpath):
                    fpath = os.path.join(mpath, fname)
                    if (os.path.isfile(fpath) and fname.endswith(".py") and
                        fname != '__init__.py'):
                        yield None, prefix + fname[:-3], False
                    elif os.path.isdir(fpath):
                        mname = prefix + fname
                        if os.path.exists(os.path.join(fpath, "__init__.py")):
                            yield None, mname, True
                        try:
                            __import__(mname)
                        except ImportError:
                            if onerror is not None:
                                onerror(mname)
                        except Exception:
                            if onerror is not None:
                                onerror(mname)
                            else:
                                raise
                        else:
                            for item in walk_packages([fpath],
                                                      prefix=mname + '.',
                                                      onerror=onerror):
                                yield item


try:
    all = all
    any = any
except NameError:
    def all(iterable):
        for element in iterable:
            if not element:
                return False
        return True

    def any(iterable):
        for element in iterable:
            if element:
                return True
        return False

try:
    from hashlib import md5
except ImportError:
    from md5 import md5


try:
    import json
except ImportError:
    import simplejson as json

