'''This module sets up a base list of configuration entries'''
__revision__ = '$Revision$'

from copy import deepcopy

from Bcfg2.Server.Generator import SingleXMLFileBacked
from Bcfg2.Server.Structure import Structure

from elementtree.ElementTree import Element, XML

class BaseFile(SingleXMLFileBacked):
    '''The Base file contains unstructured/independent configuration elements'''
    
    def Index(self):
        '''Store XML data in reasonable structures'''
        self.store = {'Class':{'all':[]}, 'Image':{'all':[]}, 'all':[]}
        for entry in XML(self.data).getchildren():
            self.store[entry.tag][entry.get('name')] = {'all':[], 'Class':{}, 'Image':{}}
            if entry.tag in ['Image', 'Class']:
                for child in entry.getchildren():
                    if child.tag in ['Image', 'Class']:
                        self.store[entry.tag][entry.get('name')][child.tag][child.get('name')] = child.getchildren()
                    else:
                        self.store[entry.tag][entry.get('name')]['all'].append(child)
            else:
                self.store[entry.tag]['all'].append(child)

    def Construct(self, metadata):
        '''Build structures for client described by metadata'''
        ret = Element("Independant", version='2.0')
        idata = self.store['Image'].get(metadata.image, {'all':[], 'Class':{}})
        for entry in idata['all']:
            ret.append(deepcopy(entry))
        for cls in metadata.classes:
            for entry in idata['Class'].get(cls, []):
                ret.append(deepcopy(entry))
            cdata = self.store['Class'].get(cls, {'all':[], 'Image':{}})
            for entry in cdata['all']:
                ret.append(deepcopy(entry))
            for entry in cdata['Image'].get(metadata.image, []):
                ret.append(deepcopy(entry))
        return [ret]

class Base(Structure):
    '''This Structure is good for the pile of independent configs needed for most actual systems'''
    __name__ =  'Base'
    __version__ = '$Id$'
    
    '''base creates independent clauses based on client metadata'''
    def __init__(self, core, datastore):
        Structure.__init__(self, core, datastore)
        self.base = BaseFile("%s/etc/base.xml"%(datastore), self.core.fam)
        self.Construct = self.base.Construct
