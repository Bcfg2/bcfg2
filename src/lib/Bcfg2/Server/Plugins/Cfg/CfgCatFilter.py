import logging
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgFilter

logger = logging.getLogger(__name__)

class CfgCatFilter(CfgFilter):
    __extensions__ = ['cat']

    def modify_data(self, entry, metadata, data):
        datalines = data.strip().split('\n')
        for line in self.data.split('\n'):
            if not line:
                continue
            if line.startswith('+'):
                datalines.append(line[1:])
            elif line.startswith('-'):
                if line[1:] in datalines:
                    datalines.remove(line[1:])
        return "\n".join(datalines) + "\n"
