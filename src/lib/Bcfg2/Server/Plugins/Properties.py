import os
import re
import sys
import copy
import logging
import lxml.etree
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugin import PluginExecutionError
try:
    from Bcfg2.Encryption import ssl_decrypt, get_passphrases, \
        get_algorithm, bruteforce_decrypt, EVPError
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

LOGGER = logging.getLogger(__name__)

SETUP = None


class PropertyFile(Bcfg2.Server.Plugin.StructFile):
    """ Class for properties files. """

    def write(self):
        """ Write the data in this data structure back to the property
        file """
        if not SETUP.cfp.getboolean("properties", "writes_enabled",
                                    default=True):
            msg = "Properties files write-back is disabled in the " + \
                "configuration"
            LOGGER.error(msg)
            raise PluginExecutionError(msg)
        try:
            self.validate_data()
        except PluginExecutionError:
            msg = "Cannot write %s: %s" % (self.name, sys.exc_info()[1])
            LOGGER.error(msg)
            raise PluginExecutionError(msg)

        try:
            open(self.name,
                 "wb").write(
                lxml.etree.tostring(self.xdata,
                                    xml_declaration=False,
                                    pretty_print=True).decode('UTF-8'))
            return True
        except IOError:
            err = sys.exc_info()[1]
            msg = "Failed to write %s: %s" % (self.name, err)
            LOGGER.error(msg)
            raise PluginExecutionError(msg)

    def validate_data(self):
        """ ensure that the data in this object validates against the
        XML schema for this property file (if a schema exists) """
        schemafile = self.name.replace(".xml", ".xsd")
        if os.path.exists(schemafile):
            try:
                schema = lxml.etree.XMLSchema(file=schemafile)
            except:
                err = sys.exc_info()[1]
                raise PluginExecutionError("Failed to process schema for %s: "
                                           "%s" % (self.name, err))
        else:
            # no schema exists
            return True

        if not schema.validate(self.xdata):
            raise PluginExecutionError("Data for %s fails to validate; run "
                                       "bcfg2-lint for more details" %
                                       self.name)
        else:
            return True

    def Index(self):
        Bcfg2.Server.Plugin.StructFile.Index(self)
        if self.xdata.get("encryption", "false").lower() != "false":
            if not HAS_CRYPTO:
                msg = "Properties: M2Crypto is not available: %s" % self.name
                LOGGER.error(msg)
                raise PluginExecutionError(msg)
            for el in self.xdata.xpath("//*[@encrypted]"):
                try:
                    el.text = self._decrypt(el)
                except EVPError:
                    msg = "Failed to decrypt %s element in %s" % (el.tag,
                                                                  self.name)
                    LOGGER.error(msg)
                    raise PluginExecutionError(msg)

    def _decrypt(self, element):
        if not element.text.strip():
            return
        passes = get_passphrases(SETUP)
        try:
            passphrase = passes[element.get("encrypted")]
            try:
                return ssl_decrypt(element.text, passphrase,
                                   algorithm=get_algorithm(SETUP))
            except EVPError:
                # error is raised below
                pass
        except KeyError:
            return bruteforce_decrypt(element.text,
                                      passphrases=passes.values(),
                                      algorithm=get_algorithm(SETUP))
        raise EVPError("Failed to decrypt")


class PropDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = PropertyFile
    patterns = re.compile(r'.*\.xml$')
    ignore = re.compile(r'.*\.xsd$')


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

    def get_additional_data(self, metadata):
        if self.core.setup.cfp.getboolean("properties", "automatch",
                                          default=False):
            default_automatch = "true"
        else:
            default_automatch = "false"
        rv = dict()
        for fname, pfile in self.store.entries.items():
            if pfile.xdata.get("automatch",
                               default_automatch).lower() == "true":
                rv[fname] = pfile.XMLMatch(metadata)
            else:
                rv[fname] = copy.copy(pfile)
        return rv
