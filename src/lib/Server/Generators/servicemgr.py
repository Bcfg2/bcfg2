#!/usr/bin/env python

from Generator import Generator
from GeneratorUtils import XMLFileBacked


class ServiceList(XMLFileBacked):
    def __init__(self, filename, fam):
        XMLFileBacked.__init__(self, filename)
        fam.AddMonitor(filename)

    def Index(self):
        a = XML(self.data)
        self.name = a.attrib['name']
        self.entries = a.getchildren()

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


