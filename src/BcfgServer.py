#!/usr/bin/env python
# $Id: $

from elementtree.ElementTree import Element, tostring

from Bcfg2.Core import Core
from Bcfg2.Metadata import Metadata

from sss.restriction import DataSet, Data
from sss.server import Server

class MetadataStore(object):
    def __init__(self):
        self.images = {'topaz':'debian-3.1'}
        self.tags = {'laptop':['topaz']}
        self.bundles = {'global':['ssh'], 'tags':{'laptop':[]}, 'hosts':{}}

    def GetMetadata(self, client):
        tags = [k for (k,v) in self.tags.iteritems() if client in v]
        bundles = self.bundles['global'] + self.bundles['hosts'].get(client,[])
        bundles += reduce(lambda x,y:x+y, map(lambda b:self.bundles.get(b,[]), tags))
        return Metadata(False, self.images[client], bundles, tags, client)

class BcfgServer(Server):
    __implementation__ = 'Bcfg2'
    __component__ = 'bcfg2'
    __dispatch__ = {'get-config':'BuildConfig', 'get-probes':'GetProbes', 'probe-data':'CommitProbeData'}
    __statefields__ = ['metadata']
    __validate__ = 0
        
    def __setup__(self):
        self.metadata = MetadataStore()
        self.core=Core('/home/desai/data/b2',['bundler'],['sshbase','fstab','myri','cfg','pkgmgr','servicemgr'])
        self.__progress__()

    def __progress__(self):
        while self.core.fam.fm.pending():
            self.core.fam.HandleEvent()
        return 1

    def BuildConfig(self, xml, (peer,port)):
        # get metadata for host
        config = Element("Configuration", version='2.0')
        m = Metadata(False, 'chiba-rh73', ['ssh'], [], 'topaz')
        structures = self.core.GetStructures(m)
        #         for s in structures:
        #             self.core.BindStructure(s, m)
        #             config.append(s)
        #             for x in s.getchildren():
        #                 print x.attrib['name'], '\000' in tostring(x)
        return config

    def GetProbes(self, xml, (peer,port)):
        return Element("probes")

    def CommitProbeData(self, xml, (peer,port)):
        return Element("success")

if __name__ == '__main__':
    server = BcfgServer()
    for i in range(10):
        server.__progress__()
