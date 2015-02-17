""" ``Bcfg2.Server.Plugin`` contains server plugin base classes,
interfaces, exceptions, and helper objects.  This module is split into
a number of submodules to make it more manageable, but it imports all
symbols from the submodules, so with the exception of some
documentation it's not necessary to use the submodules.  E.g., you can
(and should) do::

    from Bcfg2.Server.Plugin import Plugin

...rather than::

    from Bcfg2.Server.Plugin.base import Plugin
"""

import Bcfg2.Options

# pylint: disable=W0401
from Bcfg2.Server.Plugin.base import *
from Bcfg2.Server.Plugin.interfaces import *
from Bcfg2.Server.Plugin.helpers import *
from Bcfg2.Server.Plugin.exceptions import *


class _OptionContainer(object):
    """ Container for plugin options that are loaded at import time
    """
    options = [
        Bcfg2.Options.Common.default_paranoid,
        Bcfg2.Options.Option(
            cf=('mdata', 'owner'), dest="default_owner", default='root',
            help='Default Path owner'),
        Bcfg2.Options.Option(
            cf=('mdata', 'group'), dest="default_group", default='root',
            help='Default Path group'),
        Bcfg2.Options.Option(
            cf=('mdata', 'important'), dest="default_important",
            default='false', choices=['true', 'false'],
            help='Default Path priority (importance)'),
        Bcfg2.Options.Option(
            cf=('mdata', 'mode'), dest="default_mode", default='644',
            help='Default mode for Path'),
        Bcfg2.Options.Option(
            cf=('mdata', 'secontext'), dest="default_secontext",
            default='__default__', help='Default SELinux context'),
        Bcfg2.Options.Option(
            cf=('mdata', 'sensitive'), dest="default_sensitive",
            default='false',
            help='Default Path sensitivity setting')]


Bcfg2.Options.get_parser().add_component(_OptionContainer)
