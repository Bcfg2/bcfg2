"""This plugin provides automatic dependency handling."""

import lxml.etree

import Bcfg2.Server.Plugin


class DNode(Bcfg2.Server.Plugin.INode):
    """DNode provides supports for single predicate types for dependencies."""
    def _load_children(self, data, idict):
        for item in data.getchildren():
            if item.tag in self.containers:
                self.children.append(self.__class__(item, idict, self))
            else:
                data = [(child.tag, child.get('name'))
                        for child in item.getchildren()]
                try:
                    self.contents[item.tag][item.get('name')] = data
                except KeyError:
                    self.contents[item.tag] = {item.get('name'): data}


class DepXMLSrc(Bcfg2.Server.Plugin.XMLSrc):
    __node__ = DNode


class Deps(Bcfg2.Server.Plugin.PrioDir,
           Bcfg2.Server.Plugin.StructureValidator):
    name = 'Deps'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = DepXMLSrc

    # Override the default sort_order (of 500) so that this plugin
    # gets handled after others running at the default. In particular,
    # we want to run after Packages, so we can see the final set of
    # packages that will be installed on the client.
    sort_order = 750

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.PrioDir.__init__(self, core, datastore)
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
                if (tag, entry.get('name')) not in entries \
                        and not isinstance(entry, lxml.etree._Comment):
                    entries.append((tag, entry.get('name')))
        entries.sort()
        entries = tuple(entries)
        gdata = list(metadata.groups)
        gdata.sort()
        gdata = tuple(gdata)

        # Check to see if we have cached the prereqs already
        if (entries, gdata) in self.cache:
            prereqs = self.cache[(entries, gdata)]
        else:
            prereqs = self.calculate_prereqs(metadata, entries)
            self.cache[(entries, gdata)] = prereqs

        newstruct = lxml.etree.Element("Independent")
        for tag, name in prereqs:
            try:
                lxml.etree.SubElement(newstruct, tag, name=name)
            except:
                self.logger.error("Failed to add dep entry for %s:%s" % (tag, name))
        structures.append(newstruct)


    def calculate_prereqs(self, metadata, entries):
        """Calculate the prerequisites defined in Deps for the passed
        set of entries.
        """
        prereqs = []
        [src.Cache(metadata) for src in self.entries.values()]

        toexamine = list(entries[:])
        while toexamine:
            entry = toexamine.pop()
            matching = [src for src in list(self.entries.values())
                        if src.cache and entry[0] in src.cache[1]
                        and entry[1] in src.cache[1][entry[0]]]
            if len(matching) > 1:
                prio = [int(src.priority) for src in matching]
                if prio.count(max(prio)) > 1:
                    self.logger.error("Found conflicting %s sources with same priority for %s, pkg %s" %
                                      (entry[0].lower(), metadata.hostname, entry[1]))
                    raise Bcfg2.Server.Plugin.PluginExecutionError
                index = prio.index(max(prio))
                matching = [matching[index]]
            elif len(matching) == 1:
                for prq in matching[0].cache[1][entry[0]][entry[1]]:
                    # XML comments seem to show up in the cache as a
                    # tuple with item 0 being callable. The logic
                    # below filters them out. Would be better to
                    # exclude them when we load the cache in the first
                    # place.
                    if prq not in prereqs and prq not in entries and not callable(prq[0]):
                        toexamine.append(prq)
                        prereqs.append(prq)
            else:
                continue

        return prereqs
