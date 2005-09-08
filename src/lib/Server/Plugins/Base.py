'''This module sets up a base list of configuration entries'''
__revision__ = '$Revision$'

from copy import deepcopy
from syslog import syslog, LOG_ERR
from Bcfg2.Server.Plugin import Plugin, SingleXMLFileBacked

from elementtree.ElementTree import Element, XML
from xml.parsers.expat import ExpatError

class BaseFile(SingleXMLFileBacked):
    '''The Base file contains unstructured/independent configuration elements'''
    
    def Index(self):
        '''Store XML data in reasonable structures'''
        self.store = {'Class':{'all':[]}, 'Image':{'all':[]}, 'all':[]}
        try:
            xdata = XML(self.data)
        except ExpatError:
            syslog(LOG_ERR, "Failed to parse base.xml")
            return
        for entry in xdata.getchildren():
            self.store[entry.tag][entry.get('name')] = {'all':[], 'Class':{}, 'Image':{}}
            if entry.tag in ['Image', 'Class']:
                for child in entry.getchildren():
                    if child.tag in ['Image', 'Class']:
                        self.store[entry.tag][entry.get('name')][child.tag][child.get('name')] = child.getchildren()
                    else:
                        self.store[entry.tag][entry.get('name')]['all'].append(child)
            else:
                self.store[entry.tag]['all'].append(child)

    def BuildStructures(self, metadata):
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

class Base(Plugin):
    '''This Structure is good for the pile of independent configs needed for most actual systems'''
    __name__ =  'Base'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    
    '''base creates independent clauses based on client metadata'''
    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        self.base = BaseFile("%s/etc/base.xml"%(datastore), self.core.fam)
        self.BuildStructures = self.base.BuildStructures
