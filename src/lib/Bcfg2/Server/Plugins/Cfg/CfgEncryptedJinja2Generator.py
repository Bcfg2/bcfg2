""" Handle encrypted Jinja2 templates (.crypt.jinja2 or
.jinja2.crypt files)"""

from Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator import CfgJinja2Generator
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator \
    import CfgEncryptedGenerator


class CfgEncryptedJinja2Generator(CfgJinja2Generator, CfgEncryptedGenerator):
    """ CfgEncryptedJinja2Generator lets you encrypt your Jinja2
    :ref:`server-plugins-generators-cfg` files on the server """

    #: handle .crypt.jinja2 or .jinja2.crypt files
    __extensions__ = ['jinja2.crypt', 'crypt.jinja2']

    #: Override low priority from parent class
    __priority__ = 0

    def handle_event(self, event):
        CfgEncryptedGenerator.handle_event(self, event)
    handle_event.__doc__ = CfgEncryptedGenerator.handle_event.__doc__

    def get_data(self, entry, metadata):
        return CfgJinja2Generator.get_data(self, entry, metadata)
    get_data.__doc__ = CfgJinja2Generator.get_data.__doc__
