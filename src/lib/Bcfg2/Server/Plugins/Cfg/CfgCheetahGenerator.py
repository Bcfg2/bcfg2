""" The CfgCheetahGenerator allows you to use the `Cheetah
<http://www.cheetahtemplate.org/>`_ templating system to generate
:ref:`server-plugins-generators-cfg` files. """

import Bcfg2.Options
from Bcfg2.Server.Plugin import PluginExecutionError, \
    DefaultTemplateDataProvider, get_template_data
from Bcfg2.Server.Plugins.Cfg import CfgGenerator

try:
    from Cheetah.Template import Template
    HAS_CHEETAH = True
except ImportError:
    HAS_CHEETAH = False


class DefaultCheetahDataProvider(DefaultTemplateDataProvider):
    """ Template data provider for Cheetah templates. Cheetah and
    Genshi currently differ over the value of the ``path`` variable,
    which is why this is necessary. """

    def get_template_data(self, entry, metadata, template):
        rv = DefaultTemplateDataProvider.get_template_data(self, entry,
                                                           metadata, template)
        rv['path'] = rv['name']
        return rv


class CfgCheetahGenerator(CfgGenerator):
    """ The CfgCheetahGenerator allows you to use the `Cheetah
    <http://www.cheetahtemplate.org/>`_ templating system to generate
    :ref:`server-plugins-generators-cfg` files. """

    #: Handle .cheetah files
    __extensions__ = ['cheetah']

    #: Low priority to avoid matching host- or group-specific
    #: .crypt.cheetah files
    __priority__ = 50

    #: :class:`Cheetah.Template.Template` compiler settings
    settings = dict(useStackFrames=False)

    def __init__(self, fname, spec):
        CfgGenerator.__init__(self, fname, spec)
        if not HAS_CHEETAH:
            raise PluginExecutionError("Cheetah is not available")
    __init__.__doc__ = CfgGenerator.__init__.__doc__

    def get_data(self, entry, metadata):
        template = Template(self.data.decode(Bcfg2.Options.setup.encoding),
                            compilerSettings=self.settings)
        for key, val in get_template_data(
            entry, metadata, self.name,
            default=DefaultCheetahDataProvider()).items():
            setattr(template, key, val)
        return template.respond()
    get_data.__doc__ = CfgGenerator.get_data.__doc__
