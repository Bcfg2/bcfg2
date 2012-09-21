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

import os
import sys
sys.path.append(os.path.dirname(__file__))

# pylint: disable=W0401
from Bcfg2.Server.Plugin.base import *
from Bcfg2.Server.Plugin.interfaces import *
from Bcfg2.Server.Plugin.helpers import *
from Bcfg2.Server.Plugin.exceptions import *
