"""This generator provides rule-based entry mappings."""

import re
import Bcfg2.Options
import Bcfg2.Server.Plugin


class Rules(Bcfg2.Server.Plugin.PrioDir):
    """This is a generator that handles service assignments."""
    __author__ = 'bcfg-dev@mcs.anl.gov'

    options = Bcfg2.Server.Plugin.PrioDir.options + [
        Bcfg2.Options.BooleanOption(
            cf=("rules", "regex"), dest="rules_regex",
            help="Allow regular expressions in Rules")]

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.PrioDir.__init__(self, core, datastore)
        self._regex_cache = dict()

    def HandlesEntry(self, entry, metadata):
        for src in self.entries.values():
            for candidate in src.XMLMatch(metadata).xpath("//%s" % entry.tag):
                if self._matches(entry, metadata, candidate):
                    return True
        return False

    HandleEntry = Bcfg2.Server.Plugin.PrioDir.BindEntry

    def _matches(self, entry, metadata, candidate):
        if Bcfg2.Server.Plugin.PrioDir._matches(self, entry, metadata,
                                                candidate):
            return True
        elif (entry.tag == "Path" and
              entry.get('name').rstrip("/") ==
              candidate.get("name").rstrip("/")):
            # special case for Path tags:
            # http://trac.mcs.anl.gov/projects/bcfg2/ticket/967
            return True
        elif self._regex_enabled:
            # attempt regular expression matching
            rule = candidate.get("name")
            if rule not in self._regex_cache:
                self._regex_cache[rule] = re.compile("%s$" % rule)
            if self._regex_cache[rule].match(entry.get('name')):
                return True
        return False

    @property
    def _regex_enabled(self):
        """ Return True if rules regexes are enabled, False otherwise """
        return Bcfg2.Options.setup.rules_regex
