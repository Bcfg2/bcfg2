'''This module implements a templating generator based on Cheetah'''
__revision__ = '$Revision$'

import logging, lxml.etree, posixpath, re, Cheetah.Template
import Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.TCheetah')
info = re.compile('^owner:(\s)*(?P<owner>\w+)$|group:(\s)*(?P<group>\w+)$|' +
                  'perms:(\s)*(?P<perms>\w+)$')

class TemplateFile:
    '''Template file creates Cheetah template structures for the loaded file'''
    def __init__(self, name, properties):
        self.name = name
        self.properties = properties
        self.states = {'template': False, 'info': False}
        self.metadata = {'owner': 'root', 'group': 'root', 'perms': '644'}

    def HandleEvent(self, event):
        '''Handle all fs events for this template'''
        if event.filename == 'template':
            self.template = Cheetah.Template.Template(open(self.name).read())
            self.template.properties = self.properties.properties
        elif event.filename == 'info':
            for line in open(self.name[:-8] + '/info').readlines():
                match = info.match(line)
                if not match:
                    logger.warning("Failed to match line: %s"%line)
                    continue
                else:
                    mgd = match.groupdict()
                    if mgd['owner']:
                        self.metadata['owner'] = mgd['owner']
                    elif mgd['group']:
                        self.metadata['group'] = mgd['group']
                    elif mgd['perms']:
                        self.metadata['perms'] = mgd['perms']
                        if len(self.metadata['perms']) == 3:
                            self.metadata['perms'] = "0%s" % (self.metadata['perms'])              
    
    def BuildFile(self, entry, metadata):
        '''Build literal file information'''
        self.template.metadata = metadata
        self.template.properties = self.properties.properties
        try:
            entry.text = str(self.template)
        except:
            logger.error("Failed to template %s" % entry.get('name'), exc_info=1)
            raise Bcfg2.Server.Plugin.PluginExecutionError
        [entry.attrib.__setitem__(key, value) for (key, value) in self.metadata.iteritems()]

class CheetahProperties(Bcfg2.Server.Plugin.SingleXMLFileBacked):
    '''Class for Cheetah properties'''
    def Index(self):
        '''Build data into an elementtree object for templating usage'''
        try:
            self.properties = lxml.etree.XML(self.data)
            del self.data
        except lxml.etree.XMLSyntaxError:
            logger.error("Failed to parse properties")

class TCheetah(Bcfg2.Server.Plugin.Plugin):
    '''The TCheetah generator implements a templating mechanism for configuration files'''
    __name__ = 'TCheetah'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        if self.data[-1] == '/':
            self.data = self.data[:-1]
        self.Entries['ConfigFile'] = {}
        self.entries = {}
        self.handles = {}
        self.AddDirectoryMonitor('')
        self.properties = CheetahProperties('%s/../etc/properties.xml' % self.data, self.core.fam)

    def BuildEntry(self, entry, metadata):
        '''Dispatch fetch calls to the correct object'''
        self.entries[entry.get('name')].BuildFile(entry, metadata)

    def HandleEvent(self, event):
        '''Unified FAM event handler for DirShadow'''
        #print "got event %s %s %s" % ( event.code2str(), event.filename, event.requestID)
        action = event.code2str()
        if event.filename[0] == '/':
            return
        epath = "".join([self.data, self.handles[event.requestID], event.filename])
        if event.filename in ['info', 'template']:
            identifier = self.handles[event.requestID][:-1]
        else:
            identifier = self.handles[event.requestID] + event.filename
        if action in ['exists', 'created']:
            if posixpath.isdir(epath):
                self.AddDirectoryMonitor(epath[len(self.data):])
            else:
                if not self.entries.has_key(identifier):
                    self.entries[identifier] = TemplateFile(epath, self.properties)
                    self.Entries['ConfigFile'][identifier] = self.BuildEntry
                self.entries[identifier].HandleEvent(event)
        elif action == 'changed':
            if self.entries.has_key(identifier):
                self.entries[identifier].HandleEvent(event)
        elif action == 'deleted':
            # the template file is the sentinal that creates a real entry
            if event.filename == 'template' and self.entries.has_key(identifier):
                del self.entries[identifier]
                del self.Entries['ConfigFile'][identifier]
                                 
    def AddDirectoryMonitor(self, relative):
        '''Add new directory to FAM structures'''
        if not relative:
            relative = '/'
        if relative[-1] != '/':
            relative += '/'
        name = self.data + relative
        if relative not in self.handles.values():
            if not posixpath.isdir(name):
                print "Cheetah: Failed to open directory %s" % (name)
                return
            reqid = self.core.fam.AddMonitor(name, self)
            self.handles[reqid] = relative
