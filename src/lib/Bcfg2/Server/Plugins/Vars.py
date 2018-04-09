""" Support for client ACLs based on IP address and client metadata """

import os
import sys
import Bcfg2.Server.Plugin
import lxml
import copy
from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Cache import Cache


class VarsFile(Bcfg2.Server.Plugin.StructFile):
    """ representation of Vars vars.xml """
    def __init__(self, name, core, should_monitor=False):
        """
        :param name: The filename of this vars file.
        :type name: string
        :param core: The Bcfg2.Server.Core initializing the Vars plugin
        :type core: Bcfg2.Server.Core
        """
        Bcfg2.Server.Plugin.StructFile.__init__(self, name,
                                                should_monitor=should_monitor)
        self.name = name
        self.core = core
        self.cache = Cache("Vars")

    def Index(self):
        Bcfg2.Server.Plugin.StructFile.Index(self)
        self.cache.clear()

    def get_vars(self, metadata):
        if metadata.hostname in self.cache:
            self.debug_log("Vars: Found cached vars for %s." % metadata.hostname)
            return copy.copy(self.cache[metadata.hostname])
        rv = dict()
        for el in self.Match(metadata):
            # only evaluate var tags, this is extensible in the future
            if el.tag == "var":
                self.debug_log(el)
                if 'name' not in el.attrib:
                    # if we have a correct schema, this should not happen
                    raise Bcfg2.Server.Plugin.PluginExecutionError(
                        "Vars: Invalid structure of vars.xml. Missing name attribute for variable.")
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
                raise PluginExecutionError("Failed to process schema for %s: "
                                           "%s" % (self.name, err))
        else:
            # no schema exists
            return True

        if not schema.validate(self.xdata):
            raise PluginExecutionError("Data for %s fails to validate; run "
                                       "bcfg2-lint for more details" %
                                       self.name)

class Vars(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Connector):
    """ add additional info to the metadata object based on entries in the vars.xml """

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.vars_file = VarsFile(os.path.join(self.data, 'vars.xml'),
                                  core,
                                  should_monitor=True)

    def get_additional_data(self, metadata):
        """ """
        self.debug_log("Vars: Getting vars for %s" % metadata.hostname)
        return self.vars_file.get_vars(metadata)

    def set_debug(self, debug):
        rv = Bcfg2.Server.Plugin.Plugin.set_debug(self, debug)
        self.vars_file.set_debug(debug)
        return rv
    set_debug.__doc__ = Bcfg2.Server.Plugin.Plugin.set_debug.__doc__
