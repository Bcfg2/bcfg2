import logging
from Bcfg2.Compat import StringIO
from Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator import CfgGenshiGenerator
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator import decrypt, \
    CfgEncryptedGenerator

logger = logging.getLogger(__name__)

try:
    from genshi.template import TemplateLoader
except ImportError:
    # CfgGenshiGenerator will raise errors if genshi doesn't exist
    TemplateLoader = object


class EncryptedTemplateLoader(TemplateLoader):
    def _instantiate(self, cls, fileobj, filepath, filename, encoding=None):
        plaintext = StringIO(decrypt(fileobj.read()))
        return TemplateLoader._instantiate(self, cls, plaintext, filepath,
                                           filename, encoding=encoding)
        

class CfgEncryptedGenshiGenerator(CfgGenshiGenerator):
    __extensions__ = ['genshi.crypt', 'crypt.genshi']
    __loader_cls__ = EncryptedTemplateLoader

