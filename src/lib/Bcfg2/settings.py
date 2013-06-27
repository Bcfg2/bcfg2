""" Django settings for the Bcfg2 server """

import os
import Bcfg2.Options

try:
    import django
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

# required for reporting
try:
    import south  # pylint: disable=W0611
    HAS_SOUTH = True
except ImportError:
    HAS_SOUTH = False

DATABASES = dict(default=dict())

# Django < 1.2 compat
DATABASE_ENGINE = None
DATABASE_NAME = None
DATABASE_USER = None
DATABASE_PASSWORD = None
DATABASE_HOST = None
DATABASE_PORT = None

TIME_ZONE = None

TEMPLATE_DEBUG = DEBUG = False

ALLOWED_HOSTS = ['*']

MEDIA_URL = '/site_media/'

MANAGERS = ADMINS = (('Root', 'root'))

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# TODO - sanitize this
INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'Bcfg2.Server',
)
if HAS_SOUTH:
    INSTALLED_APPS = INSTALLED_APPS + (
        'south',
        'Bcfg2.Reporting',
    )
if 'BCFG2_LEGACY_MODELS' in os.environ:
    INSTALLED_APPS += ('Bcfg2.Server.Reports.reports',)

# Imported from Bcfg2.Server.Reports
MEDIA_ROOT = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
STATIC_URL = '/media/'

#TODO - make this unique
# Make this unique, and don't share it with anybody.
SECRET_KEY = 'eb5+y%oy-qx*2+62vv=gtnnxg1yig_odu0se5$h0hh#pc*lmo7'

if HAS_DJANGO and django.VERSION[0] == 1 and django.VERSION[1] < 3:
    CACHE_BACKEND = 'locmem:///'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

#TODO - review these.  auth and sessions aren't really used
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
)

# TODO - move this to a higher root and dynamically import
ROOT_URLCONF = 'Bcfg2.Reporting.urls'

# TODO - this isn't usable
# Authentication Settings
AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend')

LOGIN_URL = '/login'

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

TEMPLATE_DIRS = (
    # App loaders should take care of this.. not sure why this is here
    '/usr/share/python-support/python-django/django/contrib/admin/templates/',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request'
)


def read_config():
    """ read the config file and set django settings based on it """
    global DEBUG, TEMPLATE_DEBUG, TIME_ZONE, MEDIA_URL  # pylint: disable=W0603

    DATABASES['default'] = \
        dict(ENGINE="django.db.backends.%s" % Bcfg2.Options.setup.db_engine,
             NAME=Bcfg2.Options.setup.db_name,
             USER=Bcfg2.Options.setup.db_user,
             PASSWORD=Bcfg2.Options.setup.db_password,
             HOST=Bcfg2.Options.setup.db_host,
             PORT=Bcfg2.Options.setup.db_port)

    TIME_ZONE = Bcfg2.Options.setup.timezone

    TEMPLATE_DEBUG = DEBUG = Bcfg2.Options.setup.web_debug
    if DEBUG:
        print("Warning: Setting web_debug to True causes extraordinary memory "
              "leaks.  Only use this setting if you know what you're doing.")

    if Bcfg2.Options.setup.web_prefix:
        MEDIA_URL = Bcfg2.Options.setup.web_prefix.rstrip('/') + MEDIA_URL


class _OptionContainer(object):
    options = [
        Bcfg2.Options.Common.repository,
        Bcfg2.Options.PathOption(
            '-W', '--web-config', cf=('reporting', 'config'),
            default="/etc/bcfg2-web.conf",
            action=Bcfg2.Options.ConfigFileAction,
            help='Web interface configuration file'),
        Bcfg2.Options.Option(
            cf=('database', 'engine'), default='sqlite3',
            help='Database engine', dest='db_engine'),
        Bcfg2.Options.Option(
            cf=('database', 'name'), default='<repository>/etc/bcfg2.sqlite',
            help="Database name", dest="db_name"),
        Bcfg2.Options.Option(
            cf=('database', 'user'), help='Database username', dest='db_user'),
        Bcfg2.Options.Option(
            cf=('database', 'password'), help='Database password',
            dest='db_password'),
        Bcfg2.Options.Option(
            cf=('database', 'host'), help='Database host', dest='db_host'),
        Bcfg2.Options.Option(
            cf=('database', 'port'), help='Database port', dest='db_port'),
        Bcfg2.Options.Option(
            cf=('reporting', 'timezone'), help='Django timezone'),
        Bcfg2.Options.BooleanOption(
            cf=('reporting', 'web_debug'), help='Django debug'),
        Bcfg2.Options.Option(
            cf=('reporting', 'web_prefix'), help='Web prefix')]

    @staticmethod
    def options_parsed_hook():
        """ initialize settings from /etc/bcfg2-web.conf or
        /etc/bcfg2.conf, or set up basic defaults.  this lets
        manage.py work in all cases """
        read_config()


Bcfg2.Options.get_parser().add_component(_OptionContainer)
