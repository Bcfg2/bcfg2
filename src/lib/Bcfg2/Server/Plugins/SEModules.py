import os
import logging
import Bcfg2.Server.Plugin
from Bcfg2.Compat import b64encode

logger = logging.getLogger(__name__)


class SEModuleData(Bcfg2.Server.Plugin.SpecificData):
    def bind_entry(self, entry, _):
        entry.set('encoding', 'base64')
        entry.text = b64encode(self.data)


class SEModules(Bcfg2.Server.Plugin.GroupSpool):
    """ Handle SELinux 'module' entries """
    name = 'SEModules'
    __author__ = 'chris.a.st.pierre@gmail.com'
    es_child_cls = SEModuleData
    entry_type = 'SELinux'
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
        if entry.tag in self.Entries and entry.get('type') == 'module':
            return self._get_module_filename(entry) in self.Entries[entry.tag]
        return Bcfg2.Server.Plugin.GroupSpool.HandlesEntry(self, entry,
                                                           metadata)

    def HandleEntry(self, entry, metadata):
        entry.set("name", self._get_module_name(entry))
        bind = self.Entries[entry.tag][self._get_module_filename(entry)]
        return bind(entry, metadata)

    def add_entry(self, event):
        self.filename_pattern = \
            os.path.basename(os.path.dirname(self.event_path(event)))
        Bcfg2.Server.Plugin.GroupSpool.add_entry(self, event)
