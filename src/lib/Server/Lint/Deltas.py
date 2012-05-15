import Bcfg2.Server.Lint
from Bcfg2.Server.Plugins.Cfg import CfgFilter

class Deltas(Bcfg2.Server.Lint.ServerPlugin):
    """ Warn about usage of .cat and .diff files """

    def Run(self):
        """ run plugin """
        if 'Cfg' in self.core.plugins:
            cfg = self.core.plugins['Cfg']
            for basename, entry in list(cfg.entries.items()):
                self.check_entry(basename, entry)

    @classmethod
    def Errors(cls):
        return {"cat-file-used":"warning",
                "diff-file-used":"warning"}

    def check_entry(self, basename, entry):
        for fname, processor in entry.entries.items():
            if self.HandlesFile(fname) and isinstance(processor, CfgFilter):
                extension = fname.split(".")[-1]
                self.LintError("%s-file-used" % extension,
                               "%s file used on %s: %s" %
                               (extension, basename, fname))
