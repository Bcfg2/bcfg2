'''This file stores persistent metadata for the BCFG Configuration Repository'''
__revision__ = '$Revision$'

from elementtree.ElementTree import XML, tostring, SubElement, Element

from Bcfg2.Server.Generator import SingleXMLFileBacked
        
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
        '''Check if metadata styled object applies to current metadata'''
        if (other.all or (other.image and (self.image == other.image)) or
            (other.classes and (self.classes == other.classes)) or
            (other.attributes and (self.attributes == other.attributes)) or
            (other.hostname and (self.hostname == other.hostname))):
            return True
        else:
            return False

class Profile(object):
    '''Profiles are configuration containers for sets of classes and attributes'''
    def __init__(self, xml):
        object.__init__(self)
        self.classes = [cls.attrib['name'] for cls in xml.findall("Class")]
        self.attributes = ["%s.%s" % (attr.attrib['scope'], attr.attrib['name']) for
                           attr in xml.findall("Attribute")]

class MetadataStore(SingleXMLFileBacked):
    '''The MetadataStore is a filebacked xml repository that contains all setup info for all clients'''

    def __init__(self, filename, fam):
        SingleXMLFileBacked.__init__(self, filename, fam)
        # initialize Index data to avoid race
        self.defaults = {}
        self.clients = {}
        self.profiles = {}
        self.classes = {}
        self.element = Element("dummy")
        
    def Index(self):
        '''Build data structures for XML data'''
        self.element = XML(self.data)
        self.defaults = {}
        self.clients = {}
        self.profiles = {}
        self.classes = {}
        for prof in self.element.findall("Profile"):
            self.profiles[prof.attrib['name']] = Profile(prof)
        for cli in self.element.findall("Client"):
            self.clients[cli.attrib['name']] = (cli.attrib['image'], cli.attrib['profile'])
        for cls in self.element.findall("Class"):
            self.classes[cls.attrib['name']] = [bundle.attrib['name'] for bundle in cls.findall("Bundle")]
        for key in [key[8:] for key in self.element.attrib if key[:8] == 'default_']:
            self.defaults[key] = self.element.get("default_%s" % key)

    def FetchMetadata(self, client, image=None, profile=None):
        '''Get metadata for client'''
        if ((image != None) and (profile != None)):
            # Client asserted profile/image
            self.clients[client] = (image, profile)
            clientdata = [cli for cli in self.element.findall("Client") if cli.get('name') == client]
            if len(clientdata) == 0:
                # non-existent client
                SubElement(self.element, "Client", name=client, image=image, profile=profile)
                self.WriteBack()
            elif len(clientdata) == 1:
                # already existing client
                clientdata[0].attrib['profile'] = profile
                clientdata[0].attrib['image'] = image
                self.WriteBack()
        elif self.clients.has_key(client):
            (image, profile) = self.clients[client]
        else:
            # default profile stuff goes here
            (image, profile) = (self.defaults['image'], self.defaults['profile'])
            SubElement(self.element, "Client", name=client, profile=profile, image=image)
            self.WriteBack()
        prof = self.profiles[profile]
        # should we uniq here? V
        bundles = reduce(lambda x, y:x + y, [self.classes.get(cls) for cls in prof.classes])
        return Metadata(False, image, prof.classes, bundles, prof.attributes, client)

    def WriteBack(self):
        '''Write metadata changes back to persistent store'''
        fout = open(self.name, 'w')
        fout.write(tostring(self.element))
        fout.close()

