""" GroupLogic is a connector plugin that lets you use an XML Genshi
template to dynamically set additional groups for clients. """

import os
import lxml.etree
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Bundler import BundleFile


class GroupLogicConfig(BundleFile):
    """ Representation of the GroupLogic groups.xml file """
    create = lxml.etree.Element("GroupLogic",
                                nsmap=dict(py="http://genshi.edgewall.org/"))

    def __init__(self, name, fam):
        BundleFile.__init__(self, name,
                            Bcfg2.Server.Plugin.Specificity(), None)
        self.fam = fam
        self.should_monitor = True
        self.fam.AddMonitor(self.name, self)

    def _match(self, item, metadata):
        if item.tag == 'Group' and not len(item.getchildren()):
            return [item]
        return BundleFile._match(self, item, metadata)


class GroupLogic(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """ GroupLogic is a connector plugin that lets you use an XML
    Genshi template to dynamically set additional groups for
    clients. """

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.config = GroupLogicConfig(os.path.join(self.data, "groups.xml"),
                                       core.fam)

    def get_additional_groups(self, metadata):
        return [el.get("name")
                for el in self.config.XMLMatch(metadata).findall("Group")]
