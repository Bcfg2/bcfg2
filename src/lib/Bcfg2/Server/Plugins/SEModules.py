import os
import logging
import binascii
import posixpath

import Bcfg2.Server.Plugin
logger = logging.getLogger(__name__)

class SEModuleData(Bcfg2.Server.Plugin.SpecificData):
    def bind_entry(self, entry, _):
        entry.set('encoding', 'base64')
        entry.text = binascii.b2a_base64(self.data)


class SEModules(Bcfg2.Server.Plugin.GroupSpool):
    """ Handle SELinux 'module' entries """
    name = 'SEModules'
    __author__ = 'chris.a.st.pierre@gmail.com'
    es_cls = Bcfg2.Server.Plugin.EntrySet
    es_child_cls = SEModuleData
    entry_type = 'SELinux'
    experimental = True

    def _get_module_name(self, entry):
        """ GroupSpool stores entries as /foo.pp, but we want people
        to be able to specify module entries as name='foo' or
        name='foo.pp', so we put this abstraction in between """
        if entry.get("name").endswith(".pp"):
            name = entry.get("name")
        else:
            name = entry.get("name") + ".pp"
        return "/" + name

    def HandlesEntry(self, entry, metadata):
        if entry.tag in self.Entries and entry.get('type') == 'module':
            return self._get_module_name(entry) in self.Entries[entry.tag]
        return Bcfg2.Server.Plugin.GroupSpool.HandlesEntry(self, entry,
                                                           metadata)

    def HandleEntry(self, entry, metadata):
        entry.set("name", self._get_module_name(entry))
        return self.Entries[entry.tag][entry.get("name")](entry, metadata)

    def add_entry(self, event):
        self.filename_pattern = os.path.basename(event.filename)
        Bcfg2.Server.Plugin.GroupSpool.add_entry(self, event)
