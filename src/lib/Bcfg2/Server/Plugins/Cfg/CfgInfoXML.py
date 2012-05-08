import logging
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgInfo

logger = logging.getLogger('Bcfg2.Plugins.Cfg')

class CfgInfoXML(CfgInfo):
    names = ['info.xml']

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
