'''This generator handles MCS filesystem setup'''
__revision__ = '$Revision$'

from Bcfg2.Server.Generator import Generator, ScopedXMLFile

class FS(Generator):
    '''This generator takes care of mcs filesystem setup'''
    __name__ = 'FS'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        self.fs = ScopedXMLFile("%s/../etc/fs.xml"%(datastore), self.core.fam)
        self.__provides__ = self.fs.__provides__

        
