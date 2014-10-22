""" Custom argparse actions """

import sys
import argparse
from Bcfg2.Options.Parser import get_parser, OptionParserException
from Bcfg2.Options.Options import _debug

__all__ = ["ConfigFileAction", "ComponentAction", "PluginsAction"]


class FinalizableAction(argparse.Action):
    """ A FinalizableAction requires some additional action to be taken
    when storing the value, and as a result must be finalized if the
    default value is used."""

    def __init__(self, *args, **kwargs):
        argparse.Action.__init__(self, *args, **kwargs)
        self._final = False

    def finalize(self, parser, namespace):
        """ Finalize a default value by calling the action callable. """
        if not self._final:
            self.__call__(parser, namespace, getattr(namespace, self.dest,
                                                     self.default))

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        self._final = True


class ComponentAction(FinalizableAction):
    """ ComponentAction automatically imports classes and modules
    based on the value of the option, and automatically collects
    options from the loaded classes and modules.  It cannot be used by
    itself, but must be subclassed, with either :attr:`mapping` or
    :attr:`bases` overridden.  See
    :class:`Bcfg2.Options.PluginsAction` for an example.

    ComponentActions expect to be given a list of class names.  If
    :attr:`bases` is overridden, then it will attempt to import those
    classes from identically named modules within the given bases.
    For instance:

    .. code-block:: python

        class FooComponentAction(Bcfg2.Options.ComponentAction):
            bases = ["Bcfg2.Server.Foo"]


        class FooLoader(object):
            options = [
                Bcfg2.Options.Option(
                    "--foo",
                    type=Bcfg2.Options.Types.comma_list,
                    default=["One"],
                    action=FooComponentAction)]

    If "--foo One,Two,Three" were given on the command line, then
    ``FooComponentAction`` would attempt to import
    ``Bcfg2.Server.Foo.One.One``, ``Bcfg2.Server.Foo.Two.Two``, and
    ``Bcfg2.Server.Foo.Three.Three``.  (It would also call
    :func:`Bcfg2.Options.Parser.add_component` with each of those
    classes as arguments.)

    Note that, although ComponentActions expect lists of components
    (by default; this can be overridden by setting :attr:`islist`),
    you must still explicitly specify a ``type`` argument to the
    :class:`Bcfg2.Options.Option` constructor to split the value into
    a list.

    Note also that, unlike other actions, the default value of a
    ComponentAction option does not need to be the actual literal
    final value.  (I.e., you don't have to import
    ``Bcfg2.Server.Foo.One.One`` and set it as the default in the
    example above; the string "One" suffices.)
    """

    #: A list of parent modules where modules or classes should be
    #: imported from.
    bases = []

    #: A mapping of ``<name> => <object>`` that components will be
    #: loaded from.  This can be used to permit much more complex
    #: behavior than just a list of :attr:`bases`.
    mapping = dict()

    #: If ``module`` is True, then only the module will be loaded, not
    #: a class from the module.  For instance, in the example above,
    #: ``FooComponentAction`` would attempt instead to import
    #: ``Bcfg2.Server.Foo.One``, ``Bcfg2.Server.Foo.Two``, and
    #: ``Bcfg2.Server.Foo.Three``.
    module = False

    #: By default, ComponentActions expect a list of components to
    #: load.  If ``islist`` is False, then it will only expect a
    #: single component.
    islist = True

    #: If ``fail_silently`` is True, then failures to import modules
    #: or classes will not be logged.  This is useful when the default
    #: is to import everything, some of which are expected to fail.
    fail_silently = False

    def __init__(self, *args, **kwargs):
        if self.mapping and not self.islist:
            if 'choices' not in kwargs:
                kwargs['choices'] = self.mapping.keys()
        FinalizableAction.__init__(self, *args, **kwargs)

    def _import(self, module, name):
        """ Import the given name from the given module, handling
        errors """
        try:
            return getattr(__import__(module, fromlist=[name]), name)
        except (AttributeError, ImportError):
            msg = "Failed to load %s from %s: %s" % (name, module,
                                                     sys.exc_info()[1])
            if not self.fail_silently:
                print(msg)
            else:
                _debug(msg)
            return None

    def _load_component(self, name):
        """ Import a single class or module, adding it as a component to
        the parser.

        :param name: The name of the class or module to import, without
                     the base prepended.
        :type name: string
        :returns: the imported class or module
        """
        cls = None
        if self.mapping and name in self.mapping:
            cls = self.mapping[name]
        elif "." in name:
            cls = self._import(*name.rsplit(".", 1))
        else:
            for base in self.bases:
                if self.module:
                    mod = base
                else:
                    mod = "%s.%s" % (base, name)
                cls = self._import(mod, name)
                if cls is not None:
                    break
        if cls:
            get_parser().add_component(cls)
        elif not self.fail_silently:
            raise OptionParserException("Could not load component %s" % name)
        return cls

    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            result = None
        else:
            if self.islist:
                result = []
                for val in values:
                    cls = self._load_component(val)
                    if cls is not None:
                        result.append(cls)
            else:
                result = self._load_component(values)
        FinalizableAction.__call__(self, parser, namespace, result,
                                   option_string=option_string)


class ConfigFileAction(FinalizableAction):
    """ ConfigFileAction automatically loads and parses a
    supplementary config file (e.g., ``bcfg2-web.conf`` or
    ``bcfg2-lint.conf``). """

    def __call__(self, parser, namespace, values, option_string=None):
        if values:
            parser.add_config_file(self.dest, values, reparse=False)
        else:
            _debug("No config file passed for %s" % self)
        FinalizableAction.__call__(self, parser, namespace, values,
                                   option_string=option_string)


class PluginsAction(ComponentAction):
    """ :class:`Bcfg2.Options.ComponentAction` subclass for loading
    Bcfg2 server plugins. """
    bases = ['Bcfg2.Server.Plugins']
    fail_silently = True
