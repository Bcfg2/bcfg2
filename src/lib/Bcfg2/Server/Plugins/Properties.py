import os
import re
import sys
import copy
import logging
import lxml.etree
import Bcfg2.Server.Plugin
try:
    from Bcfg2.Encryption import ssl_decrypt, EVPError
    have_crypto = True
except ImportError:
    have_crypto = False

logger = logging.getLogger(__name__)

SETUP = None

def passphrases():
    section = "encryption"
    if SETUP.cfp.has_section(section):
        return dict([(o, SETUP.cfp.get(section, o))
                     for o in SETUP.cfp.options(section)])
    else:
        return dict()


class PropertyFile(Bcfg2.Server.Plugin.StructFile):
    """Class for properties files."""
    def __init__(self, name):
        Bcfg2.Server.Plugin.StructFile.__init__(self, name)
        self.passphrase = None

    def write(self):
        """ Write the data in this data structure back to the property
        file """
        if self.validate_data():
            try:
                open(self.name,
                     "wb").write(lxml.etree.tostring(self.xdata,
                                                     pretty_print=True))
                return True
            except IOError:
                err = sys.exc_info()[1]
                logger.error("Failed to write %s: %s" % (self.name, err))
                return False
        else:
            return False

    def validate_data(self):
        """ ensure that the data in this object validates against the
        XML schema for this property file (if a schema exists) """
        schemafile = self.name.replace(".xml", ".xsd")
        if os.path.exists(schemafile):
            try:
                schema = lxml.etree.XMLSchema(file=schemafile)
            except:
                logger.error("Failed to process schema for %s" % self.name)
                return False
        else:
            # no schema exists
            return True

        if not schema.validate(self.xdata):
            logger.error("Data for %s fails to validate; run bcfg2-lint for "
                         "more details" % self.name)
            return False
        else:
            return True

    def Index(self):
        Bcfg2.Server.Plugin.StructFile.Index(self)
        if self.xdata.get("encryption", "false").lower() != "false":
            logger.error("decrypting data in %s" % self.name)
            if not have_crypto:
                msg = "Properties: M2Crypto is not available: %s" % self.name
                logger.error(msg)
                raise Bcxfg2.Server.Plugin.PluginExecutionError(msg)
            for el in self.xdata.xpath("*[@encrypted='true']"):
                logger.error("decrypting data in %s in %s" % (el.tag, self.name))
                try:
                    el.text = self._decrypt(el.text)
                except EVPError:
                    msg = "Failed to decrypt %s element in %s" % (el.tag,
                                                                  self.name)
                    logger.error(msg)
                    raise Bcfg2.Server.PluginExecutionError(msg)

    def _decrypt(self, crypted):
        if self.passphrase is None:
            for passwd in passphrases().values():
                try:
                    rv = ssl_decrypt(crypted, passwd)
                    self.passphrase = passwd
                    return rv
                except EVPError:
                    pass
        else:
            try:
                return ssl_decrypt(crypted, self.passphrase)
            except EVPError:
                pass
        raise EVPError("Failed to decrypt")

class PropDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = PropertyFile
    patterns = re.compile(r'.*\.xml$')


class Properties(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """
       The properties plugin maps property
       files into client metadata instances.
    """
    name = 'Properties'

    def __init__(self, core, datastore):
        global SETUP
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        try:
            self.store = PropDirectoryBacked(self.data, core.fam)
        except OSError:
            e = sys.exc_info()[1]
            self.logger.error("Error while creating Properties store: %s %s" %
                              (e.strerror, e.filename))
            raise Bcfg2.Server.Plugin.PluginInitError

        SETUP = core.setup

    def get_additional_data(self, _):
        return copy.copy(self.store.entries)
