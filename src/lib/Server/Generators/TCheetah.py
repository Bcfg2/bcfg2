'''This module implements a templating generator based on Cheetah'''
__revision__ = '$Revision$'

from posixpath import isdir
from syslog import syslog, LOG_ERR
from Bcfg2.Server.Generator import Generator, GeneratorError, FileBacked, SingleXMLFileBacked
from elementtree.ElementTree import XML
from xml.parsers.expat import ExpatError
from Cheetah.Template import Template

class TemplateFile(FileBacked):
    '''Template file creates Cheetah template structures for the loaded file'''
    def __init__(self, name, properties):
        FileBacked.__init__(self, name)
        self.properties = properties
    
    def Index(self):
        '''Create the template data structures'''
        self.template = Template(self.data, searchList=[self.properties])
        self.template.properties = self.properties.properties
        # put in owner permission detection

    def BuildFile(self, entry):
        '''Build literal file information'''
        try:
            entry.text = str(self.template)
        except:
            syslog(LOG_ERR, "TCheetah: Failed to template %s" % entry.get('name'))
            raise GeneratorError
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})


class CheetahProperties(SingleXMLFileBacked):
    '''Class for Cheetah properties'''
    def Index(self):
        '''Build data into an elementtree object for templating usage'''
        try:
            self.properties = XML(self.data)
            del self.data
        except ExpatError:
            syslog(LOG_ERR, "TCheetah: Failed to parse properties")

class TCheetah(Generator):
    '''The TCheetah generator implements a templating mechanism for configuration files'''
    __name__ = 'TCheetah'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        if self.data[-1] == '/':
            self.data = self.data[:-1]
        self.__provides__['ConfigFile'] = {}
        self.entries = {}
        self.handles = {}
        self.AddDirectoryMonitor('')
        self.properties = CheetahProperties('%s/../etc/properties.xml' % self.data, self.core.fam)

    def BuildEntry(self, entry, metadata):
        '''Dispatch fetch calls to the correct object'''
        self.entries[entry.get('name')].BuildFile(entry)

    def MapName(self, name):
        '''MapName finds the object corresponding to a particular file
        the DirShadow MapName method maps filenames literally'''
        return name        

    def HandleEvent(self, event):
        '''Unified FAM event handler for DirShadow'''
        #print "got event %s %s %s" % ( event.code2str(), event.filename, event.requestID)
        action = event.code2str()
        if event.filename[0] == '/':
            return
        epath = "".join([self.data, self.handles[event.requestID], event.filename])
        identifier = self.MapName(epath[len(self.data):])
        if action in ['exists', 'created']:
            if isdir(epath):
                self.AddDirectoryMonitor(epath[len(self.data):])
            else:
                if self.entries.has_key(identifier):
                    pass
                else:
                    #try:
                    self.entries[identifier] = TemplateFile(epath, self.properties)
                    self.entries[identifier].HandleEvent(event)
                    self.__provides__['ConfigFile'][identifier] = self.BuildEntry
                    #except:
                    #   syslog(LOG_ERR, "TCheetah: bad format for file %s" % identifier)
        elif action == 'changed':
            if self.entries.has_key(identifier):
                self.entries[identifier].HandleEvent(event)
        elif action == 'deleted':
            if self.entries.has_key[identifier]:
                del self.entries[identifier]
                del self.__provides__['ConfigFile'][identifier]
                                 
    def AddDirectoryMonitor(self, relative):
        '''Add new directory to FAM structures'''
        if not relative:
            relative = '/'
        if relative[-1] != '/':
            relative += '/'
        name = self.data + relative
        if relative not in self.handles.values():
            if not isdir(name):
                print "Cheetah: Failed to open directory %s" % (name)
                return
            reqid = self.core.fam.AddMonitor(name, self)
            self.handles[reqid] = relative
