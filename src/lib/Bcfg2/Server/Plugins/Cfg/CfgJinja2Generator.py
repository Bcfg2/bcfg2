""" The CfgJinja2Generator allows you to use the `Jinja2
<http://jinja.pocoo.org/>`_ templating system to generate
:ref:`server-plugins-generators-cfg` files. """

import os
import sys
import Bcfg2.Options
from Bcfg2.Server.Plugin import PluginExecutionError, \
    DefaultTemplateDataProvider, get_template_data
from Bcfg2.Server.Plugins.Cfg import CfgGenerator

try:
    from jinja2 import Environment, FileSystemLoader
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


class RelEnvironment(Environment):
    """Override join_path() to enable relative template paths."""
    def join_path(self, template, parent):
        return os.path.join(os.path.dirname(parent), template)


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

    #: ``__loader_cls__`` is the class that will be instantiated to
    #: load the template files.  It must implement one public function,
    #: ``load()``, as :class:`genshi.template.TemplateLoader`.
    __loader_cls__ = FileSystemLoader

    #: ``__environment_cls__`` is the class that will be instantiated to
    #: store the jinja2 environment.  It must implement one public function,
    #: ``get_template()``, as :class:`jinja2.Environment`.
    __environment_cls__ = RelEnvironment

    #: Ignore ``.jinja2_include`` files so they can be used with the
    #: Jinja2 ``{% include ... %}`` directive without raising warnings.
    __ignore__ = ["jinja2_include"]

    #: Low priority to avoid matching host- or group-specific
    #: .crypt.jinja2 files
    __priority__ = 50

    def __init__(self, fname, spec):
        CfgGenerator.__init__(self, fname, spec)
        if not HAS_JINJA2:
            raise PluginExecutionError("Jinja2 is not available")
        self.template = None
        encoding = Bcfg2.Options.setup.encoding
        self.loader = self.__loader_cls__('/',
                                          encoding=encoding)
        self.environment = self.__environment_cls__(loader=self.loader)
    __init__.__doc__ = CfgGenerator.__init__.__doc__

    def get_data(self, entry, metadata):
        if self.template is None:
            raise PluginExecutionError("Failed to load template %s" %
                                       self.name)
        return self.template.render(
            get_template_data(entry, metadata, self.name,
                              default=DefaultJinja2DataProvider()))
    get_data.__doc__ = CfgGenerator.get_data.__doc__

    def handle_event(self, event):
        CfgGenerator.handle_event(self, event)
        try:
            self.template = \
                self.environment.get_template(self.name)
        except:
            raise PluginExecutionError("Failed to load template: %s" %
                                       sys.exc_info()[1])
    handle_event.__doc__ = CfgGenerator.handle_event.__doc__
