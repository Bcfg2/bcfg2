'''This module implements a templating generator based on Genshi'''
__revision__ = '$Revision$'

from genshi.template import TemplateLoader, TextTemplate, MarkupTemplate, TemplateError
import logging, lxml.etree, posixpath, re, os
import Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.TGenshi')
info = re.compile('^owner:(\s)*(?P<owner>\w+)$|group:(\s)*(?P<group>\w+)$|' +
                  'perms:(\s)*(?P<perms>\w+)$')

class TemplateFile:
    '''Template file creates Genshi template structures for the loaded file'''
    def __init__(self, name, loader, properties):
        self.name = name
        self.states = {'template': False, 'info': False}
        self.metadata = {'owner': 'root', 'group': 'root', 'perms': '0644'}
        self.properties = properties
        self.loader = loader
        
    def HandleEvent(self, event):
        '''Handle all fs events for this template'''
        if event.filename in ['template.xml', 'template.txt']:
            try:
                if event.filename.endswith('.txt'):
                    self.template = self.loader.load(os.path.join(self.name[1:], event.filename), cls=TextTemplate)
                else:
                    self.template = self.loader.load(os.path.join(self.name[1:], event.filename), cls=MarkupTemplate)
            except TemplateError, terror:
                logger.error('Genshi template error: %s' % terror)
            
        elif event.filename == 'info':
            for line in open(self.name + '/info').readlines():
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
        else:
            logger.info('Ignoring event for %s' % event.filename)
            
    def BuildFile(self, entry, metadata):
        '''Build literal file information'''
        fname = entry.get('realname', entry.get('name'))
        try:
            stream = self.template.generate(name=fname,
                                            metadata=metadata,
                                            properties=self.properties)
            if isinstance(self.template, TextTemplate):
                entry.text = stream.render('text')
            else:
                entry.text = stream.render('xml')
        except TemplateError, terror:
            logger.error('Genshi template error: %s' % terror)
            raise Bcfg2.Server.Plugin.PluginExecutionError
        [entry.attrib.__setitem__(key, value) for (key, value) in self.metadata.iteritems()]

class GenshiProperties(Bcfg2.Server.Plugin.SingleXMLFileBacked):
    '''Class for Genshi properties'''
    def Index(self):
        '''Build data into an elementtree object for templating usage'''
        try:
            self.properties = lxml.etree.XML(self.data)
            del self.data
        except lxml.etree.XMLSyntaxError:
            logger.error("Failed to parse properties")

class FakeProperties:
    '''Dummy class used when properties dont exist'''
    def __init__(self):
        self.properties = lxml.etree.Element("Properties")

class TGenshi(Bcfg2.Server.Plugin.Plugin):
    '''The TGenshi generator implements a templating mechanism for configuration files'''
    __name__ = 'TGenshi'
    __version__ = '$Id$'
    __author__ = 'jeff@ocjtech.us'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        if self.data[-1] == '/':
            self.data = self.data[:-1]
        self.Entries['ConfigFile'] = {}
        self.entries = {}
        self.handles = {}
        self.loader = TemplateLoader(self.data, auto_reload=True)
        self.AddDirectoryMonitor('')
        try:
            self.properties = GenshiProperties('%s/../etc/properties.xml' \
                                               % (self.data), self.core.fam)
        except:
            self.properties = FakeProperties()
            self.logger.info("Failed to read properties file; TGenshi properties disabled")

    def BuildEntry(self, entry, metadata):
        '''Dispatch fetch calls to the correct object'''
        self.entries[entry.get('name')].BuildFile(entry, metadata)

    def HandleEvent(self, event):
        '''Unified FAM event handler for DirShadow'''
        action = event.code2str()
        if event.filename[0] == '/':
            return
        epath = "".join([self.data, self.handles[event.requestID], event.filename])
        if event.filename in ['info', 'template.xml', 'template.txt']:
            identifier = self.handles[event.requestID][:-1]
        else:
            identifier = self.handles[event.requestID] + event.filename
        if action in ['exists', 'created']:
            if posixpath.isdir(epath):
                self.AddDirectoryMonitor(epath[len(self.data):])
            elif event.filename in ['info', 'template.xml', 'template.txt']:
                if not self.entries.has_key(identifier):
                    self.entries[identifier] = TemplateFile(identifier, self.loader, self.properties)
                    self.Entries['ConfigFile'][identifier] = self.BuildEntry
                self.entries[identifier].HandleEvent(event)
            else:
                logger.info('Not creating template for %s' % identifier)
        elif action == 'changed':
            if self.entries.has_key(identifier):
                self.entries[identifier].HandleEvent(event)
        elif action == 'deleted':
            if event.filename in ['template.xml', 'template.txt'] and self.entries.has_key(identifier):
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
                print "Genshi: Failed to open directory %s" % (name)
                return
            reqid = self.core.fam.AddMonitor(name, self)
            self.handles[reqid] = relative
