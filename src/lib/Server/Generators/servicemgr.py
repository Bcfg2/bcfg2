#!/usr/bin/env python

from elementtree.ElementTree import XML
from Bcfg2.Server.Generator import Generator, ScopedXMLFile

class servicemgr(Generator):
    '''This is a generator that handles service assignments'''
    __name__ = 'servicemgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        self.svc = ScopedXMLFile("%s/etc/services.xml"%(datastore), self.core.fam)
        self.__provides__ = self.svc.__provides__




