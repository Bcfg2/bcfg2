#!/usr/bin/env python
# $Id: $

from copy import deepcopy
from syslog import LOG_ERR, syslog

from Bcfg2.Server.Generator import SingleXMLFileBacked, XMLFileBacked, DirectoryBacked
from Bcfg2.Server.Structure import Structure

from elementtree.ElementTree import Element, XML, tostring

class ImageFile(SingleXMLFileBacked):
    def Index(self):
        a = XML(self.data)
        self.attr = a.attrib
        self.entries = a.getchildren()
        self.images = {}
        for child in self.entries:
            (name, package, service) = map(lambda x:child.attrib.get(x), ['name', 'package', 'service'])
            for grandchild in child.getchildren():
                self.images[grandchild.attrib['name']] = (name, package, service)
            
class BundleSet(DirectoryBacked):
    '''The Bundler handles creation of dependent clauses based on bundle definitions'''
    __child__ = XMLFileBacked

class bundler(Structure):
    __name__ =  'bundler'
    __version__ = '$Version'
    
    '''The bundler creates dependent clauses based on the bundle/translation scheme from bcfg1'''
    def __init__(self, core, datastore):
        Structure.__init__(self, core, datastore)
        self.imageinfo = ImageFile("%s/common/imageinfo.xml"%(datastore), self.core.fam)
        self.bundles = BundleSet(self.data, self.core.fam)

    def Construct(self, metadata):
        (system, package, service) = self.GetTransInfo(metadata)
        bundleset = []
        for bundlename in metadata.bundles:
            if self.bundles.entries.has_key("%s.xml"%(bundlename)):
                bundle = self.bundles.entries["%s.xml"%(bundlename)]
            else:
                syslog(LOG_ERR, "Client %s requested nonexistent bundle %s"%(metadata.hostname, bundlename))
                continue
            b = Element("Bundle", name=bundlename)
            for entry in bundle.entries:
                if entry.tag != 'System':
                    d = deepcopy(entry)
                    b.append(d)
                else:
                    if entry.attrib['name'] == system:
                        d = deepcopy(entry.getchildren())
                        b._children += d
            for entry in b._children:
                if entry.tag == 'Package':
                    entry.attrib['type'] = package
                elif entry.tag == 'Service':
                    entry.attrib['type'] = service
            bundleset.append(b)
        return bundleset

    def GetTransInfo(self, metadata):
        if self.imageinfo.images.has_key(metadata.image):
            return self.imageinfo.images[metadata.image]
        else:
            raise KeyError, metadata.image

    

