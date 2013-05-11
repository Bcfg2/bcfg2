""" find Probes or Cfg files with multiple similar files that might be
merged into one """

import os
import copy
from difflib import SequenceMatcher
import Bcfg2.Server.Lint
from Bcfg2.Server.Plugins.Cfg import CfgGenerator


class MergeFiles(Bcfg2.Server.Lint.ServerPlugin):
    """ find Probes or Cfg files with multiple similar files that
    might be merged into one """
    def Run(self):
        if 'Cfg' in self.core.plugins:
            self.check_cfg()
        if 'Probes' in self.core.plugins:
            self.check_probes()

    @classmethod
    def Errors(cls):
        return {"merge-cfg": "warning",
                "merge-probes": "warning"}

    def check_cfg(self):
        """ check Cfg for similar files """
        for filename, entryset in self.core.plugins['Cfg'].entries.items():
            candidates = dict([(f, e) for f, e in entryset.entries.items()
                               if isinstance(e, CfgGenerator)])
            for mset in self.get_similar(candidates):
                self.LintError("merge-cfg",
                               "The following files are similar: %s. "
                               "Consider merging them into a single Genshi "
                               "template." %
                               ", ".join([os.path.join(filename, p)
                                          for p in mset]))

    def check_probes(self):
        """ check Probes for similar files """
        probes = self.core.plugins['Probes'].probes.entries
        for mset in self.get_similar(probes):
            self.LintError("merge-probes",
                           "The following probes are similar: %s. "
                           "Consider merging them into a single probe." %
                           ", ".join([p for p in mset]))

    def get_similar(self, entries):
        """ Get a list of similar files from the entry dict.  Return
        value is a list of lists, each of which gives the filenames of
        similar files """
        if "threshold" in self.config:
            # accept threshold either as a percent (e.g., "threshold=75") or
            # as a ratio (e.g., "threshold=.75")
            threshold = float(self.config['threshold'])
            if threshold > 1:
                threshold /= 100
        else:
            threshold = 0.75
        rv = []
        elist = list(entries.items())
        while elist:
            result = self._find_similar(elist.pop(0), copy.copy(elist),
                                        threshold)
            if len(result) > 1:
                elist = [(fname, fdata)
                         for fname, fdata in elist
                         if fname not in result]
                rv.append(result)
        return rv

    def _find_similar(self, ftuple, others, threshold):
        """ Find files similar to the one described by ftupe in the
        list of other files.  ftuple is a tuple of (filename, data);
        others is a list of such tuples.  threshold is a float between
        0 and 1 that describes how similar two files much be to rate
        as 'similar' """
        fname, fdata = ftuple
        rv = [fname]
        while others:
            cname, cdata = others.pop(0)
            seqmatch = SequenceMatcher(None, fdata.data, cdata.data)
            # perform progressively more expensive comparisons
            if (seqmatch.real_quick_ratio() > threshold and
                seqmatch.quick_ratio() > threshold and
                seqmatch.ratio() > threshold):
                rv.extend(self._find_similar((cname, cdata), copy.copy(others),
                                             threshold))
        return rv
