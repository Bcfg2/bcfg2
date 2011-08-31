"""This generator provides rule-based entry mappings."""
__revision__ = '$Revision$'

import re
import Bcfg2.Server.Plugin

class Rules(Bcfg2.Server.Plugin.PrioDir):
    """This is a generator that handles service assignments."""
    name = 'Rules'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

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
        else:
            # attempt regular expression matching
            for rule in rules:
                if re.match("%s$" % rule, entry.get('name')):
                    return True
        return False
            
