""" CfgEncryptedGenerator lets you encrypt your plaintext
:ref:`server-plugins-generators-cfg` files on the server. """

import Bcfg2.Options
from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgGenerator
try:
    from Bcfg2.Server.Encryption import bruteforce_decrypt, EVPError
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

    def __init__(self, fname, spec):
        CfgGenerator.__init__(self, fname, spec)
        if not HAS_CRYPTO:
            raise PluginExecutionError("M2Crypto is not available")

    def handle_event(self, event):
        CfgGenerator.handle_event(self, event)
        if self.data is None:
            return
        # todo: let the user specify a passphrase by name
        try:
            self.data = bruteforce_decrypt(self.data)
        except EVPError:
            msg = "Cfg: Failed to decrypt %s" % self.name
            print "lax decrypt: %s" % Bcfg2.Options.setup.lax_decryption
            if Bcfg2.Options.setup.lax_decryption:
                self.logger.debug(msg)
            else:
                raise PluginExecutionError(msg)

    def get_data(self, entry, metadata):
        if self.data is None:
            raise PluginExecutionError("Failed to decrypt %s" % self.name)
        return CfgGenerator.get_data(self, entry, metadata)
