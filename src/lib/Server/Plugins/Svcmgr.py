'''This generator provides service mappings'''
__revision__ = '$Revision$'

import Bcfg2.Server.Plugin

class SNode(Bcfg2.Server.Plugin.LNode):
    '''SNode has a list of services available at a particular group intersection'''
    __leaf__ = './Service'
    
class SvcSrc(Bcfg2.Server.Plugin.XMLSrc):
    '''SvcSrc files contain prioritized service definitions'''
    __node__ = SNode
            
class Svcmgr(Bcfg2.Server.Plugin.XMLPrioDir):
    '''This is a generator that handles service assignments'''
    __name__ = 'Svcmgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = SvcSrc
    __element__ = 'Service'
