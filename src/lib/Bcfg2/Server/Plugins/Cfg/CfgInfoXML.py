import logging
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgInfo

logger = logging.getLogger(__name__)

class CfgInfoXML(CfgInfo):
    __basenames__ = ['info.xml']

    def __init__(self, path):
        CfgInfo.__init__(self, path)
        self.infoxml = Bcfg2.Server.Plugin.InfoXML(path, noprio=True)

    def bind_info_to_entry(self, entry, metadata):
        mdata = dict()
        self.infoxml.pnode.Match(metadata, mdata, entry=entry)
        if 'Info' not in mdata:
            logger.error("Failed to set metadata for file %s" %
                         entry.get('name'))
            raise PluginExecutionError
        self._set_info(entry, mdata['Info'][None])

    def handle_event(self, event):
        self.infoxml.HandleEvent()

    def _set_info(self, entry, info):
        CfgInfo._set_info(self, entry, info)
        if '__children__' in info:
            for child in info['__children__']:
                entry.append(child)
