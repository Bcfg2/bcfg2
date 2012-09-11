""" Handle info and :info files """

import logging
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgInfo

logger = logging.getLogger(__name__)

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
    __init__.__doc__ = CfgInfo.__init__.__doc__

    def bind_info_to_entry(self, entry, metadata):
        self._set_info(entry, self.metadata)
    bind_info_to_entry.__doc__ = CfgInfo.bind_info_to_entry.__doc__

    def handle_event(self, event):
        if event.code2str() == 'deleted':
            return
        for line in open(self.path).readlines():
            match = Bcfg2.Server.Plugin.info_regex.match(line)
            if not match:
                logger.warning("Failed to parse line in %s: %s" % (fpath, line))
                continue
            else:
                self.metadata = \
                    dict([(key, value)
                          for key, value in list(match.groupdict().items())
                          if value])
                if ('perms' in self.metadata and
                    len(self.metadata['perms']) == 3):
                    self.metadata['perms'] = "0%s" % self.metadata['perms']
    handle_event.__doc__ = CfgInfo.handle_event.__doc__
