""" Handle info.xml files """

from Bcfg2.Server.Plugin import InfoXML
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
        self.infoxml.BindEntry(entry, metadata)
    bind_info_to_entry.__doc__ = CfgInfo.bind_info_to_entry.__doc__

    def handle_event(self, event):
        self.infoxml.HandleEvent()
    handle_event.__doc__ = CfgInfo.handle_event.__doc__
