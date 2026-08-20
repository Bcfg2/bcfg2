"""
  Support for metadata.Vars
  these contain arbitrary strings for faster generation of templates
"""

import copy
import os
import sys

import lxml

import Bcfg2.Server.Plugin
from Bcfg2.Server.Cache import Cache
from Bcfg2.Server.Plugin import PluginExecutionError

HAS_JSON = False
try:
    import json
    HAS_JSON = True
except ImportError:
    pass


class VarsFile(Bcfg2.Server.Plugin.StructFile):
    """ representation of Vars vars.xml.
    Manages caching and handles file events. """

    def __init__(self, name, core, should_monitor=False):
        Bcfg2.Server.Plugin.StructFile.__init__(self, name,
                                                should_monitor=should_monitor)
        self.name = name
        self.core = core
        # even though we are a connector plugin, keep a local cache
        self.cache = Cache("Vars")

    __init__.__doc__ = Bcfg2.Server.Plugin.StructFile.__init__.__doc__

    def Index(self):
        Bcfg2.Server.Plugin.StructFile.Index(self)
        self.cache.clear()
        self.core.metadata_cache.expire()

    Index.__doc__ = Bcfg2.Server.Plugin.StructFile.Index.__doc__

    def get_vars(self, metadata):
        """ gets all var tags from the vars.xml """
        if metadata.hostname in self.cache:
            self.debug_log("Vars: Found cached vars for %s." %
                           metadata.hostname)
            return copy.copy(self.cache[metadata.hostname])
        rv = dict()
        for el in self.XMLMatch(metadata).xpath("//var"):
            if 'name' not in el.attrib:
                # if we have a correct schema, this should not happen
                raise Bcfg2.Server.Plugin.PluginExecutionError(
                    "Vars: Invalid structure of vars.xml. "
                    "Missing name attribute for variable.")
            if HAS_JSON and el.get('type') == "json":
                rv[el.get('name')] = json.loads(el.text)
            else:
                rv[el.get('name')] = el.text
        self.cache[metadata.hostname] = copy.copy(rv)

        return rv

    def validate_data(self):
        """ ensure that the data in this object validates against the
        XML schema for the vars file (if a schema exists) """
        schemafile = self.name.replace(".xml", ".xsd")
        if os.path.exists(schemafile):
            try:
                schema = lxml.etree.XMLSchema(file=schemafile)
            except lxml.etree.XMLSchemaParseError:
                err = sys.exc_info()[1]
                raise PluginExecutionError(
                    "Failed to process schema for %s: "
                    "%s" % (self.name, err))
        else:
            # no schema exists
            return True

        if not schema.validate(self.xdata):
            raise PluginExecutionError(
                "Data for %s fails to validate; run "
                "bcfg2-lint for more details" % self.name)


class Vars(Bcfg2.Server.Plugin.Plugin,
           Bcfg2.Server.Plugin.Connector):
    """ The vars plugins adds additional info to the metadata object
    based on entries in the vars.xml. Data can even be serialized
    with json if desired.
    """

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.vars_file = VarsFile(os.path.join(self.data, 'vars.xml'),
                                  core,
                                  should_monitor=True)

    __init__.__doc__ = Bcfg2.Server.Plugin.Plugin.__init__.__doc__

    def get_additional_data(self, metadata):
        self.debug_log("Vars: Getting vars for %s" % metadata.hostname)
        return self.vars_file.get_vars(metadata)

    get_additional_data.__doc__ = \
        Bcfg2.Server.Plugin.Connector.get_additional_data.__doc__

    def set_debug(self, debug):
        rv = Bcfg2.Server.Plugin.Plugin.set_debug(self, debug)
        self.vars_file.set_debug(debug)
        return rv

    set_debug.__doc__ = Bcfg2.Server.Plugin.Plugin.set_debug.__doc__
