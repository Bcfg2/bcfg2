#!/usr/bin/env python

from elementtree.ElementTree import XML, tostring, SubElement
from time import localtime, mktime

from Generator import SingleXMLFileBacked

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

class Profile(object):
    def __init__(self, xml):
        self.classes = map(lambda x:x.attrib['name'], xml.findall("Class"))
        self.attributes = map(lambda x:"%s.%s"%(x.attrib['scope'],x.attrib['name']), xml.findall("Attribute"))

class MetadataStore(SingleXMLFileBacked):
    def Index(self):
        self.element = XML(self.data)
        self.defaults = {}
        self.clients = {}
        self.profiles = {}
        self.classes = {}
        for p in self.element.findall("Profile"):
            self.profiles[p.attrib['name']] = Profile(p)
        for c in self.element.findall("Client"):
            self.clients[c.attrib['name']] = (c.attrib['image'], c.attrib['profile'])
        for c in self.element.findall("Class"):
            self.classes[c.attrib['name']] = map(lambda x:x.attrib['name'], c.findall("Bundle"))
        for (k,v) in self.element.attrib.iteritems():
            if k[:8] == 'default_':
                self.defaults[k[8:]] = v

    def FetchMetadata(self,client, image=None, profile=None):
        if ((image != None) and (profile != None)):
            # Client asserted profile/image
            self.clients[client] = (image,profile)
            f = filter(lambda x:x.attrib['name'] == client, self.element.findall("Client"))
            if len(f) == 0:
                # non-existent client
                SubElement(self.element, "Client", name=client, image=image, profile=profile)
                self.WriteBack()
            elif len(f) == 1:
                # already existing client
                f[0].attrib['profile'] = profile
                f[0].attrib['image'] = image
                self.WriteBack()
        elif self.clients.has_key(client):
            (image,profile) = self.clients[client]
        else:
            # default profile stuff goes here
            (image,profile) = (self.defaults['image'], self.defaults['profile'])
            SubElement(self.element, "Client", name=client, profile=profile, image=image)
            self.WriteBack()
        p = self.profiles[profile]
        # should we uniq here? V
        bundles = reduce(lambda x,y:x+y, map(self.classes.get, p.classes))
        return Metadata(False, image, p.classes, bundles, p.attributes, client)

    def WriteBack(self):
        # write changes to file back to fs
        f = open(self.name, 'w')
        f.write(tostring(self.element))
        f.close()

