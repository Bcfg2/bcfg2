""" A plugin to provide helper classes and functions to templates """

import re
import imp
import sys
from Bcfg2.Logger import Debuggable
import Bcfg2.Server.Plugin

MODULE_RE = re.compile(r'(?P<filename>(?P<module>[^\/]+)\.py)$')


def safe_module_name(module):
    """ Munge the name of a TemplateHelper module to avoid collisions
    with other Python modules.  E.g., if someone has a helper named
    'ldap.py', it should not be added to ``sys.modules`` as ``ldap``,
    but rather as something more obscure. """
    return '__TemplateHelper_%s' % module


class HelperModule(Debuggable):
    """ Representation of a TemplateHelper module """

    def __init__(self, name):
        Debuggable.__init__(self)
        self.name = name

        #: The name of the module as used by get_additional_data().
        #: the name of the file with .py stripped off.
        self._module_name = MODULE_RE.search(self.name).group('module')

        #: The attributes exported by this module
        self._attrs = []

        #: The attributes added to the template namespace by this module
        self.defaults = []

    def HandleEvent(self, event=None):
        """ HandleEvent is called whenever the FAM registers an event.

        :param event: The event object
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        if event and event.code2str() not in ['exists', 'changed', 'created']:
            return

        try:
            module = imp.load_source(safe_module_name(self._module_name),
                                     self.name)
        except:  # pylint: disable=W0702
            err = sys.exc_info()[1]
            self.logger.error("TemplateHelper: Failed to import %s: %s" %
                              (self.name, err))
            return

        if not hasattr(module, "__export__"):
            self.logger.error("TemplateHelper: %s has no __export__ list" %
                              self.name)
            return

        newattrs = []
        for sym in module.__export__:
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
            if sym not in self._attrs:
                self.logger.warning(
                    "TemplateHelper: %s: %s is flagged as a default, "
                    "but is not exported; skipping")
                continue
            self.defaults.append(sym)


class TemplateHelper(Bcfg2.Server.Plugin.Plugin,
                     Bcfg2.Server.Plugin.Connector,
                     Bcfg2.Server.Plugin.DirectoryBacked,
                     Bcfg2.Server.Plugin.TemplateDataProvider):
    """ A plugin to provide helper classes and functions to templates """
    __author__ = 'chris.a.st.pierre@gmail.com'
    ignore = re.compile(r'^(\.#.*|.*~|\..*\.(sw[px])|.*\.py[co])$')
    patterns = MODULE_RE
    __child__ = HelperModule

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data)
        Bcfg2.Server.Plugin.TemplateDataProvider.__init__(self)

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
