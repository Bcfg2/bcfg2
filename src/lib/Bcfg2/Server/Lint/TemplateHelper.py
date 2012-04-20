import sys
import imp
import glob
import Bcfg2.Server.Lint
from Bcfg2.Server.Plugins.TemplateHelper import HelperModule

class TemplateHelper(Bcfg2.Server.Lint.ServerlessPlugin):
    """ find duplicate Pkgmgr entries with the same priority """
    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerlessPlugin.__init__(self, *args, **kwargs)
        hm = HelperModule("foo.py", None, None)
        self.reserved_keywords = dir(hm)

    def Run(self):
        for helper in glob.glob("%s/TemplateHelper/*.py" % self.config['repo']):
            if not self.HandlesFile(helper):
                continue

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
                continue

            if not hasattr(module, "__export__"):
                self.LintError("templatehelper-no-export",
                               "%s has no __export__ list" % helper)
                continue
            elif not isinstance(module.__export__, list):
                self.LintError("templatehelper-nonlist-export",
                               "__export__ is not a list in %s" % helper)
                continue

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

    def Errors(self):
        return {"templatehelper-import-error":"error",
                "templatehelper-no-export":"error",
                "templatehelper-nonlist-export":"error",
                "templatehelper-nonexistent-export":"error",
                "templatehelper-reserved-export":"error",
                "templatehelper-underscore-export":"warning"}
