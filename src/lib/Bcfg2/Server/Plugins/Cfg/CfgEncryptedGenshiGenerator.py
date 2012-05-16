import logging
from Bcfg2.Bcfg2Py3k import StringIO
from Bcfg2.Server.Plugins.Cfg import SETUP
from Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator import CfgGenshiGenerator
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator import decrypt, \
    CfgEncryptedGenerator

logger = logging.getLogger(__name__)

try:
    from genshi.template import TemplateLoader, loader
except ImportError:
    # CfgGenshiGenerator will raise errors if genshi doesn't exist
    pass

def crypted_loader(filename):
    loadfunc = loader.directory(os.path.dirname(filename))
    filepath, filename, fileobj, uptodate = loadfunc(filename)
    return (filepath, filename, StringIO(decrypt(fileobj.read())), uptodate)
    

class CfgEncryptedGenshiGenerator(CfgGenshiGenerator, CfgEncryptedGenerator):
    __extensions__ = ['genshi.crypt', 'crypt.genshi']

    def __init__(self, fname, spec, encoding):
        CfgEncryptedGenerator.__init__(self, fname, spec, encoding)
        CfgGenshiGenerator.__init__(self, fname, spec, encoding)
        self.loader = TemplateLoader([crypted_loader])

    def handle_event(self, event):
        CfgEncryptedGenerator.handle_event(self, event)
        CfgGenshiGenerator.handle_event(self, event)

    def get_data(self, entry, metadata):
        CfgGenshiGenerator.get_data(self, entry, metadata)
