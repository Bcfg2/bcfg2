"""This generator provides rule-based entry mappings."""
__revision__ = '$Revision$'

import re
import Bcfg2.Server.Plugin

class RulesConfig(Bcfg2.Server.Plugin.SimpleConfig):
    _required = False

class Rules(Bcfg2.Server.Plugin.PrioDir):
    """This is a generator that handles service assignments."""
    name = 'Rules'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.PrioDir.__init__(self, core, datastore)
        self.config = RulesConfig(self)
        self._regex_cache = dict()

    def HandlesEntry(self, entry, metadata):
        if entry.tag in self.Entries:
            return self._matches(entry, metadata,
                                 self.Entries[entry.tag].keys())
        return False

    def HandleEntry(self, entry, metadata):
        return self.BindEntry(entry, metadata)

    def BindEntry(self, entry, metadata):
        attrs = self.get_attrs(entry, metadata)
        for key, val in list(attrs.items()):
            if key not in entry.attrib:
                entry.attrib[key] = val

    def _matches(self, entry, metadata, rules):
        if Bcfg2.Server.Plugin.PrioDir._matches(self, entry, metadata, rules):
            return True
        elif (entry.tag == "Path" and
              ((entry.get('name').endswith("/") and
                entry.get('name').rstrip("/") in rules) or
               (not entry.get('name').endswith("/") and
                entry.get('name') + '/' in rules))):
            # special case for Path tags:
            # http://trac.mcs.anl.gov/projects/bcfg2/ticket/967
            return True
        elif self._regex_enabled:
            # attempt regular expression matching
            for rule in rules:
                if rule not in self._regex_cache:
                    self._regex_cache[rule] = re.compile("%s$" % rule)
                if self._regex_cache[rule].match(entry.get('name')):
                    return True
        return False
            
    def _regex_enabled(self):
        return self.config.getboolean("rules", "regex", default=False)
