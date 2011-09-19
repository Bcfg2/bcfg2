import lxml.etree
import re

import Bcfg2.Server.Plugin


class PackedDigitRange(object):
    def __init__(self, digit_range):
        self.sparse = list()
        self.ranges = list()
        for item in digit_range.split(','):
            if '-' in item:
                self.ranges.append(tuple([int(x) for x in item.split('-')]))
            else:
                self.sparse.append(int(item))

    def includes(self, other):
        iother = int(other)
        if iother in self.sparse:
            return True
        for (start, end) in self.ranges:
            if iother in range(start, end + 1):
                return True
        return False


class PatternMap(object):
    range_finder = '\\[\\[[\d\-,]+\\]\\]'

    def __init__(self, pattern, rangestr, groups):
        self.pattern = pattern
        self.rangestr = rangestr
        self.groups = groups
        if pattern != None:
            self.re = re.compile(pattern)
            self.process = self.process_re
        elif rangestr != None:
            self.process = self.process_range
            self.re = re.compile('^' + re.subn(self.range_finder, '(\d+)',
                                               rangestr)[0])
            dmatcher = re.compile(re.subn(self.range_finder,
                                          '\\[\\[([\d\-,]+)\\]\\]',
                                          rangestr)[0])
            self.dranges = [PackedDigitRange(x) for x in dmatcher.match(rangestr).groups()]
        else:
            raise Exception

    def process_range(self, name):
        match = self.re.match(name)
        if not match:
            return None
        digits = match.groups()
        for i in range(len(digits)):
            if not self.dranges[i].includes(digits[i]):
                return None
        return self.groups

    def process_re(self, name):
        match = self.re.match(name)
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


class PatternFile(Bcfg2.Server.Plugin.SingleXMLFileBacked):
    __identifier__ = None

    def __init__(self, filename, fam):
        Bcfg2.Server.Plugin.SingleXMLFileBacked.__init__(self, filename, fam)
        self.patterns = []

    def Index(self):
        Bcfg2.Server.Plugin.SingleXMLFileBacked.Index(self)
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
            except:
                self.logger.error("GroupPatterns: Failed to initialize pattern "
                                  "%s" % entry.get('pattern'))

    def process_patterns(self, hostname):
        ret = []
        for pattern in self.patterns:
            try:
                gn = pattern.process(hostname)
                if gn is not None:
                    ret.extend(gn)
            except:
                self.logger.error("GroupPatterns: Failed to process pattern %s "
                                  "for %s" % (pattern.pattern, hostname),
                                  exc_info=1)
        return ret


class GroupPatterns(Bcfg2.Server.Plugin.Plugin,
                    Bcfg2.Server.Plugin.Connector):
    name = "GroupPatterns"
    experimental = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.config = PatternFile(self.data + '/config.xml',
                                  core.fam)

    def get_additional_groups(self, metadata):
        return self.config.process_patterns(metadata.hostname)
