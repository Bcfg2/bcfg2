'''This module implements a config file repository'''
__revision__ = '$Revision$'

import binascii, logging, os, re, stat, tempfile, Bcfg2.Server.Plugin, lxml.etree

logger = logging.getLogger('Bcfg2.Plugins.Cfg')

specific = re.compile('(.*/)(?P<filename>[\S\-.]+)\.((H_(?P<hostname>\S+))|' +
                      '(G(?P<prio>\d+)_(?P<group>\S+)))$')
probeData = {}

class SpecificityError(Exception):
    '''Thrown in case of filename parse failure'''
    pass

class FileEntry(Bcfg2.Server.Plugin.FileBacked):
    '''The File Entry class pertains to the config files contained in a particular directory.
    This includes :info, all base files and deltas'''

    def __init__(self, myid, name):
        Bcfg2.Server.Plugin.FileBacked.__init__(self, name)
        self.name = name
        self.identity = myid
        self.all = False
        self.hostname = False
        self.group = False
        self.op = False
        self.prio = False
        if name.split('.')[-1] in ['cat', 'diff']:
            self.op = name.split('.')[-1]
            name = name[:-(len(self.op) + 1)]
        if self.name.split('/')[-1] == myid.split('/')[-1]:
            self.all = True
        else:
            data = specific.match(name)
            if not data:
                logger.error("Failed to match %s" % name)
                raise SpecificityError
            if data.group('hostname') != None:
                self.hostname = data.group('hostname')
            else:
                self.group = data.group('group')
                self.prio = int(data.group('prio'))

    def __cmp__(self, other):
        data = [[getattr(self, field) for field in ['all', 'group', 'hostname']],
                [getattr(other, field) for field in ['all', 'group', 'hostname']]]
        for index in range(3):
            if data[0][index] and not data[1][index]:
                return -1
            elif data[1][index] and not data[0][index]:
                return 1
            elif data[0][index] and data[1][index]:
                if hasattr(self, 'prio')  and hasattr(other, 'prio'):
                    return self.prio - other.prio
                else:
                    return 0
            else:
                pass
        logger.critical("Ran off of the end of the world sorting %s" % (self.name))

    def applies(self, metadata):
        '''Predicate if fragment matches client metadata'''
        if self.all or (self.hostname == metadata.hostname) or \
           (self.group in metadata.groups):
            return True
        else:
            return False

class ConfigFileEntry(object):
    '''ConfigFileEntry is a repository entry for a single file, containing
    all data for all clients.'''
    info = re.compile('^owner:(\s)*(?P<owner>\w+)|group:(\s)*(?P<group>\w+)|' +
                      'perms:(\s)*(?P<perms>\w+)|encoding:(\s)*(?P<encoding>\w+)|' +
                      '(?P<paranoid>paranoid(\s)*)|interpolate:(\s)*(?P<interpolate>\w+)(\s)*$')
    
    def __init__(self, path, repopath):
        object.__init__(self)
        self.path = path
        self.repopath = repopath
        self.fragments = []
        self.metadata = {'encoding': 'ascii', 'owner':'root', 'group':'root', 'perms':'0644'}
        self.paranoid = False
        self.interpolate = False
        
    def read_info(self):
        '''read in :info metadata'''
        self.interpolate = False
        self.paranoid = False
        filename = "%s/:info" % self.repopath
        for line in open(filename).readlines():
            match = self.info.match(line)
            if not match:
                logger.warning("Failed to match line: %s"%line)
                continue
            else:
                mgd = match.groupdict()
                if mgd['owner']:
                    self.metadata['owner'] = mgd['owner']
                elif mgd['group']:
                    self.metadata['group'] = mgd['group']
                elif mgd['encoding']:
                    self.metadata['encoding'] = mgd['encoding']
                elif mgd['perms']:
                    self.metadata['perms'] = mgd['perms']
                    if len(self.metadata['perms']) == 3:
                        self.metadata['perms'] = "0%s" % (self.metadata['perms'])
                elif mgd['paranoid'] in ["True", "true"]:
                    self.paranoid = True
                elif mgd['interpolate'] in ["True", "true"]:
                    self.interpolate = True
                    
    def AddEntry(self, name):
        '''add new file additions for a single cf file'''
        basename = name.split('/')[-1]
        rbasename = self.repopath.split('/')[-1]
        if not ((basename == ':info') or (basename[:len(rbasename)] == rbasename)):
            logger.error("Confused about file %s; ignoring" % (name))
            return
        if basename == ':info':
            return self.read_info()

        try:
            self.fragments.append(FileEntry(self.path, name))
            self.fragments.sort()
        except SpecificityError:
            return

    def HandleEvent(self, event):
        '''Handle FAM updates'''
        action = event.code2str()
        #logger.debug("Got event %s for %s" % (action, event.filename))
        if event.filename == ':info':
            if action in ['changed', 'exists', 'created']:
                return self.read_info()
        if event.filename != self.path.split('/')[-1]:
            if not specific.match('/' + event.filename):
                logger.info('Suppressing event for bogus file %s' % event.filename)
                return

        entries = [entry for entry in self.fragments if
                   entry.name.split('/')[-1] == event.filename]

        if len(entries) == 0:
            logger.error("Failed to match entry for spec %s" % (event.filename))
        elif len(entries) > 1:
            logger.error("Matched multiple entries for spec %s" % (event.filename))
            
        if action == 'deleted':
            logger.info("Removing entry %s" % event.filename)
            for entry in entries:
                logger.info("Removing entry %s" % (entry.name))
                self.fragments.remove(entry)
                self.fragments.sort()
            logger.info("Entry deletion completed")
        elif action in ['changed', 'exists', 'created']:
            [entry.HandleEvent(event) for entry in entries]
        else:
            logger.error("Unhandled Action %s for file %s" % (action, event.filename))

    def GetConfigFile(self, entry, metadata):
        '''Fetch config file from repository'''
        name = entry.attrib['name']
        filedata = ""
        # first find basefile
        try:
            basefiles = [bfile for bfile in self.fragments if bfile.applies(metadata) and not bfile.op]
            basefiles.sort()
            basefile = basefiles[-1]
        except IndexError:
            logger.error("Failed to locate basefile for %s" % name)
            raise Bcfg2.Server.Plugin.PluginExecutionError, ('basefile', name)
        filedata += basefile.data
        #logger.debug("Used basefile %s" % (basefile.name))

        for delta in [delta for delta in self.fragments if delta.applies(metadata) and delta.op]:
            if delta.op == 'cat':
                lines = filedata.split('\n')
                if not lines[-1]:
                    lines = lines[:-1]
                dlines = [dline for dline in delta.data.split('\n') if dline]
                for line in dlines:
                    if line[0] == '-':
                        if line[1:] in lines:
                            lines.remove(line[1:])
                    else:
                        lines.append(line[1:])
                filedata = "\n".join(lines) + "\n"
            elif delta.op == 'diff':
                basefile = open(tempfile.mktemp(), 'w')
                basefile.write(filedata)
                basefile.close()
                dfile = open(tempfile.mktemp(), 'w')
                dfile.write(delta.data)
                dfile.close()
                ret = os.system("patch -uf %s < %s > /dev/null 2>&1"%(basefile.name, dfile.name))
                output = open(basefile.name, 'r').read()
                [os.unlink(fname) for fname in [basefile.name, dfile.name]]
                if ret >> 8 != 0:
                    raise Bcfg2.Server.Plugin.PluginExecutionError, ('delta', delta)
                filedata = output
            else:
                logger.error("Unknown delta type %s" % (delta.op))
            
        [entry.attrib.__setitem__(key, value) for (key, value) in self.metadata.iteritems()]
        if self.interpolate:
            if metadata.hostname in probeData:
                for name, value in probeData[metadata.hostname].iteritems():
                    filedata = filedata.replace("@@%s@@"%name, value )
            else:
                logger.warning("Cannot interpolate data for client: %s for config file: %s"% (metadata.hostname, basefile.name))
        if self.paranoid:
            entry.attrib['paranoid'] = 'true'
        if entry.attrib['encoding'] == 'base64':
            entry.text = binascii.b2a_base64(filedata)
            return
        if filedata == '':
            entry.set('empty', 'true')
        else:
            try:
                entry.text = filedata
            except:
                logger.error("Failed to marshall file %s. Mark it as base64" % (entry.get('name')))

class Cfg(Bcfg2.Server.Plugin.Plugin):
    '''This generator in the configuration file repository for bcfg2'''
    __name__ = 'Cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    tempfile = re.compile("^.*~$|^.*\.swp")

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.entries = {}
        self.Entries = {'ConfigFile':{}}
        self.famID = {}
        self.directories = []
        self.AddDirectoryMonitor(self.data)
        self.interpolate = False #this is true if any file in the repo needs to be interpolated.
        try:
            self.probes = Bcfg2.Server.Plugin.DirectoryBacked(datastore + '/Probes', self.core.fam )
        except:
            self.probes = False
        # eventually flush fam events here so that all entries built here
        # ready to go

    def GetProbes(self, _):
        '''Return a set of probes for execution on client'''
        ret = []
        bangline = re.compile('^#!(?P<interpreter>(/\w+)+)$')
        if self.interpolate:
            if self.probes:
                for name, entry in self.probes.entries.iteritems():
                    probe = lxml.etree.Element('probe')
                    probe.set('name', name )
                    probe.set('source', 'Cfg')
                    probe.text = entry.data
                    match = bangline.match(entry.data.split('\n')[0])
                    if match:
                        probe.set('interpreter', match.group('interpreter'))
                    ret.append(probe)
            probe = lxml.etree.Element('probe')
            probe.set('name', 'hostname')
            probe.set('source', 'Cfg')
            probe.text = '''/bin/hostname'''
            ret.append(probe)
        return ret

    def ReceiveData(self, client, data):
        '''Receive probe results pertaining to client'''
        probeData[client.hostname] = { data.get('name'):data.text }

    def AddDirectoryMonitor(self, name):
        '''Add new directory to FAM structures'''
        if name not in self.directories:
            try:
                os.stat(name)
            except OSError:
                logger.error("Failed to open directory %s" % (name))
                return
            reqid = self.core.fam.AddMonitor(name, self)
            self.famID[reqid] = name
            self.directories.append(name)

    def AddEntry(self, name, event):
        '''Add new entry to FAM structures'''
        try:
            sdata = os.stat(name)[stat.ST_MODE]
        except OSError:
            return

        if stat.S_ISDIR(sdata):
            self.AddDirectoryMonitor(name)
        else:
            # file entries shouldn't contain path-to-repo
            shortname = '/'+ '/'.join(name[len(self.data)+1:].split('/')[:-1])
            repodir = '/' + '/'.join(name.split('/')[:-1])
            if not self.entries.has_key(shortname):
                self.entries[shortname] = ConfigFileEntry(shortname, repodir)
                self.Entries['ConfigFile'][shortname] = self.entries[shortname].GetConfigFile
            self.entries[shortname].AddEntry(name)
            self.entries[shortname].HandleEvent(event)

    def HandleEvent(self, event):
        '''Handle FAM updates'''
        action = event.code2str()
        if self.tempfile.match(event.filename):
            logger.info("Suppressed event for file %s" % event.filename)
            return
        if event.filename[0] != '/':
            filename = "%s/%s" % (self.famID[event.requestID], event.filename)
        else:
            filename = event.filename
        configfile = filename[len(self.data):-(len(event.filename)+1)]

        if ((action in ['exists', 'created']) and (filename != self.data)):
            self.AddEntry(filename, event)
        elif action == 'changed':
            # pass the event down the chain to the ConfigFileEntry
            if self.entries.has_key(configfile):
                self.entries[configfile].HandleEvent(event)
            else:
                if filename != self.data:
                    self.AddEntry(filename, event)
                else:
                    logger.error("Ignoring event for %s"%(configfile))
        elif action == 'deleted':
            if self.entries.has_key(configfile):
                self.entries[configfile].HandleEvent(event)
        elif action in ['exists', 'endExist']:
            pass
        else:
            logger.error("Got unknown event %s %s:%s" % (action, event.requestID, event.filename))
        self.interpolate = len([entry for entry in self.entries.values() if entry.interpolate ]) > 0

