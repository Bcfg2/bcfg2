#!/usr/bin/env python

from Bcfg2.Server.Generator import Generator, SingleXMLFileBacked

class ServiceList(SingleXMLFileBacked):
    def Index(self):
        SingleXMLFileBacked.Index(self)
        self.services = {}
        for e in self.entries:
            m = (e.tag, e.attrib['name'])
            for s in e.findall('Service'):
                bs = self.services.get(s.attrib['name'],[])
                bs.append((m,s))
                self.services[s.attrib['name']] = bs
        # now we need to build the index to point __provides__ at
        self.__provides__ = {'Service':{}}
        for s in self.services.keys():
            self.__provides__['Service'][s] = self.GetService
            self.services[s].sort(self.Sort)

    def GetService(self, entry, metadata):
        s = self.services[entry.attrib['name']]
        useful = filter(lambda x:self.MatchMetadata(x[0], metadata), s)
        return useful[-1][1]
        
    def MatchMetadata(self, m, metadata):
        if m[0] == 'Global':
            return True
        elif m[0] == 'Image':
            if m[1] == metadata.image:
                return True
        elif m[0] == 'Class':
            if m[1] in metadata.classes:
                return True
        elif m[0] == 'Host':
            if m[1] == metadata.hostname:
                return True
        return False

    def Sort(self, m1, m2):
        d = {('Global','Host'):-1,('Global','Image'):-1,("Global",'Class'):-1,
             ('Image', 'Global'):1, ('Image', 'Image'):0, ('Image', 'Host'):1, ('Image':'Class'):-1,
             ('Class','Global'):1, ('Class', 'Image'):1, ('Class','Class'):0, ('Class', 'Host'), -1,
             ('Host', 'Global'):1, ('Host', 'Image'):1, ('Host','Class'):1, ('Host','Host'):0}
        if d.has_key((m1[0][0], m2[0][0])):
            return d[(m1[0][0],m2[0][0])]

class servicemgr(Generator):
    '''This is a generator that handles service assignments'''
    __name__ = 'servicemgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __setup__(self):
        self.srvinfo = ServiceList("%s/packages.xml"%(self.data))
        self.__provides__ = self.srvinfo.__provides__

    def GetService(self,entry,metadata):
        # for now sshd is on
        if entry.attrib['name'] == 'sshd':
            entry.attrib['status'] = 'on'


