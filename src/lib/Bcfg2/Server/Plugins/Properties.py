""" The properties plugin maps property files into client metadata
instances. """

import os
import re
import sys
import copy
import logging
import lxml.etree
import Bcfg2.Options
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugin import PluginExecutionError

try:
    import json
    HAS_JSON = True
except ImportError:
    try:
        import simplejson as json
        HAS_JSON = True
    except ImportError:
        HAS_JSON = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

LOGGER = logging.getLogger(__name__)


class PropertyFile(object):
    """ Base Properties file handler """

    def __init__(self, name):
        """
        :param name: The filename of this properties file.

        .. automethod:: _write
        """
        self.name = name

    def write(self):
        """ Write the data in this data structure back to the property
        file. This public method performs checking to ensure that
        writing is possible and then calls :func:`_write`. """
        if not Bcfg2.Options.setup.writes_enabled:
            raise PluginExecutionError("Properties files write-back is "
                                       "disabled in the configuration")
        try:
            self.validate_data()
        except PluginExecutionError:
            msg = "Cannot write %s: %s" % (self.name, sys.exc_info()[1])
            LOGGER.error(msg)
            raise PluginExecutionError(msg)
        try:
            return self._write()
        except IOError:
            err = sys.exc_info()[1]
            msg = "Failed to write %s: %s" % (self.name, err)
            LOGGER.error(msg)
            raise PluginExecutionError(msg)

    def _write(self):
        """ Write the data in this data structure back to the property
        file. """
        raise NotImplementedError

    def validate_data(self):
        """ Verify that the data in this file is valid. """
        raise NotImplementedError

    def get_additional_data(self, metadata):  # pylint: disable=W0613
        """ Get file data for inclusion in client metadata. """
        return copy.copy(self)


class JSONPropertyFile(Bcfg2.Server.Plugin.FileBacked, PropertyFile):
    """ Handle JSON Properties files. """

    def __init__(self, name):
        Bcfg2.Server.Plugin.FileBacked.__init__(self, name)
        PropertyFile.__init__(self, name)
        self.json = None
    __init__.__doc__ = Bcfg2.Server.Plugin.FileBacked.__init__.__doc__

    def Index(self):
        try:
            self.json = json.loads(self.data)
        except ValueError:
            err = sys.exc_info()[1]
            raise PluginExecutionError("Could not load JSON data from %s: %s" %
                                       (self.name, err))
    Index.__doc__ = Bcfg2.Server.Plugin.FileBacked.Index.__doc__

    def _write(self):
        json.dump(self.json, open(self.name, 'wb'))
        return True
    _write.__doc__ = PropertyFile._write.__doc__

    def validate_data(self):
        try:
            json.dumps(self.json)
        except:
            err = sys.exc_info()[1]
            raise PluginExecutionError("Data for %s cannot be dumped to JSON: "
                                       "%s" % (self.name, err))
    validate_data.__doc__ = PropertyFile.validate_data.__doc__

    def __str__(self):
        return str(self.json)

    def __repr__(self):
        return repr(self.json)


class YAMLPropertyFile(Bcfg2.Server.Plugin.FileBacked, PropertyFile):
    """ Handle YAML Properties files. """

    def __init__(self, name):
        Bcfg2.Server.Plugin.FileBacked.__init__(self, name)
        PropertyFile.__init__(self, name)
        self.yaml = None
    __init__.__doc__ = Bcfg2.Server.Plugin.FileBacked.__init__.__doc__

    def Index(self):
        try:
            self.yaml = yaml.load(self.data)
        except yaml.YAMLError:
            err = sys.exc_info()[1]
            raise PluginExecutionError("Could not load YAML data from %s: %s" %
                                       (self.name, err))
    Index.__doc__ = Bcfg2.Server.Plugin.FileBacked.Index.__doc__

    def _write(self):
        yaml.dump(self.yaml, open(self.name, 'wb'))
        return True
    _write.__doc__ = PropertyFile._write.__doc__

    def validate_data(self):
        try:
            yaml.dump(self.yaml)
        except yaml.YAMLError:
            err = sys.exc_info()[1]
            raise PluginExecutionError("Data for %s cannot be dumped to YAML: "
                                       "%s" % (self.name, err))
    validate_data.__doc__ = PropertyFile.validate_data.__doc__

    def __str__(self):
        return str(self.yaml)

    def __repr__(self):
        return repr(self.yaml)


class XMLPropertyFile(Bcfg2.Server.Plugin.StructFile, PropertyFile):
    """ Handle XML Properties files. """

    def __init__(self, name, should_monitor=False):
        Bcfg2.Server.Plugin.StructFile.__init__(self, name,
                                                should_monitor=should_monitor)
        PropertyFile.__init__(self, name)
    __init__.__doc__ = Bcfg2.Server.Plugin.StructFile.__init__.__doc__

    def _write(self):
        open(self.name, "wb").write(
            lxml.etree.tostring(self.xdata,
                                xml_declaration=False,
                                pretty_print=True).decode('UTF-8'))
        return True
    _write.__doc__ = PropertyFile._write.__doc__

    def validate_data(self):
        """ ensure that the data in this object validates against the
        XML schema for this property file (if a schema exists) """
        schemafile = self.name.replace(".xml", ".xsd")
        if os.path.exists(schemafile):
            try:
                schema = lxml.etree.XMLSchema(file=schemafile)
            except lxml.etree.XMLSchemaParseError:
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
    validate_data.__doc__ = PropertyFile.validate_data.__doc__

    def get_additional_data(self, metadata):
        if Bcfg2.Options.setup.automatch:
            default_automatch = "true"
        else:
            default_automatch = "false"

        if self.xdata.get("automatch", default_automatch).lower() == "true":
            return self.XMLMatch(metadata)
        else:
            return copy.copy(self)

    def __str__(self):
        return str(self.xdata)

    def __repr__(self):
        return repr(self.xdata)


class Properties(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector,
                 Bcfg2.Server.Plugin.DirectoryBacked):
    """ The properties plugin maps property files into client metadata
    instances. """
    options = [
        Bcfg2.Options.BooleanOption(
            cf=("properties", "writes_enabled"), default=True,
            help="Enable or disable Properties write-back"),
        Bcfg2.Options.BooleanOption(
            cf=("properties", "automatch"),
            help="Enable Properties automatch")]

    #: Extensions that are understood by Properties.
    extensions = ["xml"]
    if HAS_JSON:
        extensions.append("json")
    if HAS_YAML:
        extensions.extend(["yaml", "yml"])

    #: Only track and include files whose names and paths match this
    #: regex.  Created on-the-fly based on which libraries are
    #: installed (and thus which data formats are supported).
    #: Candidates are ``.xml`` (always supported), ``.json``,
    #: ``.yaml``, and ``.yml``.
    patterns = re.compile(r'.*\.%s$' % '|'.join(extensions))

    #: Ignore XML schema (``.xsd``) files
    ignore = re.compile(r'.*\.xsd$')

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data)

        #: Instead of creating children of this object with a static
        #: object, we use :func:`property_dispatcher` to create a
        #: child of the appropriate subclass of :class:`PropertyFile`
        self.__child__ = self.property_dispatcher
    __init__.__doc__ = Bcfg2.Server.Plugin.Plugin.__init__.__doc__

    def property_dispatcher(self, fname):
        """ Dispatch an event on a Properties file to the
        appropriate object.

        :param fname: The name of the file that received the event
        :type fname: string
        :returns: An object of the appropriate subclass of
                  :class:`PropertyFile`
        """
        if fname.endswith(".xml"):
            return XMLPropertyFile(fname)
        elif HAS_JSON and fname.endswith(".json"):
            return JSONPropertyFile(fname)
        elif HAS_YAML and (fname.endswith(".yaml") or fname.endswith(".yml")):
            return YAMLPropertyFile(fname)
        else:
            raise Bcfg2.Server.Plugin.PluginExecutionError(
                "Properties: Unknown extension %s" % fname)

    def get_additional_data(self, metadata):
        rv = dict()
        for fname, pfile in self.entries.items():
            rv[fname] = pfile.get_additional_data(metadata)
        return rv
    get_additional_data.__doc__ = \
        Bcfg2.Server.Plugin.Connector.get_additional_data.__doc__
