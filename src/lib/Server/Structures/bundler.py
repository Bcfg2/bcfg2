#!/usr/bin/env python

'''This provides bundle clauses with translation functionality'''
__revision__ = '$Revision$'

from copy import deepcopy
from syslog import LOG_ERR, syslog

from Bcfg2.Server.Generator import SingleXMLFileBacked, XMLFileBacked, DirectoryBacked
from Bcfg2.Server.Structure import Structure

from elementtree.ElementTree import Element, XML

class ImageFile(SingleXMLFileBacked):
    '''This file contains image -> system mappings'''
    def Index(self):
        '''Build data structures out of the data'''
        a = XML(self.data)
        self.attr = a.attrib
        self.entries = a.getchildren()
        self.images = {}
        for child in self.entries:
            [name, pkg, service] = [child.get(x) for x in ['name', 'package', 'service']]
            for grandchild in child.getchildren():
                self.images[grandchild.get('name')] = (name, pkg, service)

class Bundle(XMLFileBacked):
    def Index(self):
        x = XML(self.data)
        # scan self.entries to build partial bundle fragments
        self.all = []
        self.systems = {}
        self.attributes = {}
        for entry in x.getchildren():
            if entry.tag == 'System':
                self.systems[entry.attrib['name']] = entry.getchildren()
            elif entry.tag == 'Attribute':
                self.attributes["%s.%s" % (entry.get('scope'), entry.get('name'))] = entry.getchildren()
            else:
                self.all.append(entry)
        del self.data

    def BuildBundle(self, metadata, system):
        bundlename = self.name[:-4]
        b = Element('Bundle', name=bundlename)
        for entry in self.all + self.systems.get(system, []):
            b.append(deepcopy(entry))
        for attribute in metadata.attributes:
            for entry in self.attributes.get(attribute, []):
                b.append(deepcopy(entry))
        return b
            
class BundleSet(DirectoryBacked):
    '''The Bundler handles creation of dependent clauses based on bundle definitions'''
    __child__ = Bundle

class bundler(Structure):
    __name__ =  'bundler'
    __version__ = '$Id$'
    
    '''The bundler creates dependent clauses based on the bundle/translation scheme from bcfg1'''
    def __init__(self, core, datastore):
        Structure.__init__(self, core, datastore)
        self.imageinfo = ImageFile("%s/etc/imageinfo.xml"%(datastore), self.core.fam)
        self.bundles = BundleSet(self.data, self.core.fam)

    def Construct(self, metadata):
        (system, package, service) = self.GetTransInfo(metadata)
        bundleset = []
        for bundlename in metadata.bundles:
            if not self.bundles.entries.has_key("%s.xml"%(bundlename)):
                syslog(LOG_ERR, "Client %s requested nonexistent bundle %s"%(metadata.hostname, bundlename))
                continue

            bundle = self.bundles.entries["%s.xml" % (bundlename)].BuildBundle(metadata, system)
            # now we need to populate service/package types
            for entry in bundle.getchildren():
                if entry.tag == 'Package':
                    entry.attrib['type'] = package
                elif entry.tag == 'Service':
                    entry.attrib['type'] = service
            bundleset.append(bundle)
        return bundleset

    def GetTransInfo(self, metadata):
        if self.imageinfo.images.has_key(metadata.image):
            return self.imageinfo.images[metadata.image]
        else:
            raise KeyError, metadata.image

    

