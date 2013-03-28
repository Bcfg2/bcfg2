import os
import lxml.etree
import Bcfg2.Server.Plugin
try:
    from Bcfg2.Server.Plugins.Bundler import BundleTemplateFile
except ImportError:
    # BundleTemplateFile missing means that genshi is missing.  we
    # import genshi to get the _real_ error
    import genshi  # pylint: disable=W0611


class GroupLogicConfig(BundleTemplateFile):
    create = lxml.etree.Element("GroupLogic",
                                nsmap=dict(py="http://genshi.edgewall.org/"))

    def __init__(self, name, fam):
        BundleTemplateFile.__init__(self, name,
                                    Bcfg2.Server.Plugin.Specificity(), None)
        self.fam = fam
        self.should_monitor = True
        self.fam.AddMonitor(self.name, self)

    def _match(self, item, metadata):
        if item.tag == 'Group' and not len(item.getchildren()):
            return [item]
        return BundleTemplateFile._match(self, item, metadata)


class GroupLogic(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.config = GroupLogicConfig(os.path.join(self.data, "groups.xml"),
                                       core.fam)

    def get_additional_groups(self, metadata):
        return [el.get("name")
                for el in self.config.get_xml_value(metadata).findall("Group")]
