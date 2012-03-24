import os.path
import Bcfg2.Options
import Bcfg2.Server.Lint

class InfoXML(Bcfg2.Server.Lint.ServerPlugin):
    """ ensure that all config files have an info.xml file"""

    def Run(self):
        if 'Cfg' in self.core.plugins:
            for filename, entryset in self.core.plugins['Cfg'].entries.items():
                infoxml_fname = os.path.join(entryset.path, "info.xml")
                if self.HandlesFile(infoxml_fname):
                    if (hasattr(entryset, "infoxml") and
                        entryset.infoxml is not None):
                        self.check_infoxml(infoxml_fname,
                                           entryset.infoxml.pnode.data)
                    else:
                        self.LintError("no-infoxml",
                                       "No info.xml found for %s" % filename)

    def check_infoxml(self, fname, xdata):
        for info in xdata.getroottree().findall("//Info"):
            required = []
            if "required_attrs" in self.config:
                required = self.config["required_attrs"].split(",")

            missing = [attr for attr in required if info.get(attr) is None]
            if missing:
                self.LintError("required-infoxml-attrs-missing",
                               "Required attribute(s) %s not found in %s:%s" %
                               (",".join(missing), fname, self.RenderXML(info)))

            if ((Bcfg2.Options.MDATA_PARANOID.value and
                 info.get("paranoid") is not None and
                 info.get("paranoid").lower() == "false") or
                (not Bcfg2.Options.MDATA_PARANOID.value and
                 (info.get("paranoid") is None or
                  info.get("paranoid").lower() != "true"))):
                self.LintError("paranoid-false",
                               "Paranoid must be true in %s:%s" %
                               (fname, self.RenderXML(info)))

