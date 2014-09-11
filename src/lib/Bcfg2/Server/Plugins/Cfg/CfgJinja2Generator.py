""" The CfgJinja2Generator allows you to use the `Jinja2
<http://jinja.pocoo.org/>`_ templating system to generate
:ref:`server-plugins-generators-cfg` files. """

from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgGenerator, SETUP

try:
    from jinja2 import Template
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


class CfgJinja2Generator(CfgGenerator):
    """ The CfgJinja2Generator allows you to use the `Jinja2
    <http://jinja.pocoo.org/>`_ templating system to generate
    :ref:`server-plugins-generators-cfg` files. """

    #: Handle .jinja2 files
    __extensions__ = ['jinja2']

    #: Low priority to avoid matching host- or group-specific
    #: .crypt.jinja2 files
    __priority__ = 50

    def __init__(self, fname, spec, encoding):
        CfgGenerator.__init__(self, fname, spec, encoding)
        if not HAS_JINJA2:
            raise PluginExecutionError("Jinja2 is not available")
    __init__.__doc__ = CfgGenerator.__init__.__doc__

    def get_data(self, entry, metadata):
        template = Template(self.data.decode(self.encoding))
        name = entry.get('realname', entry.get('name'))
        return template.render(metadata=metadata, name=name, path=name,
                               source_path=name, repo=SETUP['repo'])
    get_data.__doc__ = CfgGenerator.get_data.__doc__
