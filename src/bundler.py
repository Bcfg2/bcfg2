#!/usr/bin/env python
# $Id: $

from GeneratorUtils import XMLFileBacked, DirectoryBacked
from Structure import Structure

from elementtree.ElementTree import Element

class Bundle(XMLFileBacked):
    def __iter__(self):
        return iter(self.entries)

class Translation(XMLFileBacked):
    __identifier__ = 'system'
    
    def Index(self):
        XMLFileBacked.Index(self)
        self.images = []
        self.trans = {'VPackage':{}, 'VConfig':{}, 'VService':{}, 'VFS':{}}
        for entry in self.entries:
            if entry.tag == 'Image':
                self.images.append(entry.attrib['name'] )
            else:
                self.trans[entry.tag][entry.attrib['name']] = entry.getchildren()

class TranslationSet(DirectoryBacked):
    '''TranslationSet is the container for all active translations in the system. It
    is coherent cache of a directory.'''
    __child__ = Translation

    def __iter__(self):
        return self.entries.iteritems()

    def FindTranslation(self, image):
        '''Locate a translation by image name. Needed because translations can handle multiple images'''
        x = [v for k,v in self if image in v.images]
        if len(x) == 1:
            return x[0]
        else:
            raise "Bang"

    def BindTranslation(self, image, ba):
        '''Map Bundle elements through the translation layer into concrete elements'''
        return map(lambda x:(x.tag, x.attrib),
                   self.FindTranslation(image).trans[ba.tag][ba.attrib['name']])
            
class BundleSet(DirectoryBacked):
    '''The Bundler handles creation of dependent clauses based on bundle definitions'''
    __child__ = Bundle

    def __iter__(self):
        return self.entries.iteritems()

class bundler(Structure):
    '''The bundler creates dependent clauses based on the bundle/translation scheme from bcfg1'''
    def __init__(self, core, datastore):
        self.core = core
        self.datastore = "%s/bundler/"%(datastore)
        self.bundles = BundleSet("%s/bundles"%(self.datastore), self.core.fam)
        self.translations = TranslationSet("%s/translations"%(self.datastore), self.core.fam)
        # now we build the local repr of the translated bundleset
        self.core.fam.AddMonitor("%s/bundles"%(self.datastore), self)
        self.core.fam.AddMonitor("%s/translations"%(self.datastore), self)
        # check which order events will be delivered in; need bundles/trans updated before self
        self.HandleEvent(True)

    def HandleEvent(self,event):
        self.built = {}
        for image in reduce(lambda x,y:x+y, [v.images for k,v in self.translations],[]):
            self.built[image] = {}
            for (name,bundle) in self.bundles:
                name = name[:-4]
                self.built[image][name] = []
                for entry in bundle:
                    self.built[image][name].extend(self.translations.BindTranslation(image,entry))

    def Construct(self, metadata):
        return map(lambda x:self.built[metadata.image][x], metadata.bundles)

