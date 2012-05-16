import logging
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgGenerator, SETUP
try:
    from Bcfg2.Encryption import ssl_decrypt, EVPError
    have_crypto = True
except ImportError:
    have_crypto = False

logger = logging.getLogger(__name__)

def passphrases():
    section = "cfg:encryption"
    if SETUP.cfp.has_section(section):
        return dict([(o, SETUP.cfp.get(section, o))
                     for o in SETUP.cfp.options(section)])
    else:
        return dict()

def decrypt(crypted):
    for passwd in passphrases().values():
        try:
            return ssl_decrypt(crypted, passwd)
        except EVPError:
            pass
    raise EVPError("Failed to decrypt %s" % self.name)

class CfgEncryptedGenerator(CfgGenerator):
    __extensions__ = ["crypt"]

    def __init__(self, fname, spec, encoding):
        CfgGenerator.__init__(self, fname, spec, encoding)
        if not have_crypto:
            msg = "Cfg: M2Crypto is not available: %s" % entry.get("name")
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

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
            self.data = decrypt(crypted)
        except EVPError:
            err = sys.exc_info()[1]
            logger.error(err)
            raise Bcfg2.Server.Plugin.PluginExecutionError(err)

    def get_data(self, entry, metadata):
        if self.data is None:
            raise Bcfg2.Server.Plugin.PluginExecutionError("Failed to decrypt %s" % self.name)
        return CfgGenerator.get_data(self, entry, metadata)
