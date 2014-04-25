""" CfgEncryptedGenerator lets you encrypt your plaintext
:ref:`server-plugins-generators-cfg` files on the server. """

from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgGenerator, SETUP
try:
    from Bcfg2.Encryption import bruteforce_decrypt, EVPError, \
        get_algorithm, CFG_SECTION
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

    def handle_event(self, event):
        CfgGenerator.handle_event(self, event)
        if self.data is None:
            return
        # todo: let the user specify a passphrase by name
        try:
            self.data = bruteforce_decrypt(
                self.data, setup=SETUP,
                algorithm=get_algorithm(SETUP))
        except EVPError:
            strict = SETUP.cfp.get(CFG_SECTION, "decrypt",
                                   default="strict")
            msg = "Cfg: Failed to decrypt %s" % self.name
            if strict:
                raise PluginExecutionError(msg)
            else:
                self.logger.debug(msg)

    def get_data(self, entry, metadata):
        if self.data is None:
            raise PluginExecutionError("Failed to decrypt %s" % self.name)
        return CfgGenerator.get_data(self, entry, metadata)
