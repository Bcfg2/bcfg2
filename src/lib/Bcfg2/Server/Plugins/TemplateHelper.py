""" A plugin to provide helper classes and functions to templates """

import re
import imp
import sys
import lxml.etree
from Bcfg2.Server.Plugin import Plugin, Connector, DirectoryBacked, \
    TemplateDataProvider, DefaultTemplateDataProvider
from Bcfg2.Logger import Debuggable
from Bcfg2.Utils import safe_module_name

MODULE_RE = re.compile(r'(?P<filename>(?P<module>[^\/]+)\.py)$')


class HelperModule(Debuggable):
    """ Representation of a TemplateHelper module """

    def __init__(self, name, core):
        Debuggable.__init__(self)
        self.name = name
        self.core = core

        #: The name of the module as used by get_additional_data().
        #: the name of the file with .py stripped off.
        self._module_name = MODULE_RE.search(self.name).group('module')

        #: The attributes exported by this module
        self._attrs = []

        #: The attributes added to the template namespace by this module
        self.defaults = []

        default_prov = DefaultTemplateDataProvider()
        self.reserved_defaults = list(default_prov.get_template_data(
            lxml.etree.Element("Path", name="/dummy"),
            None, None)) + ["path"]

    def HandleEvent(self, event=None):
        """ HandleEvent is called whenever the FAM registers an event.

        :param event: The event object
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        if event and event.code2str() not in ['exists', 'changed', 'created']:
            return

        # expire the metadata cache, because the module might have changed
        if self.core.metadata_cache_mode in ['cautious', 'aggressive']:
            self.core.metadata_cache.expire()

        try:
            module = imp.load_source(
                safe_module_name('TemplateHelper', self._module_name),
                self.name)
        except:  # pylint: disable=W0702
            # this needs to be a blanket except because the
            # imp.load_source() call can raise literally any error,
            # since it imports the module and just passes through any
            # exceptions raised.
            err = sys.exc_info()[1]
            self.logger.error("TemplateHelper: Failed to import %s: %s" %
                              (self.name, err))
            return

        if not hasattr(module, "__export__"):
            self.logger.error("TemplateHelper: %s has no __export__ list" %
                              self.name)
            return

        newattrs = []
        for sym in module.__export__ + getattr(module, "__default__", []):
            if sym in newattrs:
                # already added to attribute list
                continue
            if sym not in self._attrs and hasattr(self, sym):
                self.logger.warning(
                    "TemplateHelper: %s: %s is a reserved keyword, "
                    "skipping export" % (self.name, sym))
                continue
            try:
                setattr(self, sym, getattr(module, sym))
                newattrs.append(sym)
            except AttributeError:
                self.logger.warning(
                    "TemplateHelper: %s exports %s, but has no such attribute"
                    % (self.name, sym))

        # remove old exports
        for sym in set(self._attrs) - set(newattrs):
            delattr(self, sym)

        self._attrs = newattrs

        self.defaults = []
        for sym in getattr(module, "__default__", []):
            if sym in self.reserved_defaults:
                self.logger.warning(
                    "TemplateHelper: %s: %s is a reserved keyword, not adding "
                    "as default" % (self.name, sym))
            self.defaults.append(sym)


class TemplateHelper(Plugin, Connector, DirectoryBacked, TemplateDataProvider):
    """ A plugin to provide helper classes and functions to templates """
    __author__ = 'chris.a.st.pierre@gmail.com'
    ignore = re.compile(r'^(\.#.*|.*~|\..*\.(sw[px])|.*\.py[co])$')
    patterns = MODULE_RE

    def __init__(self, core):
        Plugin.__init__(self, core)
        Connector.__init__(self)
        DirectoryBacked.__init__(self, self.data)
        TemplateDataProvider.__init__(self)

        # The HelperModule needs access to the core, so we have to construct
        # it manually and add the custom argument.
        self.__child__ = lambda fname: HelperModule(fname, core)

    def get_additional_data(self, _):
        return dict([(h._module_name, h)  # pylint: disable=W0212
                     for h in self.entries.values()])

    def get_template_data(self, *_):
        rv = dict()
        source = dict()
        for helper in self.entries.values():
            for key in helper.defaults:
                if key not in rv:
                    rv[key] = getattr(helper, key)
                    source[key] = helper
                else:
                    self.logger.warning(
                        "TemplateHelper: Duplicate default variable %s "
                        "provided by both %s and %s" %
                        (key, helper.name, source[key].name))
        return rv
