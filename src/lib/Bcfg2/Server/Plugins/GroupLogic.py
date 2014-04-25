""" GroupLogic is a connector plugin that lets you use an XML Genshi
template to dynamically set additional groups for clients. """

import os
import lxml.etree
from threading import local
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Metadata import MetadataGroup


class GroupLogicConfig(Bcfg2.Server.Plugin.StructFile):
    """ Representation of the GroupLogic groups.xml file """
    create = lxml.etree.Element("GroupLogic",
                                nsmap=dict(py="http://genshi.edgewall.org/"))

    def _match(self, item, metadata, *args):
        if item.tag == 'Group' and not len(item.getchildren()):
            return [item]
        return Bcfg2.Server.Plugin.StructFile._match(self, item, metadata,
                                                     *args)

    def _xml_match(self, item, metadata, *args):
        if item.tag == 'Group' and not len(item.getchildren()):
            return [item]
        return Bcfg2.Server.Plugin.StructFile._xml_match(self, item, metadata,
                                                         *args)


class GroupLogic(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """ GroupLogic is a connector plugin that lets you use an XML
    Genshi template to dynamically set additional groups for
    clients. """
    # perform grouplogic later than other Connector plugins, so it can
    # use groups set by them
    sort_order = 1000

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.config = GroupLogicConfig(os.path.join(self.data, "groups.xml"),
                                       should_monitor=True)
        self._local = local()

    def get_additional_groups(self, metadata):
        if not hasattr(self._local, "building"):
            # building is a thread-local set that tracks which
            # machines GroupLogic is getting additional groups for.
            # If a get_additional_groups() is called twice for a
            # machine before the first call has completed, the second
            # call returns an empty list.  This is for infinite
            # recursion protection; without this check, it'd be
            # impossible to use things like metadata.query.in_group()
            # in GroupLogic, since that requires building all
            # metadata, which requires running
            # GroupLogic.get_additional_groups() for all hosts, which
            # requires building all metadata...
            self._local.building = set()
        if metadata.hostname in self._local.building:
            return []
        self._local.building.add(metadata.hostname)
        rv = []
        for el in self.config.XMLMatch(metadata).findall("Group"):
            if el.get("category"):
                rv.append(MetadataGroup(el.get("name"),
                                        category=el.get("category")))
            else:
                rv.append(el.get("name"))
        self._local.building.discard(metadata.hostname)
        return rv
