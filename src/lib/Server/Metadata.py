#!/usr/bin/env python

from elementtree.ElementTree import XML
from time import localtime, mktime

from GeneratorUtils import SingleXMLFileBacked

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

class Metadata(object):
    '''The Metadata class is a container for all classes of metadata used by Bcfg2'''
    def __init__(self, all, image, classes, bundles, attributes, hostname):
        self.all = all
        self.image = image
        self.classes = classes
        self.bundles = bundles
        self.attributes = attributes
        self.hostname = hostname

    def Applies(self, other):
        '''Applies checks if the object associated with this metadata is relevant to
        the metadata supplied by other'''
        for c in self.classes:
            if c not in other.classes:
                return False
        for bundle in self.bundles:
            if bundle not in other.bundles:
                return False
        if (self.hostname != None) and (self.hostname != other.hostname):
            return False
        return True

class MetadataStore(SingleXMLFileBacked):
    def Index(self):
        self.clients = {}
        self.classes = {}
        self.element = XML(self.data)
        for c in self.element.findall("Class"):
            self.classes[c.attrib['name']] = map(lambda x:x.attrib['name'], c.findall(".//Bundle"))
        for client in self.element.findall('Client'):
            attributes = map(lambda x:"%s.%s"%(x.attrib['scope'],x.attrib['name']),
                             client.findall(".//Attribute"))
            classes = map(lambda x:x.attrib['name'], client.findall(".//Class"))
            bundles = reduce(lambda x,y:x+y, map(lambda z:self.classes.get(z,[]), classes),[])
            for b in bundles:
                if bundles.count(b) > 1: bundles.remove(b)
            self.clients[client.attrib['name']] = Metadata(False, client.attrib['image'], classes,
                                                           bundles, attributes, client.attrib['name'])
