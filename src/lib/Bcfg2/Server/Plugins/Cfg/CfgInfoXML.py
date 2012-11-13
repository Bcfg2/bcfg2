""" Handle info.xml files """

from Bcfg2.Server.Plugin import PluginExecutionError, InfoXML
from Bcfg2.Server.Plugins.Cfg import CfgInfo


class CfgInfoXML(CfgInfo):
    """ CfgInfoXML handles :file:`info.xml` files for
    :ref:`server-plugins-generators-cfg` """

    #: Handle :file:`info.xml` files
    __basenames__ = ['info.xml']

    def __init__(self, path):
        CfgInfo.__init__(self, path)
        self.infoxml = InfoXML(path)
    __init__.__doc__ = CfgInfo.__init__.__doc__

    def bind_info_to_entry(self, entry, metadata):
        mdata = dict()
        self.infoxml.pnode.Match(metadata, mdata, entry=entry)
        if 'Info' not in mdata:
            raise PluginExecutionError("Failed to set metadata for file %s" %
                                       entry.get('name'))
        self._set_info(entry, mdata['Info'][None])
    bind_info_to_entry.__doc__ = CfgInfo.bind_info_to_entry.__doc__

    def handle_event(self, event):
        self.infoxml.HandleEvent()
    handle_event.__doc__ = CfgInfo.handle_event.__doc__

    def _set_info(self, entry, info):
        CfgInfo._set_info(self, entry, info)
        if '__children__' in info:
            for child in info['__children__']:
                entry.append(child)
    _set_info.__doc__ = CfgInfo._set_info.__doc__
