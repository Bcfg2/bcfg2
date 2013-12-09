""" Check for templated scripts or executables. """

import os
import stat
import Bcfg2.Server.Lint
from Bcfg2.Compat import any  # pylint: disable=W0622
from Bcfg2.Server.Plugin import DEFAULT_FILE_METADATA
from Bcfg2.Server.Plugins.Cfg.CfgInfoXML import CfgInfoXML
from Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator import CfgGenshiGenerator
from Bcfg2.Server.Plugins.Cfg.CfgCheetahGenerator import CfgCheetahGenerator
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenshiGenerator import \
    CfgEncryptedGenshiGenerator
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedCheetahGenerator import \
    CfgEncryptedCheetahGenerator


class TemplateAbuse(Bcfg2.Server.Lint.ServerPlugin):
    """ Check for templated scripts or executables. """
    templates = [CfgGenshiGenerator, CfgCheetahGenerator,
                 CfgEncryptedGenshiGenerator, CfgEncryptedCheetahGenerator]
    extensions = [".pl", ".py", ".sh", ".rb"]

    def Run(self):
        if 'Cfg' in self.core.plugins:
            for entryset in self.core.plugins['Cfg'].entries.values():
                for entry in entryset.entries.values():
                    if (self.HandlesFile(entry.name) and
                        any(isinstance(entry, t) for t in self.templates)):
                        self.check_template(entryset, entry)

    @classmethod
    def Errors(cls):
        return {"templated-script": "warning",
                "templated-executable": "warning"}

    def check_template(self, entryset, entry):
        """ Check a template to see if it's a script or an executable. """
        # first, check for a known script extension
        ext = os.path.splitext(entryset.path)[1]
        if ext in self.extensions:
            self.LintError("templated-script",
                           "Templated script found: %s\n"
                           "File has a known script extension: %s\n"
                           "Template a config file for the script instead" %
                           (entry.name, ext))
            return

        # next, check for a shebang line
        firstline = open(entry.name).readline()
        if firstline.startswith("#!"):
            self.LintError("templated-script",
                           "Templated script found: %s\n"
                           "File starts with a shebang: %s\n"
                           "Template a config file for the script instead" %
                           (entry.name, firstline))
            return

        # finally, check for executable permissions in info.xml
        for entry in entryset.entries.values():
            if isinstance(entry, CfgInfoXML):
                for pinfo in entry.infoxml.pnode.data.xpath("//FileInfo"):
                    try:
                        mode = int(pinfo.get("mode",
                                             DEFAULT_FILE_METADATA['mode']), 8)
                    except ValueError:
                        # LintError will be produced by RequiredAttrs plugin
                        self.logger.warning("Non-octal mode: %s" % mode)
                        continue
                    if mode & stat.S_IXUSR != 0:
                        self.LintError(
                            "templated-executable",
                            "Templated executable found: %s\n"
                            "Template a config file for the executable instead"
                            % entry.name)
                        return
