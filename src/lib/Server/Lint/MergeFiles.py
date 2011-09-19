import os
from copy import deepcopy
from difflib import SequenceMatcher
import Bcfg2.Server.Lint

class MergeFiles(Bcfg2.Server.Lint.ServerPlugin):
    """ find Probes or Cfg files with multiple similar files that
    might be merged into one """

    def Run(self):
        if 'Cfg' in self.core.plugins:
            self.check_cfg()
        if 'Probes' in self.core.plugins:
            self.check_probes()

    def check_cfg(self):
        for filename, entryset in self.core.plugins['Cfg'].entries.items():
            for mset in self.get_similar(entryset.entries):
                self.LintError("merge-cfg",
                               "The following files are similar: %s. "
                               "Consider merging them into a single Genshi "
                               "template." %
                               ", ".join([os.path.join(filename, p)
                                          for p in mset]))

    def check_probes(self):
        probes = self.core.plugins['Probes'].probes.entries
        for mset in self.get_similar(probes):
            self.LintError("merge-cfg",
                           "The following probes are similar: %s. "
                           "Consider merging them into a single probe." %
                           ", ".join([p for p in mset]))

    def get_similar(self, entries):
        if "threshold" in self.config:
            # accept threshold either as a percent (e.g., "threshold=75") or
            # as a ratio (e.g., "threshold=.75")
            threshold = float(self.config['threshold'])
            if threshold > 1:
                threshold /= 100
        else:
            threshold = 0.75
        rv = []
        elist = entries.items()
        while elist:
            result = self._find_similar(elist.pop(0), deepcopy(elist),
                                        threshold)
            if len(result) > 1:
                elist = [(fname, fdata)
                         for fname, fdata in elist
                         if fname not in result]
                rv.append(result)
        return rv

    def _find_similar(self, ftuple, others, threshold):
        fname, fdata = ftuple
        rv = [fname]
        while others:
            cname, cdata = others.pop(0)
            sm = SequenceMatcher(None, fdata.data, cdata.data)
            # perform progressively more expensive comparisons
            if (sm.real_quick_ratio() > threshold and
                sm.quick_ratio() > threshold and
                sm.ratio() > threshold):
                rv.extend(self._find_similar((cname, cdata), deepcopy(others),
                                             threshold))
        return rv

        
