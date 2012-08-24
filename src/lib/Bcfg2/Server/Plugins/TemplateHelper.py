import re
import imp
import sys
import glob
import logging
import Bcfg2.Server.Lint
import Bcfg2.Server.Plugin

logger = logging.getLogger(__name__)

module_pattern = r'(?P<filename>(?P<module>[^\/]+)\.py)$'
module_re = re.compile(module_pattern)

class HelperModule(Bcfg2.Server.Plugin.FileBacked):
    def __init__(self, name, fam=None):
        Bcfg2.Server.Plugin.FileBacked.__init__(self, name, fam=fam)
        self._module_name = module_re.search(self.name).group('module')
        self._attrs = []

    def Index(self):
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

        newattrs = []
        for sym in module.__export__:
            if sym not in self._attrs and hasattr(self, sym):
                logger.warning("TemplateHelper: %s: %s is a reserved keyword, "
                               "skipping export" % (self.name, sym))
                continue
            try:
                setattr(self, sym, getattr(module, sym))
                newattrs.append(sym)
            except AttributeError:
                logger.warning("TemplateHelper: %s: %s exports %s, but has no "
                               "such attribute" % (self.name, sym))
        # remove old exports
        for sym in set(self._attrs) - set(newattrs):
            delattr(self, sym)

        self._attrs = newattrs


class HelperSet(Bcfg2.Server.Plugin.DirectoryBacked):
    ignore = re.compile("^(\.#.*|.*~|\\..*\\.(sw[px])|.*\.py[co])$")
    patterns = module_re
    __child__ = HelperModule


class TemplateHelper(Bcfg2.Server.Plugin.Plugin,
                     Bcfg2.Server.Plugin.Connector):
    """ A plugin to provide helper classes and functions to templates """
    name = 'TemplateHelper'
    __author__ = 'chris.a.st.pierre@gmail.com'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.helpers = HelperSet(self.data, core.fam)

    def get_additional_data(self, _):
        return dict([(h._module_name, h)
                     for h in self.helpers.entries.values()])


class TemplateHelperLint(Bcfg2.Server.Lint.ServerlessPlugin):
    """ find duplicate Pkgmgr entries with the same priority """
    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerlessPlugin.__init__(self, *args, **kwargs)
        hm = HelperModule("foo.py")
        self.reserved_keywords = dir(hm)

    def Run(self):
        for fname in os.listdir(os.path.join(self.config['repo'],
                                             "TemplateHelper")):
            helper = os.path.join(self.config['repo'], "TemplateHelper",
                                  fname)
            if not module_re.search(helper) or not self.HandlesFile(helper):
                continue
            self.check_helper(helper)

    def check_helper(self, helper):
        module_name = module_re.search(helper).group(1)

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
