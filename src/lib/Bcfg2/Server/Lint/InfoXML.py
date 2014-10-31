""" Ensure that all config files have a valid info.xml file. """

import os
import Bcfg2.Options
import Bcfg2.Server.Lint
from Bcfg2.Server.Plugins.Cfg.CfgInfoXML import CfgInfoXML


class InfoXML(Bcfg2.Server.Lint.ServerPlugin):
    """ Ensure that all config files have a valid info.xml file. This
    plugin can check for:

    * Missing ``info.xml`` files;
    * Use of deprecated ``info``/``:info`` files;
    * Paranoid mode disabled in an ``info.xml`` file;
    * Required attributes missing from ``info.xml``
    """
    __serverplugin__ = 'Cfg'

    options = Bcfg2.Server.Lint.ServerPlugin.options + [
        Bcfg2.Options.Common.default_paranoid,
        Bcfg2.Options.Option(
            cf=("InfoXML", "required_attrs"),
            type=Bcfg2.Options.Types.comma_list,
            default=["owner", "group", "mode"],
            help="Attributes to require on <Info> tags")]

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
                                           entry.infoxml.xdata)
                        found = True
                if not found:
                    self.LintError("no-infoxml",
                                   "No info.xml found for %s" % filename)

    @classmethod
    def Errors(cls):
        return {"no-infoxml": "warning",
                "paranoid-false": "warning",
                "required-infoxml-attrs-missing": "error"}

    def check_infoxml(self, fname, xdata):
        """ Verify that info.xml contains everything it should. """
        for info in xdata.getroottree().findall("//Info"):
            required = []
            required = Bcfg2.Options.setup.required_attrs

            missing = [attr for attr in required if info.get(attr) is None]
            if missing:
                self.LintError("required-infoxml-attrs-missing",
                               "Required attribute(s) %s not found in %s:%s" %
                               (",".join(missing), fname,
                                self.RenderXML(info)))

            if ((Bcfg2.Options.setup.default_paranoid == "true" and
                 info.get("paranoid") is not None and
                 info.get("paranoid").lower() == "false") or
                (Bcfg2.Options.setup.default_paranoid == "false" and
                 (info.get("paranoid") is None or
                  info.get("paranoid").lower() != "true"))):
                self.LintError("paranoid-false",
                               "Paranoid must be true in %s:%s" %
                               (fname, self.RenderXML(info)))
