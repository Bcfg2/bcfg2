#!/usr/bin/env python

from Generator import Generator, ScopedXMLFile
from elementtree.ElementTree import Element

class fs(Generator):
    '''This generator takes care of mcs filesystem setup'''
    __name__ = 'fs'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        self.fs = ScopedXMLFile("%s/../common/fs.xml"%(datastore), self.core.fam)
        self.__provides__ = self.fs.__provides__

        
