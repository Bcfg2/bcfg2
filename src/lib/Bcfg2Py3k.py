try:
    from email.Utils import formatdate
except ImportError:
    from email.utils import formatdate

# urllib imports
try:
    from urllib import urlopen
except ImportError:
    from urllib.request import urlopen
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
