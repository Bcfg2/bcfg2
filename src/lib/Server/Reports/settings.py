import django
import os.path
from Bcfg2.metargs import Option
import Bcfg2.Options

# Django settings for bcfg2 reports project.

Bcfg2.Options.add_options(
    Option('--web-config', 'statistics:config', default='/etc/bcfg2-web.conf',
           help='Location of the reports configuration file', type=os.path.abspath),
)

Bcfg2.Options.add_configs(Bcfg2.Options.bootstrap().web_config)

Bcfg2.Options.add_options(
    Option('statistics:web_debug', default=False, type=lambda v: v == "True"),
    Option('statistics:database_engine', required=True),
    Option('statistics:database_name', default=''),
    Option('statistics:time_zone'),
    Option('statistics:web_prefix'),
    Bcfg2.Options.SERVER_REPOSITORY,
)

if Bcfg2.Options.bootstrap().statistics_database_engine != 'sqlite3':
    Bcfg2.Options.add_options(
        Option('statistics:database_user', required=True),
        Option('statistics:database_password', required=True),
        Option('statistics:database_host', required=True),
        Option('statistics:database_port', default=''),
    )

args = Bcfg2.Options.bootstrap()

DEBUG = args.statistics_web_debug

if DEBUG:
    print("Warning: Setting web_debug to True causes extraordinary memory "
          "leaks.  Only use this setting if you know what you're doing.")

TEMPLATE_DEBUG = DEBUG

ADMINS = (
     ('Root', 'root'),
)

MANAGERS = ADMINS

db_engine = args.statistics_database_engine
db_name = args.statistics_database_name

if db_name == '' and db_engine == 'sqlite3':
    db_name = "%s/etc/brpt.sqlite" % args.repository_path

DATABASES = {
    'default': {
        'ENGINE': "django.db.backends.%s" % db_engine,
        'NAME': db_name
    }
}

if db_engine != 'sqlite3':
    DATABASES['default']['USER'] = args.statistics_database_user
    DATABASES['default']['PASSWORD'] = args.statistics_database_password
    DATABASES['default']['HOST'] = args.statistics_database_host
    DATABASES['default']['PORT'] = args.statistics_database_port

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
TIME_ZONE = args.statistics_time_zone

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
if args.statistics_web_prefix is not None:
    MEDIA_URL = args.statistics_web_prefix.rstrip('/') + MEDIA_URL

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
    raise ImportError('Import of Django module failed. Is Django installed?')
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
