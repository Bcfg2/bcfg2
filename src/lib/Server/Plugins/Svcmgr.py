"""This generator provides service mappings."""
__revision__ = '$Revision$'

import Bcfg2.Server.Plugin


class Svcmgr(Bcfg2.Server.Plugin.PrioDir):
    """This is a generator that handles service assignments."""
    name = 'Svcmgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    deprecated = True
