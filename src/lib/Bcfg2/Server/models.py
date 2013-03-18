""" Django database models for all plugins """

import sys
import copy
import logging
import Bcfg2.Options
import Bcfg2.Server.Plugins
from django.db import models

LOGGER = logging.getLogger('Bcfg2.Server.models')

MODELS = []


def load_models(plugins=None, cfile='/etc/bcfg2.conf', quiet=True):
    """ load models from plugins specified in the config """
    global MODELS

    if plugins is None:
        # we want to provide a different default plugin list --
        # namely, _all_ plugins, so that the database is guaranteed to
        # work, even if /etc/bcfg2.conf isn't set up properly
        plugin_opt = copy.deepcopy(Bcfg2.Options.SERVER_PLUGINS)
        plugin_opt.default = Bcfg2.Server.Plugins.__all__

        setup = \
            Bcfg2.Options.OptionParser(dict(plugins=plugin_opt,
                                            configfile=Bcfg2.Options.CFILE),
                                       quiet=quiet)
        setup.parse([Bcfg2.Options.CFILE.cmd, cfile])
        plugins = setup['plugins']

    if MODELS:
        # load_models() has been called once, so first unload all of
        # the models; otherwise we might call load_models() with no
        # arguments, end up with _all_ models loaded, and then in a
        # subsequent call only load a subset of models
        for model in MODELS:
            delattr(sys.modules[__name__], model)
        MODELS = []

    for plugin in plugins:
        try:
            mod = getattr(__import__("Bcfg2.Server.Plugins.%s" %
                                     plugin).Server.Plugins, plugin)
        except ImportError:
            try:
                err = sys.exc_info()[1]
                mod = __import__(plugin)
            except:  # pylint: disable=W0702
                if plugins != Bcfg2.Server.Plugins.__all__:
                    # only produce errors if the default plugin list
                    # was not used -- i.e., if the config file was set
                    # up.  don't produce errors when trying to load
                    # all plugins, IOW.  the error from the first
                    # attempt to import is probably more accurate than
                    # the second attempt.
                    LOGGER.error("Failed to load plugin %s: %s" % (plugin,
                                                                   err))
                    continue
        for sym in dir(mod):
            obj = getattr(mod, sym)
            if hasattr(obj, "__bases__") and models.Model in obj.__bases__:
                setattr(sys.modules[__name__], sym, obj)
                MODELS.append(sym)

# basic invocation to ensure that a default set of models is loaded,
# and thus that this module will always work.
load_models(quiet=True)


class InternalDatabaseVersion(models.Model):
    """ Object that tell us to which version the database is """
    version = models.IntegerField()
    updated = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "version %d updated the %s" % (self.version,
                                              self.updated.isoformat())

    class Meta:  # pylint: disable=C0111,W0232
        app_label = "reports"
        get_latest_by = "version"
