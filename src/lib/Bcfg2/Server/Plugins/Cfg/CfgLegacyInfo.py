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
        self.metadata = dict()
        for line in open(self.path).readlines():
            match = Bcfg2.Server.Plugin.INFO_REGEX.match(line)
            if not match:
                self.logger.warning("Failed to parse line in %s: %s" %
                                    (event.filename, line))
                continue
            else:
                for key, value in list(match.groupdict().items()):
                    if value:
                        self.metadata[key] = value
        if ('mode' in self.metadata and len(self.metadata['mode']) == 3):
            self.metadata['mode'] = "0%s" % self.metadata['mode']
    handle_event.__doc__ = CfgInfo.handle_event.__doc__
