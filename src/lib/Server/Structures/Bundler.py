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
        self.images = {}
        for child in XML(self.data).getchildren():
            [name, pkg, service] = [child.get(field) for field in ['name', 'package', 'service']]
            for grandchild in child.getchildren():
                self.images[grandchild.get('name')] = (name, pkg, service)

class Bundle(XMLFileBacked):
    '''Bundles are configuration specifications (with image/translation abstraction)'''

    def Index(self):
        '''Build data structures from the source data'''
        self.all = []
        self.systems = {}
        self.attributes = {}
        for entry in XML(self.data).getchildren():
            if entry.tag == 'System':
                self.systems[entry.attrib['name']] = entry.getchildren()
            elif entry.tag == 'Attribute':
                self.attributes["%s.%s" % (entry.get('scope'), entry.get('name'))] = entry.getchildren()
            else:
                self.all.append(entry)
        del self.data

    def BuildBundle(self, metadata, system):
        '''Build a bundle for a particular client'''
        bundlename = self.name.split('/')[-1]
        bundle = Element('Bundle', name=bundlename)
        for entry in self.all + self.systems.get(system, []):
            bundle.append(deepcopy(entry))
        for attribute in metadata.attributes:
            for entry in self.attributes.get(attribute, []):
                bundle.append(deepcopy(entry))
        return bundle
            
class BundleSet(DirectoryBacked):
    '''The Bundler handles creation of dependent clauses based on bundle definitions'''
    __child__ = Bundle

class Bundler(Structure):
    '''The bundler creates dependent clauses based on the bundle/translation scheme from bcfg1'''
    __name__ =  'Bundler'
    __version__ = '$Id$'
    
    def __init__(self, core, datastore):
        Structure.__init__(self, core, datastore)
        self.imageinfo = ImageFile("%s/etc/imageinfo.xml"%(datastore), self.core.fam)
        self.bundles = BundleSet(self.data, self.core.fam)

    def Construct(self, metadata):
        '''Build all structures for client (metadata)'''
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
        '''Get Translation info for metadata.image'''
        if self.imageinfo.images.has_key(metadata.image):
            return self.imageinfo.images[metadata.image]
        else:
            raise KeyError, metadata.image

    

