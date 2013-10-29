"""This plugin provides automatic dependency handling."""

import lxml.etree
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugin import PluginExecutionError


class Deps(Bcfg2.Server.Plugin.PrioDir,
           Bcfg2.Server.Plugin.StructureValidator):
    # Override the default sort_order (of 500) so that this plugin
    # gets handled after others running at the default. In particular,
    # we want to run after Packages, so we can see the final set of
    # packages that will be installed on the client.
    sort_order = 750

    def __init__(self, core):
        Bcfg2.Server.Plugin.PrioDir.__init__(self, core)
        Bcfg2.Server.Plugin.StructureValidator.__init__(self)
        self.cache = {}

    def HandleEvent(self, event):
        self.cache = {}
        Bcfg2.Server.Plugin.PrioDir.HandleEvent(self, event)

    def validate_structures(self, metadata, structures):
        """Examine the passed structures and append any additional
        prerequisite entries as defined by the files in Deps.
        """
        entries = []
        for structure in structures:
            for entry in structure.getchildren():
                tag = entry.tag
                if tag.startswith('Bound'):
                    tag = tag[5:]
                if ((tag, entry.get('name')) not in entries
                        and not isinstance(entry, lxml.etree._Comment)):
                    entries.append((tag, entry.get('name')))
        entries.sort()
        entries = tuple(entries)
        groups = list(metadata.groups)
        groups.sort()
        groups = tuple(groups)

        # Check to see if we have cached the prereqs already
        if (entries, groups) in self.cache:
            prereqs = self.cache[(entries, groups)]
        else:
            prereqs = self.calculate_prereqs(metadata, entries)
            self.cache[(entries, groups)] = prereqs

        newstruct = lxml.etree.Element("Independent",
                                       name=self.__class__.__name__)
        for tag, name in prereqs:
            lxml.etree.SubElement(newstruct, tag, name=name)
        structures.append(newstruct)

    def calculate_prereqs(self, metadata, entries):
        """Calculate the prerequisites defined in Deps for the passed
        set of entries.
        """
        prereqs = []
        toexamine = list(entries[:])
        while toexamine:
            entry = toexamine.pop()
            # tuples of (PriorityStructFile, element) for each
            # matching element and the structfile that contains it
            matching = []
            for deps in self.entries.values():
                el = deps.find("/%s[name='%s']" % (entry.tag,
                                                   entry.get("name")))
                if el:
                    matching.append((deps, el))
            if len(matching) > 1:
                prio = [int(m[0].priority) for m in matching]
                if prio.count(max(prio)) > 1:
                    raise PluginExecutionError(
                        "Deps: Found conflicting dependencies with same "
                        "priority for %s:%s for %s: %s" %
                        (entry.tag, entry.get("name"),
                         metadata.hostname, [m[0].name for m in matching]))
                index = prio.index(max(prio))
                matching = [matching[index]]
            if not matching:
                continue
            for prq in matching[0][1].getchildren():
                if prq not in prereqs and prq not in entries:
                    toexamine.append(prq)
                    prereqs.append(prq)

        return prereqs
