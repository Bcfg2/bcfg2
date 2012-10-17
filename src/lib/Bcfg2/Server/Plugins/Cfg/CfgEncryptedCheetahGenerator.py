""" Handle encrypted Cheetah templates (.crypt.cheetah or
.cheetah.crypt files)"""

from Bcfg2.Server.Plugins.Cfg.CfgCheetahGenerator import CfgCheetahGenerator
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator \
    import CfgEncryptedGenerator


class CfgEncryptedCheetahGenerator(CfgCheetahGenerator, CfgEncryptedGenerator):
    """ CfgEncryptedCheetahGenerator lets you encrypt your Cheetah
    :ref:`server-plugins-generators-cfg` files on the server """

    #: handle .crypt.cheetah or .cheetah.crypt files
    __extensions__ = ['cheetah.crypt', 'crypt.cheetah']

    #: Override low priority from parent class
    __priority__ = 0

    def handle_event(self, event):
        CfgEncryptedGenerator.handle_event(self, event)
    handle_event.__doc__ = CfgEncryptedGenerator.handle_event.__doc__

    def get_data(self, entry, metadata):
        return CfgCheetahGenerator.get_data(self, entry, metadata)
    get_data.__doc__ = CfgCheetahGenerator.get_data.__doc__
