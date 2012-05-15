import Bcfg2.Server.Lint

class Deltas(Bcfg2.Server.Lint.ServerPlugin):
    """ Warn about usage of .cat and .diff files """

    def Run(self):
        """ run plugin """
        if 'Cfg' in self.core.plugins:
            cfg = self.core.plugins['Cfg']
            for basename, entry in list(cfg.entries.items()):
                self.check_entry(basename, entry)

    def check_entry(self, basename, entry):
        for fname in list(entry.entries.keys()):
            if self.HandlesFile(fname):
                match = entry.specific.delta_reg.match(fname)
                if match:
                    self.LintError("%s-file-used" % match.group('delta'),
                                   "%s file used on %s: %s" %
                                   (match.group('delta'), basename, fname))
