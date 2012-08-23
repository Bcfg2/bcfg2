import re
import imp
import sys
import glob
import logging
import Bcfg2.Server.Lint
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
    fpattern = '[0-9A-Za-z_\-]+\.py'
    basename_is_regex = True

    def __init__(self, path, fam, encoding, plugin_name):
        self.plugin_name = plugin_name
        Bcfg2.Server.Plugin.EntrySet.__init__(self, self.fpattern, path,
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
                     for h in self.helpers.get_matching(metadata)])


class TemplateHelperLint(Bcfg2.Server.Lint.ServerlessPlugin):
    """ find duplicate Pkgmgr entries with the same priority """
    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerlessPlugin.__init__(self, *args, **kwargs)
        hm = HelperModule("foo.py", None, None)
        self.reserved_keywords = dir(hm)

    def Run(self):
        for helper in glob.glob(os.path.join(self.config['repo'],
                                             "TemplateHelper",
                                             "*.py")):
            if not self.HandlesFile(helper):
                continue
            self.check_helper(helper)

    def check_helper(self, helper):
        match = HelperModule._module_name_re.search(helper)
        if match:
            module_name = match.group(1)
        else:
            module_name = helper

        try:
            module = imp.load_source(module_name, helper)
        except:
            err = sys.exc_info()[1]
            self.LintError("templatehelper-import-error",
                           "Failed to import %s: %s" %
                           (helper, err))
            return

        if not hasattr(module, "__export__"):
            self.LintError("templatehelper-no-export",
                           "%s has no __export__ list" % helper)
            return
        elif not isinstance(module.__export__, list):
            self.LintError("templatehelper-nonlist-export",
                           "__export__ is not a list in %s" % helper)
            return

        for sym in module.__export__:
            if not hasattr(module, sym):
                self.LintError("templatehelper-nonexistent-export",
                               "%s: exported symbol %s does not exist" %
                               (helper, sym))
            elif sym in self.reserved_keywords:
                self.LintError("templatehelper-reserved-export",
                               "%s: exported symbol %s is reserved" %
                               (helper, sym))
            elif sym.startswith("_"):
                self.LintError("templatehelper-underscore-export",
                               "%s: exported symbol %s starts with underscore" %
                               (helper, sym))

    @classmethod
    def Errors(cls):
        return {"templatehelper-import-error":"error",
                "templatehelper-no-export":"error",
                "templatehelper-nonlist-export":"error",
                "templatehelper-nonexistent-export":"error",
                "templatehelper-reserved-export":"error",
                "templatehelper-underscore-export":"warning"}
