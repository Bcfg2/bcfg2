""" find Probes or Cfg files with multiple similar files that might be
merged into one """

import os
import copy
from difflib import SequenceMatcher
import Bcfg2.Server.Lint
from Bcfg2.Server.Plugins.Cfg import CfgGenerator


def threshold(val):
    """ Option type processor to accept either a percentage (e.g.,
     "threshold=75") or a ratio (e.g., "threshold=.75") """
    rv = float(val)
    if rv > 1:
        rv /= 100
    return rv


class MergeFiles(Bcfg2.Server.Lint.ServerPlugin):
    """ find Probes or Cfg files with multiple similar files that
    might be merged into one """

    options = Bcfg2.Server.Lint.ServerPlugin.options + [
        Bcfg2.Options.Option(
            cf=("MergeFiles", "threshold"), default="0.75", type=threshold,
            help="The threshold at which to suggest merging files and probes")]

    def Run(self):
        if 'Cfg' in self.core.plugins:
            self.check_cfg()
        if 'Probes' in self.core.plugins:
            self.check_probes()

    @classmethod
    def Errors(cls):
        return {"merge-cfg": "warning",
                "identical-cfg": "error",
                "merge-probes": "warning",
                "identical-probes": "error"}

    def check_cfg(self):
        """ check Cfg for similar files """
        # ignore non-specific Cfg entries, e.g., privkey.xml
        ignore = []
        for hdlr in Bcfg2.Options.setup.cfg_handlers:
            if not hdlr.__specific__:
                ignore.extend(hdlr.__basenames__)

        for filename, entryset in self.core.plugins['Cfg'].entries.items():
            candidates = dict([(f, e) for f, e in entryset.entries.items()
                               if (isinstance(e, CfgGenerator) and
                                   f not in ignore and
                                   not f.endswith(".crypt"))])
            similar, identical = self.get_similar(candidates)
            for mset in similar:
                self.LintError("merge-cfg",
                               "The following files are similar: %s. "
                               "Consider merging them into a single Genshi "
                               "template." %
                               ", ".join([os.path.join(filename, p)
                                          for p in mset]))

            for mset in identical:
                self.LintError("identical-cfg",
                               "The following files are identical: %s. "
                               "Strongly consider merging them into a single "
                               "Genshi template." %
                               ", ".join([os.path.join(filename, p)
                                          for p in mset]))

    def check_probes(self):
        """ check Probes for similar files """
        probes = self.core.plugins['Probes'].probes.entries
        similar, identical = self.get_similar(probes)
        for mset in similar:
            self.LintError("merge-probes",
                           "The following probes are similar: %s. "
                           "Consider merging them into a single probe." %
                           ", ".join([p for p in mset]))
        for mset in identical:
            self.LintError("identical-probes",
                           "The following probes are identical: %s. "
                           "Strongly consider merging them into a single "
                           "probe." %
                           ", ".join([p for p in mset]))

    def get_similar(self, entries):
        """ Get a list of similar files from the entry dict.  Return
        value is a list of lists, each of which gives the filenames of
        similar files """
        similar = []
        identical = []
        elist = list(entries.items())
        while elist:
            rv = self._find_similar(elist.pop(0), copy.copy(elist))
            if rv[0]:
                similar.append(rv[0])
            if rv[1]:
                identical.append(rv[1])
            elist = [(fname, fdata)
                     for fname, fdata in elist
                     if fname not in rv[0] | rv[1]]
        return similar, identical

    def _find_similar(self, ftuple, others):
        """ Find files similar to the one described by ftupe in the
        list of other files.  ftuple is a tuple of (filename, data);
        others is a list of such tuples.  threshold is a float between
        0 and 1 that describes how similar two files much be to rate
        as 'similar' """
        fname, fdata = ftuple
        similar = set()
        identical = set()
        for cname, cdata in others:
            seqmatch = SequenceMatcher(None, fdata.data, cdata.data)
            # perform progressively more expensive comparisons
            if seqmatch.real_quick_ratio() == 1.0:
                identical.add(cname)
            elif (
                seqmatch.real_quick_ratio() > Bcfg2.Options.setup.threshold and
                seqmatch.quick_ratio() > Bcfg2.Options.setup.threshold and
                seqmatch.ratio() > Bcfg2.Options.setup.threshold):
                similar.add(cname)
        if similar:
            similar.add(fname)
        if identical:
            identical.add(fname)
        return (similar, identical)
