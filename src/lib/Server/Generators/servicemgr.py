#!/usr/bin/env python

from Bcfg2.Server.Generator import Generator, SingleXMLFileBacked

class ServiceList(SingleXMLFileBacked):
    pass

class servicemgr(Generator):
    '''This is a generator that handles service assignments'''
    __name__ = 'servicemgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __setup__(self):
        self.__provides__ = {'Service':{'sshd':self.GetService}}
        #self.datafile = ServiceList("%s/packages.xml"%(self.data))
        pass

    def GetService(self,entry,metadata):
        # for now sshd is on
        if entry.attrib['name'] == 'sshd':
            entry.attrib['status'] = 'on'


