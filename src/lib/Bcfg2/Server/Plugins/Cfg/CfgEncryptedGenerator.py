""" CfgEncryptedGenerator lets you encrypt your plaintext
:ref:`server-plugins-generators-cfg` files on the server. """

import logging
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgGenerator, SETUP
try:
    from Bcfg2.Encryption import bruteforce_decrypt, EVPError
    have_crypto = True
except ImportError:
    have_crypto = False

logger = logging.getLogger(__name__)

class CfgEncryptedGenerator(CfgGenerator):
    """ CfgEncryptedGenerator lets you encrypt your plaintext
    :ref:`server-plugins-generators-cfg` files on the server. """

    #: Handle .crypt files
    __extensions__ = ["crypt"]

    def __init__(self, fname, spec, encoding):
        CfgGenerator.__init__(self, fname, spec, encoding)
        if not have_crypto:
            msg = "Cfg: M2Crypto is not available: %s" % entry.get("name")
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
    __init__.__doc__ = CfgGenerator.__init__.__doc__

    def handle_event(self, event):
        if event.code2str() == 'deleted':
            return
        try:
            crypted = open(self.name).read()
        except UnicodeDecodeError:
            crypted = open(self.name, mode='rb').read()
        except:
            logger.error("Failed to read %s" % self.name)
            return
        # todo: let the user specify a passphrase by name
        try:
            self.data = bruteforce_decrypt(crypted, setup=SETUP)
        except EVPError:
            msg = "Failed to decrypt %s" % self.name
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
    handle_event.__doc__ = CfgGenerator.handle_event.__doc__

    def get_data(self, entry, metadata):
        if self.data is None:
            raise Bcfg2.Server.Plugin.PluginExecutionError("Failed to decrypt %s" % self.name)
        return CfgGenerator.get_data(self, entry, metadata)
    get_data.__doc__ = CfgGenerator.get_data.__doc__
