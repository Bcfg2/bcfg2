'''This file stores persistent metadata for the BCFG Configuration Repository'''
__revision__ = '$Revision$'

from elementtree.ElementTree import XML, SubElement, Element
from syslog import syslog, LOG_ERR, LOG_INFO

from Bcfg2.Server.Plugin import SingleXMLFileBacked

class MetadataConsistencyError(Exception):
    '''This error gets raised when metadata is internally inconsistent'''
    pass

class Metadata(object):
    '''The Metadata class is a container for all classes of metadata used by Bcfg2'''
    def __init__(self, all, image, classes, bundles, attributes, hostname, toolset):
        self.all = all
        self.image = image
        self.classes = classes
        self.bundles = bundles
        self.attributes = attributes
        self.hostname = hostname
        self.toolset = toolset

    def Applies(self, other):
        '''Check if metadata styled object applies to current metadata'''
        if (other.all or (other.image and (self.image == other.image)) or
            (other.classes and (other.classes in self.classes)) or
            (other.attributes and (other.attributes in self.attributes)) or
            (other.bundles and (other.bundles in self.bundles)) or
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
        # initialize Index data to avoid race
        self.defaults = {}
        self.clients = {}
        self.profiles = {}
        self.classes = {}
        self.images = {}
        self.element = Element("dummy")
        SingleXMLFileBacked.__init__(self, filename, fam)
        
    def Index(self):
        '''Build data structures for XML data'''
        self.element = XML(self.data)
        self.defaults = {}
        self.clients = {}
        self.profiles = {}
        self.classes = {}
        self.images = {}
        for prof in self.element.findall("Profile"):
            self.profiles[prof.attrib['name']] = Profile(prof)
        for cli in self.element.findall("Client"):
            self.clients[cli.attrib['name']] = (cli.attrib['image'], cli.attrib['profile'])
        for cls in self.element.findall("Class"):
            self.classes[cls.attrib['name']] = [bundle.attrib['name'] for bundle in cls.findall("Bundle")]
        for img in self.element.findall("Image"):
            self.images[img.attrib['name']] = img.attrib['toolset']
        for key in [key[8:] for key in self.element.attrib if key[:8] == 'default_']:
            self.defaults[key] = self.element.get("default_%s" % key)

    def FetchMetadata(self, client, image=None, profile=None):
        '''Get metadata for client'''
        if ((image != None) and (profile != None)):
            # Client asserted profile/image
            self.clients[client] = (image, profile)
            syslog(LOG_INFO, "Asserted metadata for %s: %s, %s" % (client, image, profile))
            clientdata = [cli for cli in self.element.findall("Client") if cli.get('name') == client]
            if len(clientdata) == 0:
                syslog(LOG_INFO, "Added Metadata for nonexistent client %s" % client)
                SubElement(self.element, "Client", name=client, image=image, profile=profile)
                self.WriteBack()
            elif len(clientdata) == 1:
                # already existing client
                clientdata[0].attrib['profile'] = profile
                clientdata[0].attrib['image'] = image
                self.WriteBack()
        else:
            # no asserted metadata
            if self.clients.has_key(client):
                (image, profile) = self.clients[client]
            else:
                # default profile stuff goes here
                (image, profile) = (self.defaults['image'], self.defaults['profile'])
                SubElement(self.element, "Client", name=client, profile=profile, image=image)
                self.WriteBack()

        if not self.profiles.has_key(profile):
            syslog(LOG_ERR, "Metadata: profile %s not defined" % profile)
            raise MetadataConsistencyError
        prof = self.profiles[profile]
        # should we uniq here? V
        bundles = reduce(lambda x, y:x + y, [self.classes.get(cls, []) for cls in prof.classes])
        if not self.images.has_key(image):
            syslog(LOG_ERR, "Metadata: Image %s not defined" % image)
            raise MetadataConsistencyError
        toolset = self.images[image]
        return Metadata(False, image, prof.classes, bundles, prof.attributes, client, toolset)

    def pretty_print(self, element, level=0):
        '''Produce a pretty-printed text representation of element'''
        if element.text:
            fmt = "%s<%%s %%s>%%s</%%s>" % (level*" ")
            data = (element.tag, (" ".join(["%s='%s'" % x for x in element.attrib.iteritems()])),
                    element.text, element.tag)
        if element._children:
            fmt = "%s<%%s %%s>\n" % (level*" ",) + (len(element._children) * "%s") + "%s</%%s>\n" % (level*" ")
            data = (element.tag, ) + (" ".join(["%s='%s'" % x for x in element.attrib.iteritems()]),)
            data += tuple([self.pretty_print(x, level+2) for x in element._children]) + (element.tag, )
        else:
            fmt = "%s<%%s %%s/>\n" % (level * " ")
            data = (element.tag, " ".join(["%s='%s'" % x for x in element.attrib.iteritems()]))
        return fmt % data

    def WriteBack(self):
        '''Write metadata changes back to persistent store'''
        fout = open(self.name, 'w')
        fout.write(self.pretty_print(self.element))
        fout.close()

