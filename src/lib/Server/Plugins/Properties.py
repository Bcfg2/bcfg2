import os
import sys
import copy
import logging
import lxml.etree
import Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.Properties')

class PropertyFile(Bcfg2.Server.Plugin.StructFile):
    """Class for properties files."""
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


class PropDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = PropertyFile


class Properties(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """
       The properties plugin maps property
       files into client metadata instances.
    """
    name = 'Properties'
    version = '$Revision$'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        try:
            self.store = PropDirectoryBacked(self.data, core.fam)
        except OSError:
            e = sys.exc_info()[1]
            self.logger.error("Error while creating Properties store: %s %s" %
                              (e.strerror, e.filename))
            raise Bcfg2.Server.Plugin.PluginInitError

    def get_additional_data(self, _):
        return copy.deepcopy(self.store.entries)
