import sys
import Bcfg2.Server.Lint
from Bcfg2.Server.Plugins.GroupPatterns import PatternMap
                        
class GroupPatterns(Bcfg2.Server.Lint.ServerPlugin):
    """ Check Genshi templates for syntax errors """

    def Run(self):
        """ run plugin """
        if 'GroupPatterns' in self.core.plugins:
            cfg = self.core.plugins['GroupPatterns'].config
            for entry in cfg.xdata.xpath('//GroupPattern'):
                groups = [g.text for g in entry.findall('Group')]
                self.check(entry, groups, ptype='NamePattern')
                self.check(entry, groups, ptype='NameRange')

    def check(self, entry, groups, ptype="NamePattern"):
        if ptype == "NamePattern":
            pmap = lambda p: PatternMap(p, None, groups)
        else:
            pmap = lambda p: PatternMap(None, p, groups)
            
        for el in entry.findall(ptype):
            pat = el.text
            try:
                pmap(pat)
            except:
                err = sys.exc_info()[1]
                self.LintError("pattern-fails-to-initialize",
                               "Failed to initialize %s %s for %s: %s" %
                               (ptype, pat, entry.get('pattern'), err))
