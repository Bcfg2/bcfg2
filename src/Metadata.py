#!/usr/bin/env python

from threading import Lock
from time import localtime, mktime

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

    def GetStats(self):
        return (self.status, self.count, self.last, self.fail)

    def Suceed(self,changeset):
        self.count += 1
        self.last = mktime(localtime())
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
            self.stats.Suceed(changeset)
        else:
            self.stats.Fail(changeset)

    def GetStats(self):
        return self.stats.GetStats()
        
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
            return self.clients[node].image
        except NodeConfigurationError, e:
            self.clients[node]=Node(node,self.default['image'],self.default['tags'])
            return self.clients[node].image

    def GetTags(self,node):
        try:
            return self.clients[node].tags
        except NodeConfigurationError, e:
            self.clients[node]=Node(node,self.default['image'],self.default['tags'])
            return self.clients[node].image

    def AddTag(self,node,tag):
        if GetTags(node).count(tag) == 0:
            self.clients[node].tags.append(tag)

    def DelTag(self,node,tag):
        if GetTags(node).count(tag) != 0:
            self.clients[node].tags.remove(tag)

    def GetBundles(self,tag):
        return self.bundles.get(tag,[])

    def GetNodeBundles(self,node):
        ret = {}
        for tag in self.GetTags(node):
            for bundle in self.GetBundles(tag):
                ret[bundle]=True
        return ret.keys()

class Metadata(object):
    '''The Metadata class is a container for all classes of metadata used by Bcfg2'''
    def __init__(self, all, image, bundles, tags, hostname):
        self.all = all
        self.image = image
        self.bundles = bundles
        self.tags = tags
        self.hostname = hostname

    def Applies(self, other):
        '''Applies checks if the object associated with this metadata is relevant to
        the metadata supplied by other'''
        for tag in self.tags:
            if tag not in other.tags:
                return False
        for bundle in self.bundles:
            if bundle not in other.bundles:
                return False
        if (self.hostname != None) and (self.hostname != other.hostname):
            return False
        return True

