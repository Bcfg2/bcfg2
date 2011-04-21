import os.path
import Bcfg2.Options
import Bcfg2.Server.Lint

class InfoXML(Bcfg2.Server.Lint.ServerPlugin):
    """ ensure that all config files have an info.xml file"""

    @Bcfg2.Server.Lint.returnErrors
    def Run(self):
        for filename, entryset in self.core.plugins['Cfg'].entries.items():
            infoxml_fname = os.path.join(entryset.path, "info.xml")
            if self.HandlesFile(infoxml_fname):
                if (hasattr(entryset, "infoxml") and
                    entryset.infoxml is not None):
                    xdata = entryset.infoxml.pnode.data
                    for info in xdata.getroottree().findall("//Info"):
                        required = []
                        if "required_attrs" in self.config:
                            required = self.config["required_attrs"].split(",")

                        missing = [attr for attr in required
                                   if info.get(attr) is None]
                        if missing:
                            self.LintError("Required attribute(s) %s not found in %s:%s" %
                                           (",".join(missing), infoxml_fname,
                                            self.RenderXML(info)))

                        if ("require_paranoid" in self.config and
                            self.config["require_paranoid"].lower() == "true" and
                            (Bcfg2.Options.MDATA_PARANOID.value and
                             info.get("paranoid") is not None and
                             info.get("paranoid").lower() == "false") or
                            (not Bcfg2.Options.MDATA_PARANOID.value and
                             (info.get("paranoid") is None or
                              info.get("paranoid").lower() != "true"))):
                            self.LintError("Paranoid must be true in %s:%s" %
                                           (infoxml_fname,
                                            self.RenderXML(info)))
                elif ("require" in self.config and
                      self.config["require"].lower != "false"):
                    self.LintError("No info.xml found for %s" % filename)

