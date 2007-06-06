# Django settings for bcfg reports project.
from ConfigParser import ConfigParser, NoSectionError, NoOptionError
c = ConfigParser()
c.read(['/etc/bcfg2.conf'])#This needs to be configurable one day somehow
sqlitedbpath = "%s/etc/brpt.sqlite" % c.get('server', 'repository')

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
     ('Joey Hagedorn', 'hagedorn@mcs.anl.gov'),
)

MANAGERS = ADMINS

DATABASE_ENGINE = 'sqlite3'           # 'postgresql', 'mysql', 'sqlite3' or 'ado_mssql'.
DATABASE_NAME = sqlitedbpath             # Or path to database file if using sqlite3.
DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Local time zone for this installation. All choices can be found here:
# http://www.postgresql.org/docs/current/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'eb5+y%oy-qx*2+62vv=gtnnxg1yig_odu0se5$h0hh#pc*lmo7'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
    'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'django.middleware.profile.ProfileMiddleware',
)

ROOT_URLCONF = 'Bcfg2.Server.Reports.urls'

# Authentication Settings
# Use NIS authentication backend defined in backends.py
AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',
                           'Bcfg2.Server.Reports.backends.NISBackend')
# The NIS group authorized to login to BCFG2's reportinvg system
AUTHORIZED_GROUP = ''
#create login url area:
import django.contrib.auth
django.contrib.auth.LOGIN_URL = '/login'

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
            
    

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates".
    # Always use forward slashes, even on Windows.
    '/usr/share/python-support/python-django/django/contrib/admin/templates/',
    '/usr/share/bcfg2/Reports/templates'
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'Bcfg2.Server.Reports.reports'
)
