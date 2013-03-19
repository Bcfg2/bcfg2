""" Handle info and :info files """

import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgInfo


class CfgLegacyInfo(CfgInfo):
    """ CfgLegacyInfo handles :file:`info` and :file:`:info` files for
    :ref:`server-plugins-generators-cfg` """

    #: Handle :file:`info` and :file:`:info`
    __basenames__ = ['info', ':info']

    #: CfgLegacyInfo is deprecated.  Use
    #: :class:`Bcfg2.Server.Plugins.Cfg.CfgInfoXML.CfgInfoXML` instead.
    deprecated = True

    def __init__(self, path):
        CfgInfo.__init__(self, path)
        self.path = path

        #: The set of info metadata stored in the file
        self.metadata = None
    __init__.__doc__ = CfgInfo.__init__.__doc__

    def bind_info_to_entry(self, entry, metadata):
        self._set_info(entry, self.metadata)
    bind_info_to_entry.__doc__ = CfgInfo.bind_info_to_entry.__doc__

    def handle_event(self, event):
        if event.code2str() == 'deleted':
            return
        self.metadata = Bcfg2.Server.Plugin.parse_info(open(self.path).readlines(),
                                                       self.logger)
    handle_event.__doc__ = CfgInfo.handle_event.__doc__
