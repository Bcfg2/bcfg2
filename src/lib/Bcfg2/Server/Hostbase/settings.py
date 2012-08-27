import os.path
# Compatibility import
from Bcfg2.Compat import ConfigParser

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

c = ConfigParser.ConfigParser()
#This needs to be configurable one day somehow
c.read(['./bcfg2.conf'])

defaults = {'database_engine':'sqlite3',
            'database_name':'./dev.db',
            'database_user':'',
            'database_password':'',
            'database_host':'',
            'database_port':3306,
            'default_mx':'localhost',
            'priority':10,
            'authorized_group':'admins',
            }

if c.has_section('hostbase'):
    options = dict(c.items('hostbase'))
else:
    options = defaults

# Django settings for Hostbase project.
DEBUG = True
TEMPLATE_DEBUG = DEBUG
ADMINS = (
     ('Root', 'root'),
)
MANAGERS = ADMINS

# 'postgresql', 'mysql', 'sqlite3' or 'ado_mssql'.
DATABASE_ENGINE = options['database_engine']
# Or path to database file if using sqlite3.
DATABASE_NAME = options['database_name']
# Not used with sqlite3.
DATABASE_USER = options['database_user']
# Not used with sqlite3.
DATABASE_PASSWORD = options['database_password']
# Set to empty string for localhost. Not used with sqlite3.
DATABASE_HOST = options['database_host']
# Set to empty string for default. Not used with sqlite3.
DATABASE_PORT = int(options['database_port'])
# Local time zone for this installation. All choices can be found here:
# http://docs.djangoproject.com/en/dev/ref/settings/#time-zone
try:
    TIME_ZONE = c.get('statistics', 'time_zone')
except:
    TIME_ZONE = None

# enter the defauly MX record machines will get in Hostbase
# this setting may move elsewhere eventually
DEFAULT_MX = options['default_mx']
PRIORITY = int(options['priority'])

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Uncomment a backend below if you would like to use it for authentication
AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',
                           'Bcfg2.Server.Hostbase.backends.NISBackend',
                           #'Bcfg2.Server.Hostbase.backends.LDAPBacken',
                           )
# enter an NIS group name you'd like to give access to edit hostbase records
AUTHORIZED_GROUP = options['authorized_group']

#create login url area:
import django.contrib.auth
django.contrib.auth.LOGIN_URL = '/login'
# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media')
# Just for development
SERVE_MEDIA = DEBUG

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = '/site_media/'
# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'
# Make this unique, and don't share it with anybody.
SECRET_KEY = '*%=fv=yh9zur&gvt4&*d#84o(cy^-*$ox-v1e9%32pzf2*qu#s'
# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.request",
    "django.core.context_processors.media",
# Django development version.
#    "django.core.context_processors.csrf",
)


MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
)

ROOT_URLCONF = 'Bcfg2.Server.Hostbase.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates".
    # Always use forward slashes, even on Windows.
    '/usr/lib/python2.3/site-packages/Bcfg2/Server/Hostbase/hostbase/webtemplates',
    '/usr/lib/python2.4/site-packages/Bcfg2/Server/Hostbase/hostbase/webtemplates',
    '/usr/lib/python2.3/site-packages/Bcfg2/Server/Hostbase/templates',
    '/usr/lib/python2.4/site-packages/Bcfg2/Server/Hostbase/templates',
    '/usr/share/bcfg2/Hostbase/templates',
    os.path.join(PROJECT_ROOT, 'templates'),
    os.path.join(PROJECT_ROOT, 'hostbase/webtemplates'),
)

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.humanize',
    'Bcfg2.Server.Hostbase.hostbase',
)

LOGIN_URL = '/login/'
