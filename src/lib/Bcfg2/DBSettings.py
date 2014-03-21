""" Django settings for the Bcfg2 server """

import os
import sys
import logging
import Bcfg2.Logger
import Bcfg2.Options

try:
    import django
    import django.conf
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

# required for reporting
try:
    import south  # pylint: disable=W0611
    HAS_SOUTH = True
except ImportError:
    HAS_SOUTH = False

settings = dict(  # pylint: disable=C0103
    TIME_ZONE=None,
    TEMPLATE_DEBUG=False,
    DEBUG=False,
    ALLOWED_HOSTS=['*'],
    MEDIA_URL='/site_media/',
    MANAGERS=(('Root', 'root')),
    ADMINS=(('Root', 'root')),
    # Language code for this installation. All choices can be found
    # here:
    # http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
    # http://blogs.law.harvard.edu/tech/stories/storyReader$15
    LANGUAGE_CODE='en-us',
    SITE_ID=1,
    INSTALLED_APPS=('django.contrib.auth',
                    'django.contrib.contenttypes',
                    'django.contrib.sessions',
                    'django.contrib.sites',
                    'django.contrib.admin',
                    'Bcfg2.Server'),
    MEDIA_ROOT='',
    STATIC_URL='/media/',
    # TODO - make this unique
    SECRET_KEY='eb5+y%oy-qx*2+62vv=gtnnxg1yig_odu0se5$h0hh#pc*lmo7',
    TEMPLATE_LOADERS=('django.template.loaders.filesystem.Loader',
                      'django.template.loaders.app_directories.Loader'),
    MIDDLEWARE_CLASSES=(
        'django.middleware.common.CommonMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.middleware.doc.XViewMiddleware'),
    ROOT_URLCONF='Bcfg2.Reporting.urls',
    AUTHENTICATION_BACKENDS=('django.contrib.auth.backends.ModelBackend'),
    LOGIN_URL='/login',
    SESSION_EXPIRE_AT_BROWSER_CLOSE=True,
    TEMPLATE_DIRS=(
        '/usr/share/python-support/python-django/django/contrib/admin/'
        'templates/'),
    TEMPLATE_CONTEXT_PROCESSORS=(
        'django.contrib.auth.context_processors.auth',
        'django.core.context_processors.debug',
        'django.core.context_processors.i18n',
        'django.core.context_processors.media',
        'django.core.context_processors.request'),
    DATABASE_ROUTERS = ['Bcfg2.DBSettings.PerApplicationRouter'])

if HAS_SOUTH:
    settings['INSTALLED_APPS'] += ('south', 'Bcfg2.Reporting')
if 'BCFG2_LEGACY_MODELS' in os.environ:
    settings['INSTALLED_APPS'] += ('Bcfg2.Server.Reports.reports',)

if HAS_DJANGO and django.VERSION[0] == 1 and django.VERSION[1] < 3:
    settings['CACHE_BACKEND'] = 'locmem:///'
else:
    settings['CACHES'] = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }


def finalize_django_config(opts=None, silent=False):
    """ Perform final Django configuration """
    if opts is None:
        opts = Bcfg2.Options.setup
    settings['DATABASES'] = dict(
        default=dict(
            ENGINE="django.db.backends.%s" % opts.db_engine,
            NAME=opts.db_name,
            USER=opts.db_user,
            PASSWORD=opts.db_password,
            HOST=opts.db_host,
            PORT=opts.db_port,
            OPTIONS=opts.db_opts,
            SCHEMA=opts.db_schema))

    if opts.reporting_db_engine is not None:
        settings['DATABASES']['Reporting'] = dict(
            ENGINE="django.db.backends.%s" % opts.reporting_db_engine,
            NAME=opts.reporting_db_name,
            USER=opts.reporting_db_user,
            PASSWORD=opts.reporting_db_password,
            HOST=opts.reporting_db_host,
            PORT=opts.reporting_db_port,
            OPTIONS=opts.reporting_db_opts,
            SCHEMA=opts.reporting_db_schema)

    settings['TIME_ZONE'] = opts.timezone

    settings['TEMPLATE_DEBUG'] = settings['DEBUG'] = \
        opts.web_debug
    if opts.web_debug:
        print("Warning: Setting web_debug to True causes extraordinary "
              "memory leaks.  Only use this setting if you know what "
              "you're doing.")

    if opts.web_prefix:
        settings['MEDIA_URL'] = \
            opts.web_prefix.rstrip('/') + \
            settings['MEDIA_URL']

    logger = logging.getLogger()

    logger.debug("Finalizing Django settings: %s" % settings)
    module = sys.modules[__name__]
    for name, value in settings.items():
        setattr(module, name, value)
    try:
        django.conf.settings.configure(**settings)
    except RuntimeError:
        if not silent:
            logger.warning("Failed to finalize Django settings: %s" %
                           sys.exc_info()[1])


def sync_databases(**kwargs):
    """ Synchronize all databases that we know about.  """
    logger = logging.getLogger()
    for database in settings['DATABASES']:
        logger.debug("Syncing database %s" % (database))
        django.core.management.call_command("syncdb", database=database,
                                            **kwargs)


def migrate_databases(**kwargs):
    """ Do South migrations on all databases that we know about.  """
    logger = logging.getLogger()
    for database in settings['DATABASES']:
        logger.debug("Migrating database %s" % (database))
        django.core.management.call_command("migrate", database=database,
                                            **kwargs)


class PerApplicationRouter(object):
    """ Django database router for redirecting different applications to their
    own database """

    def _db_per_app(self, model, **hints):
        """ If a database with the same name as the application exists, use it.
        Otherwise use the default """
        app = model._meta.app_label
        if app in settings['DATABASES']:
            return app

        return 'default'

    def db_for_read(self, model, **hints):
        """ Called when Django wants to find out what database to read from """
        return self._db_per_app(model, **hints)

    def db_for_write(self, model, **hints):
        """ Called when Django wants to find out what database to write to """
        return self._db_per_app(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        """ Called when Django wants to determine what relations to allow. Only
        allow relations within an app """
        return obj1._meta.app_label == obj2._meta.app_label

    def allow_syncdb(self, db, model):
        """ Called when Django wants to determine which models to sync to a
        given database.  Take the cowards way out and sync all models to all
        databases to allow for easy migrations. """
        return True


class _OptionContainer(object):
    """ Container for options loaded at import-time to configure
    databases """
    parse_first = True
    options = [
        Bcfg2.Options.Common.repository,
        Bcfg2.Options.PathOption(
            '-W', '--web-config', cf=('reporting', 'config'),
            default="/etc/bcfg2-web.conf",
            action=Bcfg2.Options.ConfigFileAction,
            help='Web interface configuration file'),
        # default database options
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
            cf=('database', 'schema'), help='Database schema',
            dest='db_schema', default='public'),
        Bcfg2.Options.Option(
            cf=('database', 'options'), help='Database options',
            dest='db_opts', type=Bcfg2.Options.Types.comma_dict,
            default=dict()),
        # reporting database options
        Bcfg2.Options.Option(
            cf=('database', 'reporting_engine'),
            help='Reporting database engine', dest='reporting_db_engine'),
        Bcfg2.Options.Option(
            cf=('database', 'reporting_name'),
            default='<repository>/etc/reporting.sqlite',
            help="Reporting database name", dest="reporting_db_name"),
        Bcfg2.Options.Option(
            cf=('database', 'reporting_user'),
            help='Reporting database username', dest='reporting_db_user'),
        Bcfg2.Options.Option(
            cf=('database', 'reporting_password'),
            help='Reporting database password', dest='reporting_db_password'),
        Bcfg2.Options.Option(
            cf=('database', 'reporting_host'),
            help='Reporting database host', dest='reporting_db_host'),
        Bcfg2.Options.Option(
            cf=('database', 'reporting_port'),
            help='Reporting database port', dest='reporting_db_port'),
        Bcfg2.Options.Option(
            cf=('database', 'reporting_schema'),
            help='Reporting database schema', dest='reporting_db_schema',
            default='public'),
        Bcfg2.Options.Option(
            cf=('database', 'reporting_options'),
            help='Reporting database options', dest='reporting_db_opts',
            type=Bcfg2.Options.Types.comma_dict, default=dict()),
        # Django options
        Bcfg2.Options.Option(
            cf=('reporting', 'timezone'), help='Django timezone'),
        Bcfg2.Options.BooleanOption(
            cf=('reporting', 'web_debug'), help='Django debug'),
        Bcfg2.Options.Option(
            cf=('reporting', 'web_prefix'), help='Web prefix')]

    @staticmethod
    def component_parsed_hook(opts):
        """ Finalize the Django config after this component's options
        are parsed. """
        finalize_django_config(opts=opts)

    @staticmethod
    def options_parsed_hook():
        """ Finalize the Django config after all options are parsed.
        This is added in case the DBSettings component isn't added
        early enough in option parsing to be parsed in the 'early'
        phase.  Chances are good that things will break if that
        happens, but we do our best to be a good citizen. """
        finalize_django_config(silent=True)

Bcfg2.Options.get_parser().add_component(_OptionContainer)
