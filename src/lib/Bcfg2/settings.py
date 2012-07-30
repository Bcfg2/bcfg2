import sys
import django
import Bcfg2.Options

DATABASES = dict()

# Django < 1.2 compat
DATABASE_ENGINE = None
DATABASE_NAME = None
DATABASE_USER = None
DATABASE_PASSWORD = None
DATABASE_HOST = None
DATABASE_PORT = None

def read_config(cfile='/etc/bcfg2.conf', repo=None, quiet=False):
    global DATABASE_ENGINE, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, \
        DATABASE_HOST, DATABASE_PORT

    setup = \
        Bcfg2.Options.OptionParser(dict(repo=Bcfg2.Options.SERVER_REPOSITORY,
                                        configfile=Bcfg2.Options.CFILE,
                                        db_engine=Bcfg2.Options.DB_ENGINE,
                                        db_name=Bcfg2.Options.DB_NAME,
                                        db_user=Bcfg2.Options.DB_USER,
                                        db_password=Bcfg2.Options.DB_PASSWORD,
                                        db_host=Bcfg2.Options.DB_HOST,
                                        db_port=Bcfg2.Options.DB_PORT),
                                   quiet=quiet)
    setup.parse([Bcfg2.Options.CFILE.cmd, cfile])

    if repo is None:
        repo = setup['repo']

    DATABASES['default'] = \
        dict(ENGINE=setup['db_engine'],
             NAME=setup['db_name'],
             USER=setup['db_user'],
             PASSWORD=setup['db_password'],
             HOST=setup['db_host'],
             PORT=setup['db_port'])

    if django.VERSION[0] == 1 and django.VERSION[1] < 2:
        DATABASE_ENGINE = setup['db_engine']
        DATABASE_NAME = DATABASES['default']['NAME']
        DATABASE_USER = DATABASES['default']['USER']
        DATABASE_PASSWORD = DATABASES['default']['PASSWORD']
        DATABASE_HOST = DATABASES['default']['HOST']
        DATABASE_PORT = DATABASES['default']['PORT']

# initialize settings from /etc/bcfg2.conf, or set up basic defaults.
# this lets manage.py work in all cases
read_config(quiet=True)

if django.VERSION[0] == 1 and django.VERSION[1] > 2:
    TIME_ZONE = None

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (('Root', 'root'))
MANAGERS = ADMINS

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

INSTALLED_APPS = ('Bcfg2.Server')

