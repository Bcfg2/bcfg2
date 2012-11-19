""" CfgEncryptedGenerator lets you encrypt your plaintext
:ref:`server-plugins-generators-cfg` files on the server. """

from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgGenerator, SETUP
try:
    from Bcfg2.Encryption import bruteforce_decrypt, EVPError, \
        get_algorithm
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class CfgEncryptedGenerator(CfgGenerator):
    """ CfgEncryptedGenerator lets you encrypt your plaintext
    :ref:`server-plugins-generators-cfg` files on the server. """

    #: Handle .crypt files
    __extensions__ = ["crypt"]

    #: Low priority to avoid matching host- or group-specific
    #: .genshi.crypt and .cheetah.crypt files
    __priority__ = 50

    def __init__(self, fname, spec, encoding):
        CfgGenerator.__init__(self, fname, spec, encoding)
        if not HAS_CRYPTO:
            raise PluginExecutionError("M2Crypto is not available")
    __init__.__doc__ = CfgGenerator.__init__.__doc__

    def handle_event(self, event):
        CfgGenerator.handle_event(self, event)
        if self.data is None:
            return
        # todo: let the user specify a passphrase by name
        try:
            self.data = bruteforce_decrypt(self.data, setup=SETUP,
                                           algorithm=get_algorithm(SETUP))
        except EVPError:
            raise PluginExecutionError("Failed to decrypt %s" % self.name)
    handle_event.__doc__ = CfgGenerator.handle_event.__doc__

    def get_data(self, entry, metadata):
        if self.data is None:
            raise PluginExecutionError("Failed to decrypt %s" % self.name)
        return CfgGenerator.get_data(self, entry, metadata)
    get_data.__doc__ = CfgGenerator.get_data.__doc__
