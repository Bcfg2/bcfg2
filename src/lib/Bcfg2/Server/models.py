""" Django database models for all plugins """

import sys
import logging
import Bcfg2.Options
import Bcfg2.Server.Plugins

LOGGER = logging.getLogger(__name__)

MODELS = []
INTERNAL_DATABASE_VERSION = None


class _OptionContainer(object):
    """Options for Bcfg2 database models."""

    # we want to provide a different default plugin list --
    # namely, _all_ plugins, so that the database is guaranteed to
    # work, even if /etc/bcfg2.conf isn't set up properly
    options = [Bcfg2.Options.Common.plugins]

    @staticmethod
    def options_parsed_hook():
        # basic invocation to ensure that a default set of models is
        # loaded, and thus that this module will always work.
        load_models()

Bcfg2.Options.get_parser().add_component(_OptionContainer)


def load_models(plugins=None):
    """ load models from plugins specified in the config """
    # this has to be imported after options are parsed, because Django
    # finalizes its settings as soon as it's loaded, which means that
    # if we import this before Bcfg2.DBSettings has been populated,
    # Django gets a null configuration, and subsequent updates to
    # Bcfg2.DBSettings won't help.
    from django.db import models
    global MODELS

    if not plugins:
        plugins = Bcfg2.Options.setup.plugins

    if MODELS:
        # load_models() has been called once, so first unload all of
        # the models; otherwise we might call load_models() with no
        # arguments, end up with _all_ models loaded, and then in a
        # subsequent call only load a subset of models
        for model in MODELS:
            delattr(sys.modules[__name__], model)
        MODELS = []

    for mod in plugins:
        for sym in dir(mod):
            obj = getattr(mod, sym)
            if isinstance(obj, type) and issubclass(obj, models.Model):
                setattr(sys.modules[__name__], sym, obj)
                MODELS.append(sym)

def internal_database_version():
    global INTERNAL_DATABASE_VERSION

    if INTERNAL_DATABASE_VERSION is None:
        from django.db import models
        class InternalDatabaseVersion(models.Model):
            """ Object that tell us to which version the database is """
            version = models.IntegerField()
            updated = models.DateTimeField(auto_now_add=True)

            def __str__(self):
                return "version %d updated %s" % (self.version,
                                                  self.updated.isoformat())

            class Meta:  # pylint: disable=C0111,W0232
                app_label = "reports"
                get_latest_by = "version"
        INTERNAL_DATABASE_VERSION = InternalDatabaseVersion

    return INTERNAL_DATABASE_VERSION.objects
