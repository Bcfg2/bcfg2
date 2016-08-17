""" Django database models for all plugins """

import sys
import logging
import Bcfg2.Options
import Bcfg2.Server.Plugins
from Bcfg2.Compat import walk_packages

LOGGER = logging.getLogger('Bcfg2.Server.models')

MODELS = []
INTERNAL_DATABASE_VERSION = None


def _get_all_plugins():
    rv = []
    for submodule in walk_packages(path=Bcfg2.Server.Plugins.__path__,
                                   prefix="Bcfg2.Server.Plugins."):
        module = submodule[1].rsplit('.', 1)[-1]
        if submodule[1] == "Bcfg2.Server.Plugins.%s" % module:
            # we only include direct children of
            # Bcfg2.Server.Plugins -- e.g., all_plugins should
            # include Bcfg2.Server.Plugins.Cfg, but not
            # Bcfg2.Server.Plugins.Cfg.CfgInfoXML
            rv.append(module)
    return rv


_ALL_PLUGINS = _get_all_plugins()


class _OptionContainer(object):
    # we want to provide a different default plugin list --
    # namely, _all_ plugins, so that the database is guaranteed to
    # work, even if /etc/bcfg2.conf isn't set up properly
    options = [
        Bcfg2.Options.Option(
            cf=('server', 'plugins'), type=Bcfg2.Options.Types.comma_list,
            default=_ALL_PLUGINS, dest="models_plugins",
            action=Bcfg2.Options.PluginsAction)]

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
        plugins = Bcfg2.Options.setup.models_plugins

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
