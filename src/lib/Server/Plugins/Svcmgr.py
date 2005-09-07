'''This generator provides service mappings'''
__revision__ = '$Revision$'

from Bcfg2.Server.Plugin import Plugin, ScopedXMLFile

class Svcmgr(Plugin):
    '''This is a generator that handles service assignments'''
    __name__ = 'Svcmgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        self.svc = ScopedXMLFile("%s/etc/services.xml"%(datastore), self.core.fam)
        self.Entries = self.svc.__provides__




