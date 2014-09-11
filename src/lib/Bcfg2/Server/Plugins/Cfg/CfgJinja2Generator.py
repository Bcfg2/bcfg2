""" The CfgJinja2Generator allows you to use the `Jinja2
<http://jinja.pocoo.org/>`_ templating system to generate
:ref:`server-plugins-generators-cfg` files. """

import Bcfg2.Options
from Bcfg2.Server.Plugin import PluginExecutionError, \
    DefaultTemplateDataProvider, get_template_data
from Bcfg2.Server.Plugins.Cfg import CfgGenerator

try:
    from jinja2 import Template
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


class DefaultJinja2DataProvider(DefaultTemplateDataProvider):
    """ Template data provider for Jinja2 templates. Jinja2 and
    Genshi currently differ over the value of the ``path`` variable,
    which is why this is necessary. """

    def get_template_data(self, entry, metadata, template):
        rv = DefaultTemplateDataProvider.get_template_data(self, entry,
                                                           metadata, template)
        rv['path'] = rv['name']
        return rv


class CfgJinja2Generator(CfgGenerator):
    """ The CfgJinja2Generator allows you to use the `Jinja2
    <http://jinja.pocoo.org/>`_ templating system to generate
    :ref:`server-plugins-generators-cfg` files. """

    #: Handle .jinja2 files
    __extensions__ = ['jinja2']

    #: Low priority to avoid matching host- or group-specific
    #: .crypt.jinja2 files
    __priority__ = 50

    def __init__(self, fname, spec):
        CfgGenerator.__init__(self, fname, spec)
        if not HAS_JINJA2:
            raise PluginExecutionError("Jinja2 is not available")
    __init__.__doc__ = CfgGenerator.__init__.__doc__

    def get_data(self, entry, metadata):
        template = Template(self.data.decode(Bcfg2.Options.setup.encoding))
        return template.render(
            get_template_data(entry, metadata, self.name,
                              default=DefaultJinja2DataProvider()))
    get_data.__doc__ = CfgGenerator.get_data.__doc__
