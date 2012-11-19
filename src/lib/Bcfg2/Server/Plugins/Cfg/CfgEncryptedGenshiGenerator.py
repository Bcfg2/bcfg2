""" Handle encrypted Genshi templates (.crypt.genshi or .genshi.crypt
files) """

from Bcfg2.Compat import StringIO
from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import SETUP
from Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator import CfgGenshiGenerator

try:
    from Bcfg2.Encryption import bruteforce_decrypt, get_algorithm
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    from genshi.template import TemplateLoader
except ImportError:
    # CfgGenshiGenerator will raise errors if genshi doesn't exist
    TemplateLoader = object  # pylint: disable=C0103


class EncryptedTemplateLoader(TemplateLoader):
    """ Subclass :class:`genshi.template.TemplateLoader` to decrypt
    the data on the fly as it's read in using
    :func:`Bcfg2.Encryption.bruteforce_decrypt` """
    def _instantiate(self, cls, fileobj, filepath, filename, encoding=None):
        plaintext = \
            StringIO(bruteforce_decrypt(fileobj.read(),
                                        algorithm=get_algorithm(SETUP)))
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

    def __init__(self, fname, spec, encoding):
        CfgGenshiGenerator.__init__(self, fname, spec, encoding)
        if not HAS_CRYPTO:
            raise PluginExecutionError("M2Crypto is not available")
