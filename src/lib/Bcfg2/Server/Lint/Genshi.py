""" Check Genshi templates for syntax errors. """

import sys
import Bcfg2.Server.Lint
from genshi.template import TemplateLoader, NewTextTemplate, MarkupTemplate, \
    TemplateSyntaxError
from Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator import CfgGenshiGenerator


class Genshi(Bcfg2.Server.Lint.ServerPlugin):
    """ Check Genshi templates for syntax errors. """

    def Run(self):
        if 'Cfg' in self.core.plugins:
            self.check_cfg()
        if 'Bundler' in self.core.plugins:
            self.check_bundler()

    @classmethod
    def Errors(cls):
        return {"genshi-syntax-error": "error",
                "unknown-genshi-error": "error"}

    def check_template(self, loader, fname, cls=None):
        """ Generic check for all genshi templates (XML and text) """
        try:
            loader.load(fname, cls=cls)
        except TemplateSyntaxError:
            err = sys.exc_info()[1]
            self.LintError("genshi-syntax-error",
                           "Genshi syntax error in %s: %s" % (fname, err))
        except:
            err = sys.exc_info()[1]
            self.LintError("unknown-genshi-error",
                           "Unknown Genshi error in %s: %s" % (fname, err))

    def check_cfg(self):
        """ Check genshi templates in Cfg for syntax errors. """
        for entryset in self.core.plugins['Cfg'].entries.values():
            for entry in entryset.entries.values():
                if (self.HandlesFile(entry.name) and
                        isinstance(entry, CfgGenshiGenerator) and
                        not entry.template):
                    self.check_template(entry.loader, entry.name,
                                        cls=NewTextTemplate)

    def check_bundler(self):
        """ Check templates in Bundler for syntax errors. """
        loader = TemplateLoader()
        for entry in self.core.plugins['Bundler'].entries.values():
            if (self.HandlesFile(entry.name) and
                    entry.template is not None):
                self.check_template(loader, entry.name, cls=MarkupTemplate)
