""" Django settings for the Bcfg2 server """

import os
import sys
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

DATABASES = dict()

# Django < 1.2 compat
DATABASE_ENGINE = None
DATABASE_NAME = None
DATABASE_USER = None
DATABASE_PASSWORD = None
DATABASE_HOST = None
DATABASE_PORT = None
DATABASE_OPTIONS = None

TIME_ZONE = None

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = ['*']

MEDIA_URL = '/site_media/'


def _default_config():
    """ get the default config file.  returns /etc/bcfg2-web.conf,
    UNLESS /etc/bcfg2.conf exists AND /etc/bcfg2-web.conf does not
    exist. """
    optinfo = dict(cfile=Bcfg2.Options.CFILE,
                   web_cfile=Bcfg2.Options.WEB_CFILE)
    setup = Bcfg2.Options.OptionParser(optinfo, quiet=True)
    setup.parse(sys.argv[1:], do_getopt=False)
    if (not os.path.exists(setup['web_cfile']) and
        os.path.exists(setup['cfile'])):
        return setup['cfile']
    else:
        return setup['web_cfile']

DEFAULT_CONFIG = _default_config()


def read_config(cfile=DEFAULT_CONFIG, repo=None, quiet=False):
    """ read the config file and set django settings based on it """
    # pylint: disable=W0602,W0603
    global DATABASE_ENGINE, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, \
        DATABASE_HOST, DATABASE_PORT, DATABASE_OPTIONS, DEBUG, \
        TEMPLATE_DEBUG, TIME_ZONE, MEDIA_URL
    # pylint: enable=W0602,W0603

    if not os.path.exists(cfile) and os.path.exists(DEFAULT_CONFIG):
        print("%s does not exist, using %s for database configuration" %
              (cfile, DEFAULT_CONFIG))
        cfile = DEFAULT_CONFIG

    optinfo = Bcfg2.Options.DATABASE_COMMON_OPTIONS
    optinfo['repo'] = Bcfg2.Options.SERVER_REPOSITORY
    # when setting a different config file, it has to be set in either
    # sys.argv or in the OptionSet() constructor AS WELL AS the argv
    # that's passed to setup.parse()
    argv = [Bcfg2.Options.CFILE.cmd, cfile,
            Bcfg2.Options.WEB_CFILE.cmd, cfile]
    setup = Bcfg2.Options.OptionParser(optinfo, argv=argv, quiet=quiet)
    setup.parse(argv)

    if repo is None:
        repo = setup['repo']

    DATABASES['default'] = \
        dict(ENGINE="django.db.backends.%s" % setup['db_engine'],
             NAME=setup['db_name'],
             USER=setup['db_user'],
             PASSWORD=setup['db_password'],
             HOST=setup['db_host'],
             PORT=setup['db_port'],
             OPTIONS=setup['db_options'])

    if HAS_DJANGO and django.VERSION[0] == 1 and django.VERSION[1] < 2:
        DATABASE_ENGINE = setup['db_engine']
        DATABASE_NAME = DATABASES['default']['NAME']
        DATABASE_USER = DATABASES['default']['USER']
        DATABASE_PASSWORD = DATABASES['default']['PASSWORD']
        DATABASE_HOST = DATABASES['default']['HOST']
        DATABASE_PORT = DATABASES['default']['PORT']
        DATABASE_OPTIONS = DATABASES['default']['OPTIONS']

    # dropping the version check.  This was added in 1.1.2
    TIME_ZONE = setup['time_zone']

    DEBUG = setup['django_debug']
    TEMPLATE_DEBUG = DEBUG
    if DEBUG:
        print("Warning: Setting web_debug to True causes extraordinary memory "
              "leaks.  Only use this setting if you know what you're doing.")

    if setup['web_prefix']:
        MEDIA_URL = setup['web_prefix'].rstrip('/') + MEDIA_URL
    else:
        MEDIA_URL = '/site_media/'

# initialize settings from /etc/bcfg2-web.conf or /etc/bcfg2.conf, or
# set up basic defaults.  this lets manage.py work in all cases
read_config(quiet=True)

ADMINS = (('Root', 'root'))
MANAGERS = ADMINS

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

if HAS_DJANGO and django.VERSION[0] == 1 and django.VERSION[1] < 2:
    TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.load_template_source',
        'django.template.loaders.app_directories.load_template_source',
    )
else:
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

# TODO - sanitize this
if HAS_DJANGO and django.VERSION[0] == 1 and django.VERSION[1] < 2:
    TEMPLATE_CONTEXT_PROCESSORS = (
        'django.core.context_processors.auth',
        'django.core.context_processors.debug',
        'django.core.context_processors.i18n',
        'django.core.context_processors.media',
        'django.core.context_processors.request'
    )
else:
    TEMPLATE_CONTEXT_PROCESSORS = (
        'django.contrib.auth.context_processors.auth',
        'django.core.context_processors.debug',
        'django.core.context_processors.i18n',
        'django.core.context_processors.media',
        'django.core.context_processors.request'
    )
