#!/usr/bin/env python
# $Id: $

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
    __dispatch__ = {'get-config':'GetConfig'}
    __statefields__ = ['metadata']
        
    def __setup__(self):
        self.metadata = MetadataStore()
        self.core=Core('/home/desai/data/b2',['bundler'],['sshbase','fstab','myri','cfg','pkgmgr','servicemgr'])
        self.__progress__()

    def __progress__(self):
        while self.core.fam.fm.pending():
            self.core.fam.HandleEvent()

    def BuildConfig(self, xml, (peer,port)):
        # get metadata for host
        # m = Metadata(???)
        for s in self.core.GetStructures(m):
            # build the actual config
            pass

if __name__ == '__main__':
    server = BcfgServer()
    while server.core.fam.fm.pending():
        server.core.fam.HandleEvent()
