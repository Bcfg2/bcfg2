""" Check Jinja2 templates for syntax errors. """

import sys
import Bcfg2.Server.Lint
from jinja2 import Template, TemplateSyntaxError
from Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator import CfgJinja2Generator


class Jinja2(Bcfg2.Server.Lint.ServerPlugin):
    """ Check Jinja2 templates for syntax errors. """

    def Run(self):
        if 'Cfg' in self.core.plugins:
            self.check_cfg()

    @classmethod
    def Errors(cls):
        return {"jinja2-syntax-error": "error",
                "unknown-jinja2-error": "error"}

    def check_template(self, entry):
        """ Generic check for all jinja2 templates """
        try:
            Template(entry.data.decode(entry.encoding))
        except TemplateSyntaxError:
            err = sys.exc_info()[1]
            self.LintError("jinja2-syntax-error",
                           "Jinja2 syntax error in %s: %s" % (entry.name, err))
        except:
            err = sys.exc_info()[1]
            self.LintError("unknown-jinja2-error",
                           "Unknown Jinja2 error in %s: %s" % (entry.name,
                                                               err))

    def check_cfg(self):
        """ Check jinja2 templates in Cfg for syntax errors. """
        for entryset in self.core.plugins['Cfg'].entries.values():
            for entry in entryset.entries.values():
                if (self.HandlesFile(entry.name) and
                        isinstance(entry, CfgJinja2Generator)):
                    self.check_template(entry)
