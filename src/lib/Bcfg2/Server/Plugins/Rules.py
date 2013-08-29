"""This generator provides rule-based entry mappings."""

import re
import Bcfg2.Server.Plugin


class Rules(Bcfg2.Server.Plugin.PrioDir):
    """This is a generator that handles service assignments."""
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.PrioDir.__init__(self, core, datastore)
        self._regex_cache = dict()

    def HandlesEntry(self, entry, metadata):
        for src in self.entries.values():
            for candidate in src.XMLMatch(metadata).xpath("//%s" % entry.tag):
                if self._matches(entry, metadata, candidate):
                    return True
        return False

    def BindEntry(self, entry, metadata):
        attrs = self.get_attrs(entry, metadata)
        for key, val in list(attrs.items()):
            if key not in entry.attrib:
                entry.attrib[key] = val

    HandleEntry = BindEntry

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

    @property
    def _regex_enabled(self):
        """ Return True if rules regexes are enabled, False otherwise """
        return self.core.setup.cfp.getboolean("rules", "regex", default=False)
