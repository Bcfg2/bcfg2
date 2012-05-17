import logging
from Bcfg2.Server.Plugins.Cfg.CfgCheetahGenerator import CfgCheetahGenerator
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator import CfgEncryptedGenerator

logger = logging.getLogger(__name__)

class CfgEncryptedCheetahGenerator(CfgCheetahGenerator, CfgEncryptedGenerator):
    __extensions__ = ['cheetah.crypt', 'crypt.cheetah']

    def handle_event(self, event):
        CfgEncryptedGenerator.handle_event(self, event)

    def get_data(self, entry, metadata):
        return CfgCheetahGenerator.get_data(self, entry, metadata)
