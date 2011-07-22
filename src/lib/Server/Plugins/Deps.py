"""This plugin provides automatic dependency handling."""
__revision__ = '$Revision$'

import lxml.etree

import Bcfg2.Server.Plugin


class DNode(Bcfg2.Server.Plugin.INode):
    """DNode provides supports for single predicate types for dependencies."""
    raw = {'Group': "lambda m, e:'%(name)s' in m.groups and predicate(m, e)"}
    containers = ['Group']

    def __init__(self, data, idict, parent=None):
        self.data = data
        self.contents = {}
        if parent == None:
            self.predicate = lambda x, d: True
        else:
            predicate = parent.predicate
            if data.tag in list(self.raw.keys()):
                self.predicate = eval(self.raw[data.tag] %
                                      {'name': data.get('name')},
                                      {'predicate': predicate})
            else:
                raise Exception
        mytype = self.__class__
        self.children = []
        for item in data.getchildren():
            if item.tag in self.containers:
                self.children.append(mytype(item, idict, self))
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
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = DepXMLSrc

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.PrioDir.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.StructureValidator.__init__(self)
        self.cache = {}

    def HandleEvent(self, event):
        self.cache = {}
        Bcfg2.Server.Plugin.PrioDir.HandleEvent(self, event)

    def validate_structures(self, metadata, structures):
        entries = []
        prereqs = []
        for structure in structures:
            for entry in structure.getchildren():
                if (entry.tag, entry.get('name')) not in entries \
                       and not isinstance(entry, lxml.etree._Comment):
                    entries.append((entry.tag, entry.get('name')))
        entries.sort()
        entries = tuple(entries)
        gdata = list(metadata.groups)
        gdata.sort()
        gdata = tuple(gdata)
        if (entries, gdata) in self.cache:
            prereqs = self.cache[(entries, gdata)]
        else:
            [src.Cache(metadata) for src in list(self.entries.values())]

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

                if not matching:
                    continue
                elif len(matching) == 1:
                    for prq in matching[0].cache[1][entry[0]][entry[1]]:
                        if prq not in prereqs and prq not in entries:
                            toexamine.append(prq)
                            prereqs.append(prq)
            self.cache[(entries, gdata)] = prereqs

        newstruct = lxml.etree.Element("Independent")
        for tag, name in prereqs:
            try:
                lxml.etree.SubElement(newstruct, tag, name=name)
            except:
                self.logger.error("Failed to add dep entry for %s:%s" % (tag, name))
        structures.append(newstruct)
