import django
import sys

# Compatibility import
from Bcfg2.Bcfg2Py3k import ConfigParser
# Django settings for bcfg2 reports project.
c = ConfigParser.ConfigParser()
if len(c.read(['/etc/bcfg2.conf', '/etc/bcfg2-web.conf'])) == 0:
    print("Please check that bcfg2.conf or bcfg2-web.conf exists "
          "and is readable by your web server.")
    sys.exit(1)

try:
    dset = c.get('statistics', 'web_debug')
except:
    dset = 'false'

if dset == "True":
    DEBUG = True
else:
    DEBUG = False
    
TEMPLATE_DEBUG = DEBUG

ADMINS = (
     ('Root', 'root'),
)

MANAGERS = ADMINS
try:
    db_engine = c.get('statistics', 'database_engine')
except ConfigParser.NoSectionError:
    e = sys.exc_info()[1]
    print("Failed to determine database engine: %s" % e)
    sys.exit(1)
db_name = ''
if c.has_option('statistics', 'database_name'):
    db_name = c.get('statistics', 'database_name')
if db_engine == 'sqlite3' and db_name == '':
    db_name = "%s/etc/brpt.sqlite" % c.get('server', 'repository')

DATABASES = {
    'default': {
        'ENGINE': "django.db.backends.%s" % db_engine,
        'NAME': db_name
    }
}

if db_engine != 'sqlite3':
    DATABASES['default']['USER'] =  c.get('statistics', 'database_user')
    DATABASES['default']['PASSWORD'] = c.get('statistics', 'database_password')
    DATABASES['default']['HOST'] = c.get('statistics', 'database_host')
    try:
        DATABASES['default']['PORT'] = c.get('statistics', 'database_port')
    except: # An empty string tells Django to use the default port.
        DATABASES['default']['PORT'] = ''

if django.VERSION[0] == 1 and django.VERSION[1] < 2:
    DATABASE_ENGINE = db_engine
    DATABASE_NAME = DATABASES['default']['NAME']
    if DATABASE_ENGINE != 'sqlite3':
        DATABASE_USER = DATABASES['default']['USER']
        DATABASE_PASSWORD = DATABASES['default']['PASSWORD']
        DATABASE_HOST = DATABASES['default']['HOST']
        DATABASE_PORT = DATABASES['default']['PORT']


# Local time zone for this installation. All choices can be found here:
# http://docs.djangoproject.com/en/dev/ref/settings/#time-zone
try:
    TIME_ZONE = c.get('statistics', 'time_zone')
except:
    if django.VERSION[0] == 1 and django.VERSION[1] > 2:
        TIME_ZONE = None

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
MEDIA_URL = '/site_media'
if c.has_option('statistics', 'web_prefix'):
    MEDIA_URL = c.get('statistics', 'web_prefix').rstrip('/') + MEDIA_URL

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
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
)

ROOT_URLCONF = 'Bcfg2.Server.Reports.urls'

# Authentication Settings
# Use NIS authentication backend defined in backends.py
AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',
                           'Bcfg2.Server.Reports.backends.NISBackend')
# The NIS group authorized to login to BCFG2's reportinvg system
AUTHORIZED_GROUP = ''
#create login url area:
try:
    import django.contrib.auth
except ImportError:
    print('Import of Django module failed. Is Django installed?')
django.contrib.auth.LOGIN_URL = '/login'

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
            
    

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates".
    # Always use forward slashes, even on Windows.
    '/usr/share/python-support/python-django/django/contrib/admin/templates/',
    'Bcfg2.Server.Reports.reports'
)

if django.VERSION[0] == 1 and django.VERSION[1] < 2:
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

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'Bcfg2.Server.Reports.reports'
)
