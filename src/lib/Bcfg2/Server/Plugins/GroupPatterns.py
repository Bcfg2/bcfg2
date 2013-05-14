""" set group membership based on client hostnames """

import os
import re
import sys
import Bcfg2.Server.Lint
import Bcfg2.Server.Plugin
from Bcfg2.Utils import PackedDigitRange


class PatternMap(object):
    """ Handler for a single pattern or range """

    def __init__(self, pattern, rangestr, groups):
        self.pattern = pattern
        self.rangestr = rangestr
        self.groups = groups
        if pattern is not None:
            self.re = re.compile(pattern)
            self.process = self.process_re
        elif rangestr is not None:
            if '\\' in rangestr:
                raise Exception("Backslashes are not allowed in NameRanges")
            range_finder = r'\[\[[\d\-,]+\]\]'
            self.process = self.process_range
            self.re = re.compile(r'^' + re.sub(range_finder, r'(\d+)',
                                               rangestr))
            dmatcher = re.compile(re.sub(range_finder,
                                         r'\[\[([\d\-,]+)\]\]',
                                         rangestr))
            self.dranges = [PackedDigitRange(x)
                            for x in dmatcher.match(rangestr).groups()]
        else:
            raise Exception("No pattern or range given")

    def process_range(self, name):
        """ match the given hostname against a range-based NameRange """
        match = self.re.match(name)
        if not match:
            return None
        digits = match.groups()
        for grp in range(len(digits)):
            if not self.dranges[grp].includes(digits[grp]):
                return None
        return self.groups

    def process_re(self, name):
        """ match the given hostname against a regex-based NamePattern """
        match = self.re.search(name)
        if not match:
            return None
        ret = list()
        sub = match.groups()
        for group in self.groups:
            newg = group
            for idx in range(len(sub)):
                newg = newg.replace('$%s' % (idx + 1), sub[idx])
            ret.append(newg)
        return ret

    def __str__(self):
        return "%s: %s %s" % (self.__class__.__name__, self.pattern,
                              self.groups)


class PatternFile(Bcfg2.Server.Plugin.XMLFileBacked):
    """ representation of GroupPatterns config.xml """
    __identifier__ = None
    create = 'GroupPatterns'

    def __init__(self, filename, core=None):
        try:
            fam = core.fam
        except AttributeError:
            fam = None
        Bcfg2.Server.Plugin.XMLFileBacked.__init__(self, filename, fam=fam,
                                                   should_monitor=True)
        self.core = core
        self.patterns = []

    def Index(self):
        Bcfg2.Server.Plugin.XMLFileBacked.Index(self)
        if (self.core and
            self.core.metadata_cache_mode in ['cautious', 'aggressive']):
            self.core.metadata_cache.expire()
        self.patterns = []
        for entry in self.xdata.xpath('//GroupPattern'):
            try:
                groups = [g.text for g in entry.findall('Group')]
                for pat_ent in entry.findall('NamePattern'):
                    pat = pat_ent.text
                    self.patterns.append(PatternMap(pat, None, groups))
                for range_ent in entry.findall('NameRange'):
                    rng = range_ent.text
                    self.patterns.append(PatternMap(None, rng, groups))
            except:  # pylint: disable=W0702
                self.logger.error("GroupPatterns: Failed to initialize "
                                  "pattern %s: %s" % (entry.text,
                                                      sys.exc_info()[1]))

    def process_patterns(self, hostname):
        """ return a list of groups that should be added to the given
        client based on patterns that match the hostname """
        ret = []
        for pattern in self.patterns:
            try:
                grps = pattern.process(hostname)
                if grps is not None:
                    ret.extend(grps)
            except:  # pylint: disable=W0702
                self.logger.error("GroupPatterns: Failed to process pattern "
                                  "%s for %s" % (pattern.pattern, hostname),
                                  exc_info=1)
        return ret


class GroupPatterns(Bcfg2.Server.Plugin.Plugin,
                    Bcfg2.Server.Plugin.Connector):
    """ set group membership based on client hostnames """

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.config = PatternFile(os.path.join(self.data, 'config.xml'),
                                  core=core)

    def get_additional_groups(self, metadata):
        return self.config.process_patterns(metadata.hostname)


class GroupPatternsLint(Bcfg2.Server.Lint.ServerPlugin):
    """ ``bcfg2-lint`` plugin to check all given :ref:`GroupPatterns
    <server-plugins-grouping-grouppatterns>` patterns for validity.
    This is simply done by trying to create a
    :class:`Bcfg2.Server.Plugins.GroupPatterns.PatternMap` object for
    each pattern, and catching exceptions and presenting them as
    ``bcfg2-lint`` errors."""

    def Run(self):
        cfg = self.core.plugins['GroupPatterns'].config
        for entry in cfg.xdata.xpath('//GroupPattern'):
            groups = [g.text for g in entry.findall('Group')]
            self.check(entry, groups, ptype='NamePattern')
            self.check(entry, groups, ptype='NameRange')

    @classmethod
    def Errors(cls):
        return {"pattern-fails-to-initialize": "error"}

    def check(self, entry, groups, ptype="NamePattern"):
        """ Check a single pattern for validity """
        if ptype == "NamePattern":
            pmap = lambda p: PatternMap(p, None, groups)
        else:
            pmap = lambda p: PatternMap(None, p, groups)

        for el in entry.findall(ptype):
            pat = el.text
            try:
                pmap(pat)
            except:  # pylint: disable=W0702
                err = sys.exc_info()[1]
                self.LintError("pattern-fails-to-initialize",
                               "Failed to initialize %s %s for %s: %s" %
                               (ptype, pat, entry.get('pattern'), err))
