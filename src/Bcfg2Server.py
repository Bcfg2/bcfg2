#!/usr/bin/env python
# $Id: $

from socket import gethostbyaddr, herror
from syslog import syslog, LOG_INFO, LOG_ERR
from sys import exc_info
from time import time
from traceback import extract_tb

from elementtree.ElementTree import Element, tostring

from Bcfg2.Core import Core
from Bcfg2.Metadata import Metadata, eMetadata

from sss.restriction import DataSet, Data
from sss.server import Server

class BcfgServer(Server):
    __implementation__ = 'Bcfg2'
    __component__ = 'bcfg2'
    __dispatch__ = {'get-config':'BuildConfig', 'get-probes':'GetProbes', 'probe-data':'CommitProbeData', 'add-metadata':"metadata.Add", "del-metadata":"metadata.Del", "set-metadata":"XSetMeta",'get-metadata':'metadata.Get', 'add-class':'XAddClass', "del-class":'XDelClass'}
    __statefields__ = ['metadata']
    __validate__ = 0
        
    def __setup__(self):
        self.metadata = DataSet("metadata", "metadata", Data, None, False)
        self.core=Core('/home/desai/data/b2',['bundler'],['sshbase','fstab','myri','cfg','pkgmgr','servicemgr'])
        self.__progress__()

    def __progress__(self):
        while self.core.fam.fm.pending():
            self.core.fam.HandleEvent()
        return 0

    def XSetMeta(self, xml, (peer,port)):
        return self.metadata.Get(xml, (peer,port), lambda x,y:x.element.attrib.update(y))
        
    def XAddClass(self, xml, (peer,port)):
        return self.metadata.Get(xml, (peer,port), self.AddClass)
    
    def AddClass(self, entry, attrib):
        c = entry.attrib['class'].split(':')
        if attrib['class'] not in c:
            c.append(attrib['class'])
        entry.attrib['class'] = join(c, ':')

    def XDelClass(self, xml, (peer,port)):
        return self.metadata.Get(xml, (peer,port), self.DelClass)
    
    def AddClass(self, entry, attrib):
        c = entry.attrib['class'].split(':')
        if attrib['class'] in c:
            c.remove(attrib['class'])
        entry.attrib['class'] = join(c, ':')

    def GetMetadata(self, client):
        m = [x for x in self.metadata if x.element.attrib['client'] == client]
        if len(m) != 1:
            raise 'error'
        return eMetadata(m[0].element)

    def BuildConfig(self, xml, (peer,port)):
        try:
            client = gethostbyaddr(peer)[0].split('.')[0]
        except herror:
            return Element("error", type='host resolution error')
        t = time()
        config = Element("Configuration", version='2.0')
        # get metadata for host
        try:
            m = self.GetMetadata(client)
        except KeyError:
            return Element("error", type='metadata fetch')
        structures = self.core.GetStructures(m)
        for s in structures:
            self.core.BindStructure(s, m)
            config.append(s)
            #for x in s.getchildren():
            #    print x.attrib['name'], '\000' in tostring(x)
        syslog(LOG_INFO, "Generated config for %s in %s seconds"%(client, time()-t))
        return config

    def GetProbes(self, xml, (peer,port)):
        r = Element('probes')
        try:
            client = gethostbyaddr(peer)[0].split('.')[0]
        except herror:
            return Element("error", type='host resolution error')
        try:
            m = self.GetMetadata(client)
        except:
            syslog(LOG_ERR, "Failed to fetch metadata for %s"%(client))
            return Element("error", type='metadata failure')
        for g in self.core.generators:
            for p in g.GetProbes(m):
                r.append(p)
        return r

    def CommitProbeData(self, xml, (peer,port)):
        try:
            client = gethostbyaddr(peer)[0].split('.')[0]
        except herror:
            return Element("error", type='host resolution error')
        for data in xml.findall(".//probe-data"):
            try:
                [g] = [x for x in self.core.generators if x.__name__ == data.attrib['source']]
                g.AcceptProbeData(client, data)
            except:
                self.LogFailure("CommitProbeData")
        return Element("OK")

    def LogFailure(self, failure):
        (t,v,tb)=exc_info()
        syslog(LOG_ERR, "Unexpected failure in %s"%(failure))
        for line in extract_tb(tb):
            errstr = '  File "%s", line %i, in %s\n    %s\n'%line
            syslog(LOG_ERR,errstr)
            errstr = "%s: %s\n"%(t,v)
        syslog(LOG_ERR,errstr)
        del t,v,tb

if __name__ == '__main__':
    server = BcfgServer()
    for i in range(10):
        server.__progress__()
