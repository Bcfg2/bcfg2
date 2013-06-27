""" Handle encrypted Genshi templates (.crypt.genshi or .genshi.crypt
files) """

from genshi.template import TemplateLoader
from Bcfg2.Compat import StringIO
from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator import CfgGenshiGenerator

try:
    from Bcfg2.Server.Encryption import bruteforce_decrypt
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class EncryptedTemplateLoader(TemplateLoader):
    """ Subclass :class:`genshi.template.TemplateLoader` to decrypt
    the data on the fly as it's read in using
    :func:`Bcfg2.Server.Encryption.bruteforce_decrypt` """
    def _instantiate(self, cls, fileobj, filepath, filename, encoding=None):
        plaintext = StringIO(bruteforce_decrypt(fileobj.read()))
        return TemplateLoader._instantiate(self, cls, plaintext, filepath,
                                           filename, encoding=encoding)


class CfgEncryptedGenshiGenerator(CfgGenshiGenerator):
    """ CfgEncryptedGenshiGenerator lets you encrypt your Genshi
    :ref:`server-plugins-generators-cfg` files on the server """

    #: handle .crypt.genshi or .genshi.crypt files
    __extensions__ = ['genshi.crypt', 'crypt.genshi']

    #: Override low priority from parent class
    __priority__ = 0

    #: Use a TemplateLoader class that decrypts the data on the fly
    #: when it's read in
    __loader_cls__ = EncryptedTemplateLoader

    def __init__(self, fname, spec):
        CfgGenshiGenerator.__init__(self, fname, spec)
        if not HAS_CRYPTO:
            raise PluginExecutionError("M2Crypto is not available")
