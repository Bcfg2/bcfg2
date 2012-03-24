import re
import imp
import sys
import logging
import Bcfg2.Server.Plugin

logger = logging.getLogger(__name__)

class HelperModule(Bcfg2.Server.Plugin.SpecificData):
    _module_name_re = re.compile(r'([^/]+?)\.py')

    def __init__(self, name, specific, encoding):
        Bcfg2.Server.Plugin.SpecificData.__init__(self, name, specific,
                                                  encoding)
        match = self._module_name_re.search(self.name)
        if match:
            self._module_name = match.group(1)
        else:
            self._module_name = name
        self._attrs = []

    def handle_event(self, event):
        Bcfg2.Server.Plugin.SpecificData.handle_event(self, event)
        try:
            module = imp.load_source(self._module_name, self.name)
        except:
            err = sys.exc_info()[1]
            logger.error("TemplateHelper: Failed to import %s: %s" %
                         (self.name, err))
            return

        if not hasattr(module, "__export__"):
            logger.error("TemplateHelper: %s has no __export__ list" %
                         self.name)
            return

        for sym in module.__export__:
            if sym not in self._attrs and hasattr(self, sym):
                logger.warning("TemplateHelper: %s: %s is a reserved keyword, "
                               "skipping export" % (self.name, sym))
            setattr(self, sym, getattr(module, sym))
        # remove old exports
        for sym in set(self._attrs) - set(module.__export__):
            delattr(self, sym)

        self._attrs = module.__export__


class HelperSet(Bcfg2.Server.Plugin.EntrySet):
    ignore = re.compile("^(\.#.*|.*~|\\..*\\.(sw[px])|.*\.py[co])$")

    def __init__(self, path, fam, encoding, plugin_name):
        fpattern = '[0-9A-Za-z_\-]+\.py'
        self.plugin_name = plugin_name
        Bcfg2.Server.Plugin.EntrySet.__init__(self, fpattern, path,
                                              HelperModule, encoding)
        fam.AddMonitor(path, self)

    def HandleEvent(self, event):
        if (event.filename != self.path and
            not self.ignore.match(event.filename)):
            return self.handle_event(event)


class TemplateHelper(Bcfg2.Server.Plugin.Plugin,
                     Bcfg2.Server.Plugin.Connector):
    """ A plugin to provide helper classes and functions to templates """
    name = 'TemplateHelper'
    __author__ = 'chris.a.st.pierre@gmail.com'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)

        try:
            self.helpers = HelperSet(self.data, core.fam, core.encoding,
                                     self.name)
        except:
            raise Bcfg2.Server.Plugin.PluginInitError

    def get_additional_data(self, metadata):
        return dict([(h._module_name, h)
                     for h in list(self.helpers.entries.values())])
