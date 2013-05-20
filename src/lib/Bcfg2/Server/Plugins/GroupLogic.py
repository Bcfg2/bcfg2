""" GroupLogic is a connector plugin that lets you use an XML Genshi
template to dynamically set additional groups for clients. """

import os
import lxml.etree
import Bcfg2.Server.Plugin


class GroupLogicConfig(Bcfg2.Server.Plugin.StructFile):
    """ Representation of the GroupLogic groups.xml file """
    create = lxml.etree.Element("GroupLogic",
                                nsmap=dict(py="http://genshi.edgewall.org/"))

    def _match(self, item, metadata):
        if item.tag == 'Group' and not len(item.getchildren()):
            return [item]
        return Bcfg2.Server.Plugin.StructFile._match(self, item, metadata)


class GroupLogic(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """ GroupLogic is a connector plugin that lets you use an XML
    Genshi template to dynamically set additional groups for
    clients. """

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.config = GroupLogicConfig(os.path.join(self.data, "groups.xml"),
                                       should_monitor=True)

    def get_additional_groups(self, metadata):
        return [el.get("name")
                for el in self.config.XMLMatch(metadata).findall("Group")]
