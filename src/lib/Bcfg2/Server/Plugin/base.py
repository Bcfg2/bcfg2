"""This module provides the base class for Bcfg2 server plugins."""

import os
import logging


class Debuggable(object):
    """ Mixin to add a debugging interface to an object and expose it
    via XML-RPC on :class:`Bcfg2.Server.Plugin.base.Plugin` objects """

    #: List of names of methods to be exposed as XML-RPC functions
    __rmi__ = ['toggle_debug', 'set_debug']

    def __init__(self, name=None):
        """
        :param name: The name of the logger object to get.  If none is
                     supplied, the full name of the class (including
                     module) will be used.
        :type name: string

        .. autoattribute:: __rmi__
        """
        if name is None:
            name = "%s.%s" % (self.__class__.__module__,
                              self.__class__.__name__)
        self.debug_flag = False
        self.logger = logging.getLogger(name)

    def set_debug(self, debug):
        """ Explicitly enable or disable debugging.  This method is exposed
        via XML-RPC.

        :returns: bool - The new value of the debug flag
        """
        self.debug_flag = debug
        self.debug_log("%s: debug_flag = %s" % (self.__class__.__name__,
                                                self.debug_flag),
                       flag=True)
        return debug

    def toggle_debug(self):
        """ Turn debugging output on or off.  This method is exposed
        via XML-RPC.

        :returns: bool - The new value of the debug flag
        """
        return self.set_debug(not self.debug_flag)

    def debug_log(self, message, flag=None):
        """ Log a message at the debug level.

        :param message: The message to log
        :type message: string
        :param flag: Override the current debug flag with this value
        :type flag: bool
        :returns: None
        """
        if (flag is None and self.debug_flag) or flag:
            self.logger.error(message)


class ClassName(object):
    """ This very simple descriptor class exists only to get the name
    of the owner class.  This is used because, for historical reasons,
    we expect every plugin to have a ``name`` attribute that is in
    almost all cases the same as the ``__class__.__name__`` attribute
    of the plugin object.  This makes that more dynamic so that each
    plugin isn't repeating its own name. """

    def __get__(self, inst, owner):
        return owner.__name__


class Plugin(Debuggable):
    """ The base class for all Bcfg2 Server plugins. """

    #: The name of the plugin.
    name = ClassName()

    #: The email address of the plugin author.
    __author__ = 'bcfg-dev@mcs.anl.gov'

    #: Plugin is experimental.  Use of this plugin will produce a log
    #: message alerting the administrator that an experimental plugin
    #: is in use.
    experimental = False

    #: Plugin is deprecated and will be removed in a future release.
    #: Use of this plugin will produce a log message alerting the
    #: administrator that an experimental plugin is in use.
    deprecated = False

    #: Plugin conflicts with the list of other plugin names
    conflicts = []

    #: Plugins of the same type are processed in order of ascending
    #: sort_order value. Plugins with the same sort_order are sorted
    #: alphabetically by their name.
    sort_order = 500

    #: List of names of methods to be exposed as XML-RPC functions
    __rmi__ = Debuggable.__rmi__

    def __init__(self, core, datastore):
        """
        :param core: The Bcfg2.Server.Core initializing the plugin
        :type core: Bcfg2.Server.Core
        :param datastore: The path to the Bcfg2 repository on the
                          filesystem
        :type datastore: string
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginInitError`

        .. autoattribute:: Bcfg2.Server.Plugin.base.Debuggable.__rmi__
        """
        self.Entries = {}
        self.core = core
        self.data = os.path.join(datastore, self.name)
        self.running = True
        Debuggable.__init__(self, name=self.name)

    @classmethod
    def init_repo(cls, repo):
        """ Perform any tasks necessary to create an initial Bcfg2
        repository.

        :param repo: The path to the Bcfg2 repository on the filesystem
        :type repo: string
        :returns: None
        """
        os.makedirs(os.path.join(repo, cls.name))

    def shutdown(self):
        """ Perform shutdown tasks for the plugin

        :returns: None """
        self.running = False

    def __str__(self):
        return "%s Plugin" % self.__class__.__name__
