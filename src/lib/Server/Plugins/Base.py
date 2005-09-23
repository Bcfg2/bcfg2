'''This module sets up a base list of configuration entries'''
__revision__ = '$Revision$'

from copy import deepcopy
from elementtree.ElementTree import Element, XML
from xml.parsers.expat import ExpatError

from Bcfg2.Server.Plugin import Plugin, PluginInitError, SingleXMLFileBacked

class Base(Plugin, SingleXMLFileBacked):
    '''This Structure is good for the pile of independent configs needed for most actual systems'''
    __name__ =  'Base'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    
    '''base creates independent clauses based on client metadata'''
    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        self.store = {'all':[], 'Class':{'all':[]}, 'Image':{'all':[]}, 'all':[]}
        try:
            SingleXMLFileBacked.__init__(self, "%s/etc/base.xml"%(datastore), self.core.fam)
        except OSError:
            self.LogError("Failed to load base.xml")
            raise PluginInitError
        
    def Index(self):
        '''Store XML data in reasonable structures'''
        try:
            xdata = XML(self.data)
        except ExpatError:
            self.LogError("Failed to parse base.xml")
            return
        for entry in xdata.getchildren():
            if entry.tag in ['Image', 'Class']:
                if not self.store[entry.tag].has_key(entry.get('name')):
                    self.store[entry.tag][entry.get('name')] = {'all':[], 'Class':{}, 'Image':{}}
                for child in entry.getchildren():
                    if child.tag in ['Image', 'Class']:
                        self.store[entry.tag][entry.get('name')][child.tag][child.get('name')] = child.getchildren()
                    else:
                        self.store[entry.tag][entry.get('name')]['all'].append(child)
            else:
                self.store['all'].append(child)

    def BuildStructures(self, metadata):
        '''Build structures for client described by metadata'''
        ret = Element("Independant", version='2.0')
        [ret.append(deepcopy(entry)) for entry in self.store['all']]
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
