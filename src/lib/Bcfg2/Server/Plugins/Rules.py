"""This generator provides rule-based entry mappings."""

import copy
import re
import string
import Bcfg2.Options
import Bcfg2.Server.Plugin


class NameTemplate(string.Template):
    """Simple subclass of string.Template with a custom delimiter."""
    delimiter = '%'


class Rules(Bcfg2.Server.Plugin.PrioDir):
    """This is a generator that handles service assignments."""
    __author__ = 'bcfg-dev@mcs.anl.gov'

    options = Bcfg2.Server.Plugin.PrioDir.options + [
        Bcfg2.Options.BooleanOption(
            cf=("rules", "regex"), dest="rules_regex",
            help="Allow regular expressions in Rules"),
        Bcfg2.Options.BooleanOption(
            cf=("rules", "replace_name"), dest="rules_replace_name",
            help="Replace %{name} in attributes with name of target entry")]

    def __init__(self, core):
        Bcfg2.Server.Plugin.PrioDir.__init__(self, core)
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

    def _apply(self, entry, data):
        if self._replace_name_enabled:
            data = copy.deepcopy(data)
            for key, val in list(data.attrib.items()):
                data.attrib[key] = NameTemplate(val).safe_substitute(
                    name=entry.get('name'))

        Bcfg2.Server.Plugin.PrioDir._apply(self, entry, data)

    @property
    def _regex_enabled(self):
        """ Return True if rules regexes are enabled, False otherwise """
        return Bcfg2.Options.setup.rules_regex

    @property
    def _replace_name_enabled(self):
        """ Return True if the replace_name feature is enabled,
        False otherwise """
        return Bcfg2.Options.setup.rules_replace_name
