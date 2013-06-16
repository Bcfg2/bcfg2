""" Compatibility imports, mostly for Py3k support, but also for
Python 2.4 and such-like """

###################################################
#                                                 #
#   IF YOU ADD SOMETHING TO THIS FILE, YOU MUST   #
#   DOCUMENT IT IN docs/development/compat.txt    #
#                                                 #
###################################################

import sys

# pylint: disable=E0601,E0602,E0611,W0611,W0622,C0103

try:
    from email.Utils import formatdate
except ImportError:
    from email.utils import formatdate

# urllib imports
try:
    from urllib import quote_plus
    from urlparse import urljoin, urlparse
    from urllib2 import HTTPBasicAuthHandler, \
        HTTPPasswordMgrWithDefaultRealm, build_opener, install_opener, \
        urlopen, HTTPError, URLError
except ImportError:
    from urllib.parse import urljoin, urlparse, quote_plus
    from urllib.request import HTTPBasicAuthHandler, \
        HTTPPasswordMgrWithDefaultRealm, build_opener, install_opener, urlopen
    from urllib.error import HTTPError, URLError

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
    import xmlrpclib
    import SimpleXMLRPCServer
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

try:
    unicode = unicode
except NameError:
    unicode = str


def u_str(string, encoding=None):
    """ print to file compatibility """
    if sys.hexversion >= 0x03000000:
        return string
    else:
        if encoding is not None:
            return unicode(string, encoding)
        else:
            return unicode(string)

try:
    from functools import wraps
except ImportError:
    def wraps(wrapped):  # pylint: disable=W0613
        """ implementation of functools.wraps() for python 2.4 """
        return lambda f: f


# base64 compat
if sys.hexversion >= 0x03000000:
    from base64 import b64encode as _b64encode, b64decode as _b64decode

    @wraps(_b64encode)
    def b64encode(val, **kwargs):  # pylint: disable=C0111
        try:
            return _b64encode(val, **kwargs)
        except TypeError:
            return _b64encode(val.encode('UTF-8'), **kwargs).decode('UTF-8')

    @wraps(_b64decode)
    def b64decode(val, **kwargs):  # pylint: disable=C0111
        return _b64decode(val.encode('UTF-8'), **kwargs).decode('UTF-8')
else:
    from base64 import b64encode, b64decode

try:
    input = raw_input
except NameError:
    input = input

try:
    reduce = reduce
except NameError:
    from functools import reduce

try:
    from collections import MutableMapping
except ImportError:
    from UserDict import DictMixin as MutableMapping


class CmpMixin(object):
    """ In Py3K, :meth:`object.__cmp__` is no longer magical, so this
    mixin can be used to define the rich comparison operators from
    ``__cmp__`` -- i.e., it makes ``__cmp__`` magical again. """

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
            """ Implementation of walk_packages for python 2.5 """
            def seen(path, seenpaths={}):  # pylint: disable=W0102
                """ detect if a path has been 'seen' (i.e., considered
                for inclusion in the generator).  tracks what has been
                seen through the magic of python default arguments """
                if path in seenpaths:
                    return True
                seenpaths[path] = True

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
            """ Imperfect, incomplete implementation of
            :func:`pkgutil.walk_packages` for python 2.4. Differences:

            * Requires a full path, not a path relative to something
              in sys.path.  Anywhere we care about that shouldn't be
              an issue.
            * The first element of each tuple is None instead of an
              importer object.
            """
            if path is None:
                path = sys.path
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
        """ implementation of builtin all() for python 2.4 """
        for element in iterable:
            if not element:
                return False
        return True

    def any(iterable):
        """ implementation of builtin any() for python 2.4 """
        for element in iterable:
            if element:
                return True
        return False

try:
    from hashlib import md5
except ImportError:
    from md5 import md5


def oct_mode(mode):
    """ Convert a decimal number describing a POSIX permissions mode
    to a string giving the octal mode.  In Python 2, this is a synonym
    for :func:`oct`, but in Python 3 the octal format has changed to
    ``0o000``, which cannot be used as an octal permissions mode, so
    we need to strip the 'o' from the output.  I.e., this function
    acts like the Python 2 :func:`oct` regardless of what version of
    Python is in use.

    :param mode: The decimal mode to convert to octal
    :type mode: int
    :returns: string """
    return oct(mode).replace('o', '')


try:
    long = long
except NameError:
    # longs are just ints in py3k
    long = int


try:
    cmp = cmp
except NameError:
    def cmp(a, b):
        """ Py3k implementation of cmp() """
        return (a > b) - (a < b)
