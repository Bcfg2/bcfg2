#!/usr/bin/env python

'''This file stores persistent metadata for the BCFG Configuration Repository'''
__revision__ = '$Revision$'

from elementtree.ElementTree import XML, tostring, SubElement

from Bcfg2.Server.Generator import SingleXMLFileBacked
        
class ConfigurationRegion(object):
    def __init__(self, name, scope, stype):
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

    def __cmp__(self, other):
        fields = ['image', 'classes', 'bundles', 'attributes', 'hostname']
        sum1 = [x for x in len(fields) if getattr(self, fields[x])][0]
        sum2 = [x for x in len(fields) if getattr(other, fields[x])][0]
        return sum1 < sum2

class Profile(object):
    def __init__(self, xml):
        object.__init__(self)
        self.classes = [x.attrib['name'] for x in xml.findall("Class")]
        self.attributes = ["%s.%s" % (x.attrib['scope'], x.attrib['name']) for x in xml.findall("Attribute")]

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
            self.classes[c.attrib['name']] = [x.attrib['name'] for x in c.findall("Bundle")]
        for (k, v) in self.element.attrib.iteritems():
            if k[:8] == 'default_':
                self.defaults[k[8:]] = v

    def FetchMetadata(self, client, image=None, profile=None):
        if ((image != None) and (profile != None)):
            # Client asserted profile/image
            self.clients[client] = (image, profile)
            f = [x for x in self.element.findall("Client") if x.attrib['name'] == client]
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
            (image, profile) = self.clients[client]
        else:
            # default profile stuff goes here
            (image, profile) = (self.defaults['image'], self.defaults['profile'])
            SubElement(self.element, "Client", name=client, profile=profile, image=image)
            self.WriteBack()
        p = self.profiles[profile]
        # should we uniq here? V
        bundles = reduce(lambda x, y:x + y, [self.classes.get[x] for x in p.classes])
        return Metadata(False, image, p.classes, bundles, p.attributes, client)

    def WriteBack(self):
        # write changes to file back to fs
        f = open(self.name, 'w')
        f.write(tostring(self.element))
        f.close()

