#!/usr/bin/env python

from threading import Lock

from Error import NodeConfigurationError

'''This file stores persistent metadata for the BCFG Configuration Repository'''

class NodeStatistics(object):
    '''Statistics type for Nodes.
    self.last => time of last successful run
    self.status => final status of last run
    self.changeset -> the id of the last config successfully configured
    self.count => number of times client run
    self.fail => failure count'''
    
    def __init__(self):
        self.last = 0
        self.status = False
        self.changeset = 0
        self.count = 0
        self.fail = 0

    def Suceed(self,changeset):
        self.count += 1
        self.last = localtime()
        self.status = True
        self.changeset=changeset

    def Fail(self,changeset):
        self.count += 1
        self.fail += 1
        self.status = False

class Client(object):
    def __init__(self,name,image,tags):
        self.name = name
        self.image = image
        self.tags = tags
        self.stats = NodeStatistics()
        self.dirty = []

    def UpdateStats(self,status,changeset):
        if status:
            self.stats.Succeed(changeset)
        else:
            self.stats.Fail(changeset)
        
class ConfigurationRegion(object):
    def __init__(self,name,scope,stype):
        self.name = name
        self.scope = scope
        self.stype = stype

class Store(object):
    def __init__(self):
        self.clients = {}
        self.default = {}
        self.bundles = {}
        self.mappings = {}
        self.rw = Lock()
        self.r = Lock()

    def __getstate__(self):
        d=self.__dict__.copy()
        del d['rw'], d['r']
        return d

    def __setstate__(self,d):
        self.__dict__=d
        self.rw=Lock()
        self.r=Lock()

    def GetImage(self,node):
        try:
            return self.nodes[node].image
        except NodeConfigurationError, e:
            self.nodes[node]=Node(node,self.default['image'],self.default['tags'])
            return self.nodes[node].image

    def GetTags(self,node):
        try:
            return self.nodes[node].tags
        except NodeConfigurationError, e:
            self.nodes[node]=Node(node,self.default['image'],self.default['tags'])
            return self.nodes[node].image

    def AddTag(self,node,tag):
        if GetTags(node).count(tag) == 0:
            self.nodes[node].tags.append(tag)

    def DelTag(self,node,tag):
        if GetTags(node).count(tag) != 0:
            self.nodes[node].tags.remove(tag)

    def GetBundles(self,tag):
        return self.bundles.get(tag,[])

    def GetNodeBundles(self,node):
        ret = {}
        for tag in self.GetTags(node):
            for bundle in self.GetBundles(tag):
                ret[bundle]=True
        return ret.keys()
