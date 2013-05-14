""" Ensure that all config files have a valid info.xml file. """

import os
import Bcfg2.Options
import Bcfg2.Server.Lint
from Bcfg2.Server.Plugins.Cfg.CfgInfoXML import CfgInfoXML
from Bcfg2.Server.Plugins.Cfg.CfgLegacyInfo import CfgLegacyInfo


class InfoXML(Bcfg2.Server.Lint.ServerPlugin):
    """ Ensure that all config files have a valid info.xml file. This
    plugin can check for:

    * Missing ``info.xml`` files;
    * Use of deprecated ``info``/``:info`` files;
    * Paranoid mode disabled in an ``info.xml`` file;
    * Required attributes missing from ``info.xml``
    """
    def Run(self):
        if 'Cfg' not in self.core.plugins:
            return

        for filename, entryset in self.core.plugins['Cfg'].entries.items():
            infoxml_fname = os.path.join(entryset.path, "info.xml")
            if self.HandlesFile(infoxml_fname):
                found = False
                for entry in entryset.entries.values():
                    if isinstance(entry, CfgInfoXML):
                        self.check_infoxml(infoxml_fname,
                                           entry.infoxml.pnode.data)
                        found = True
                if not found:
                    self.LintError("no-infoxml",
                                   "No info.xml found for %s" % filename)

            for entry in entryset.entries.values():
                if isinstance(entry, CfgLegacyInfo):
                    if not self.HandlesFile(entry.path):
                        continue
                    self.LintError("deprecated-info-file",
                                   "Deprecated %s file found at %s" %
                                   (os.path.basename(entry.name),
                                    entry.path))

    @classmethod
    def Errors(cls):
        return {"no-infoxml": "warning",
                "deprecated-info-file": "warning",
                "paranoid-false": "warning",
                "required-infoxml-attrs-missing": "error"}

    def check_infoxml(self, fname, xdata):
        """ Verify that info.xml contains everything it should. """
        for info in xdata.getroottree().findall("//Info"):
            required = []
            if "required_attrs" in self.config:
                required = self.config["required_attrs"].split(",")

            missing = [attr for attr in required if info.get(attr) is None]
            if missing:
                self.LintError("required-infoxml-attrs-missing",
                               "Required attribute(s) %s not found in %s:%s" %
                               (",".join(missing), fname,
                                self.RenderXML(info)))

            if ((Bcfg2.Options.MDATA_PARANOID.value and
                 info.get("paranoid") is not None and
                 info.get("paranoid").lower() == "false") or
                (not Bcfg2.Options.MDATA_PARANOID.value and
                 (info.get("paranoid") is None or
                  info.get("paranoid").lower() != "true"))):
                self.LintError("paranoid-false",
                               "Paranoid must be true in %s:%s" %
                               (fname, self.RenderXML(info)))
