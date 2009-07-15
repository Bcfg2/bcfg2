
import re, lxml.etree
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
        return iother in self.sparse or True in \
               [iother in range(rng[0], rng[1]+1) for rng in self.ranges]

class PatternMap(object):
    range_finder = '\\[\\[[\d\-,]+\\]\\]'
    def __init__(self, pattern, rangestr, groupname):
        self.pattern = pattern
        self.rangestr = rangestr
        self.groupname = groupname
        if pattern != None:
            self.re = re.compile(pattern)
            self.process = self.process_re
        elif rangestr != None:
            self.process = self.process_range
            self.re = re.compile('^' + re.subn(self.range_finder, '(\d+)', rangestr)[0])
            dmatcher = re.compile(re.subn(self.range_finder, '\\[\\[([\d\-,]+)\\]\\]', rangestr)[0])
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
        return self.groupname

    def process_re(self, name):
        match = self.re.match(name)
        if not match:
            return None
        ret = self.groupname
        sub = match.groups()
        for idx in range(len(sub)):
            ret = ret.replace('$%s' % (idx+1), sub[idx])
        return ret

class PatternFile(Bcfg2.Server.Plugin.SingleXMLFileBacked):
    def __init__(self, filename, fam):
        Bcfg2.Server.Plugin.SingleXMLFileBacked.__init__(self, filename, fam)
        self.patterns = []

    def Index(self):
        self.patterns = []
        try:
            parsed = lxml.etree.XML(self.data)
        except:
            Bcfg2.Server.Plugin.logger.error("Failed to read file %s" % self.name)
            return
        for entry in parsed.findall('GroupPattern'):
            try:
                pat = None
                rng = None
                if entry.find('NamePattern') is not None:
                    pat = entry.find('NamePattern').text
                if entry.find('NameRange') is not None:
                    rng = entry.find('NameRange').text
                grp = entry.find('Group').text
                self.patterns.append(PatternMap(pat, rng, grp))
            except:
                Bcfg2.Server.Plugin.logger.error(\
                    "GroupPatterns: Failed to initialize pattern %s" % \
                    (entry.get('pattern')))

    def process_patterns(self, hostname):
        ret = []
        for pattern in self.patterns:
            try:
                gn = pattern.process(hostname)
                if gn:
                    ret.append(gn)
            except:
                Bcfg2.Server.Plugin.logger.error(\
                    "GroupPatterns: Failed to process pattern %s for %s" % \
                    (pattern.pattern, hostname), exc_info=1)
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
