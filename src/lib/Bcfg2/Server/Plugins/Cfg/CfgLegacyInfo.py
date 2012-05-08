import logging
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgInfo

logger = logging.getLogger('Bcfg2.Plugins.Cfg')

class CfgLegacyInfo(CfgInfo):
    names = ['info', ':info']

    def bind_info_to_entry(self, entry, metadata):
        self._set_info(entry, self.metadata)

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
