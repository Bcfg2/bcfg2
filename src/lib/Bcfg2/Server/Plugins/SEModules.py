"""
The SEModules plugin handles SELinux module entries.  It supports
group- and host-specific module versions, and enabling/disabling
modules.

You can use ``tools/selinux_baseline.py`` to create a baseline of all
of your installed modules.

See :ref:`server-selinux` for more information.
"""

import os
import Bcfg2.Server.Plugin
from Bcfg2.Compat import b64encode


class SEModuleData(Bcfg2.Server.Plugin.SpecificData):
    """ Representation of a single SELinux module file.  Encodes the
    data using base64 automatically """

    def bind_entry(self, entry, _):
        """ Return a fully-bound entry.  The module data is
        automatically encoded with base64.

        :param entry: The abstract entry to bind the module for
        :type entry: lxml.etree._Element
        :returns: lxml.etree._Element - the fully bound entry
        """
        entry.set('encoding', 'base64')
        entry.text = b64encode(self.data)
        return entry


class SEModules(Bcfg2.Server.Plugin.GroupSpool):
    """ Handle SELinux 'module' entries """
    __author__ = 'chris.a.st.pierre@gmail.com'

    #: SEModules is a :class:`Bcfg2.Server.Plugin.helpers.GroupSpool`
    #: that uses :class:`Bcfg2.Server.Plugins.SEModules.SEModuleData`
    #: objects as its EntrySet children.
    es_child_cls = SEModuleData

    #: SEModules manages ``SEModule`` entries
    entry_type = 'SEModule'

    #: The SEModules plugin is experimental
    experimental = True

    def _get_module_filename(self, entry):
        """ GroupSpool stores entries as /foo.pp, but we want people
        to be able to specify module entries as name='foo' or
        name='foo.pp', so we put this abstraction in between """
        if entry.get("name").endswith(".pp"):
            name = entry.get("name")
        else:
            name = entry.get("name") + ".pp"
        return "/" + name

    def _get_module_name(self, entry):
        """ On the client we do most of our logic on just the module
        name, but we want people to be able to specify module entries
        as name='foo' or name='foo.pp', so we put this abstraction in
        between"""
        if entry.get("name").endswith(".pp"):
            name = entry.get("name")[:-3]
        else:
            name = entry.get("name")
        return name.lstrip("/")

    def HandlesEntry(self, entry, metadata):
        if entry.tag in self.Entries:
            return self._get_module_filename(entry) in self.Entries[entry.tag]
        return Bcfg2.Server.Plugin.GroupSpool.HandlesEntry(self, entry,
                                                           metadata)
    HandlesEntry.__doc__ = Bcfg2.Server.Plugin.GroupSpool.HandlesEntry.__doc__

    def HandleEntry(self, entry, metadata):
        entry.set("name", self._get_module_name(entry))
        bind = self.Entries[entry.tag][self._get_module_filename(entry)]
        return bind(entry, metadata)
    HandleEntry.__doc__ = Bcfg2.Server.Plugin.GroupSpool.HandleEntry.__doc__

    def add_entry(self, event):
        self.filename_pattern = \
            os.path.basename(os.path.dirname(self.event_path(event)))
        Bcfg2.Server.Plugin.GroupSpool.add_entry(self, event)
    add_entry.__doc__ = Bcfg2.Server.Plugin.GroupSpool.add_entry.__doc__
