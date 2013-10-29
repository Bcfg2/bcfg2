""" A plugin to provide helper classes and functions to templates """

import re
import imp
import sys
import logging
import Bcfg2.Server.Plugin

LOGGER = logging.getLogger(__name__)

MODULE_RE = re.compile(r'(?P<filename>(?P<module>[^\/]+)\.py)$')


def safe_module_name(module):
    """ Munge the name of a TemplateHelper module to avoid collisions
    with other Python modules.  E.g., if someone has a helper named
    'ldap.py', it should not be added to ``sys.modules`` as ``ldap``,
    but rather as something more obscure. """
    return '__TemplateHelper_%s' % module


class HelperModule(object):
    """ Representation of a TemplateHelper module """

    def __init__(self, name):
        self.name = name

        #: The name of the module as used by get_additional_data().
        #: the name of the file with .py stripped off.
        self._module_name = MODULE_RE.search(self.name).group('module')

        #: The attributes exported by this module
        self._attrs = []

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
            LOGGER.error("TemplateHelper: Failed to import %s: %s" %
                         (self.name, err))
            return

        if not hasattr(module, "__export__"):
            LOGGER.error("TemplateHelper: %s has no __export__ list" %
                         self.name)
            return

        newattrs = []
        for sym in module.__export__:
            if sym not in self._attrs and hasattr(self, sym):
                LOGGER.warning("TemplateHelper: %s: %s is a reserved keyword, "
                               "skipping export" % (self.name, sym))
                continue
            try:
                setattr(self, sym, getattr(module, sym))
                newattrs.append(sym)
            except AttributeError:
                LOGGER.warning("TemplateHelper: %s exports %s, but has no "
                               "such attribute" % (self.name, sym))
        # remove old exports
        for sym in set(self._attrs) - set(newattrs):
            delattr(self, sym)

        self._attrs = newattrs


class TemplateHelper(Bcfg2.Server.Plugin.Plugin,
                     Bcfg2.Server.Plugin.Connector,
                     Bcfg2.Server.Plugin.DirectoryBacked):
    """ A plugin to provide helper classes and functions to templates """
    __author__ = 'chris.a.st.pierre@gmail.com'
    ignore = re.compile(r'^(\.#.*|.*~|\..*\.(sw[px])|.*\.py[co])$')
    patterns = MODULE_RE
    __child__ = HelperModule

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data)

    def get_additional_data(self, _):
        return dict([(h._module_name, h)  # pylint: disable=W0212
                     for h in self.entries.values()])
