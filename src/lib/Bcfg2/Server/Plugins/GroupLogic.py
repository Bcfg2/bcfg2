""" GroupLogic is a connector plugin that lets you use an XML Genshi
template to dynamically set additional groups for clients. """

import os
import lxml.etree
from threading import local
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Metadata import MetadataGroup
try:
    from Bcfg2.Server.Plugins.Bundler import BundleTemplateFile
except ImportError:
    # BundleTemplateFile missing means that genshi is missing.  we
    # import genshi to get the _real_ error
    import genshi  # pylint: disable=W0611


class GroupLogicConfig(BundleTemplateFile):
    """ Representation of the GroupLogic groups.xml file """
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
    """ GroupLogic is a connector plugin that lets you use an XML
    Genshi template to dynamically set additional groups for
    clients. """
    # perform grouplogic later than other Connector plugins, so it can
    # use groups set by them
    sort_order = 1000

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.config = GroupLogicConfig(os.path.join(self.data, "groups.xml"),
                                       core.fam)
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
        for el in self.config.get_xml_value(metadata).findall("Group"):
            if el.get("category"):
                rv.append(MetadataGroup(el.get("name"),
                                        category=el.get("category")))
            else:
                rv.append(el.get("name"))
        self._local.building.discard(metadata.hostname)
        return rv
