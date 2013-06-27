""" The CfgCheetahGenerator allows you to use the `Cheetah
<http://www.cheetahtemplate.org/>`_ templating system to generate
:ref:`server-plugins-generators-cfg` files. """

import Bcfg2.Options
from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgGenerator

try:
    from Cheetah.Template import Template
    HAS_CHEETAH = True
except ImportError:
    HAS_CHEETAH = False


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
        template.metadata = metadata
        template.name = entry.get('realname', entry.get('name'))
        template.path = entry.get('realname', entry.get('name'))
        template.source_path = self.name
        template.repo = Bcfg2.Options.setup.repository
        return template.respond()
    get_data.__doc__ = CfgGenerator.get_data.__doc__
