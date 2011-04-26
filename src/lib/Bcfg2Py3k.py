try:
    from email.Utils import formatdate
except ImportError:
    from email.utils import formatdate

# urllib imports
try:
    from urlparse import urljoin
    from urllib2 import HTTPBasicAuthHandler
    from urllib2 import HTTPPasswordMgrWithDefaultRealm
    from urllib2 import build_opener
    from urllib2 import install_opener
    from urllib import urlopen
    from urllib2 import HTTPError
except ImportError:
    from urllib.parse import urljoin
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
    from Queue import Queue
    from Queue import Empty
    from Queue import Full
except ImportError:
    from queue import Queue
    from queue import Empty
    from queue import Full
