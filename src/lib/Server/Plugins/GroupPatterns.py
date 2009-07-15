
import re, lxml.etree
import Bcfg2.Server.Plugin

class PatternMap(object):
    def __init__(self, pattern, groupname):
        self.pattern = pattern
        self.re = re.compile(pattern)
        self.groupname = groupname

    def process(self, name):
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
                pat = entry.find('NamePattern').text
                grp = entry.find('Group').text
                self.patterns.append(PatternMap(pat, grp))
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
