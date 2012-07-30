"""This module provides the baseclass for Bcfg2 Server Plugins."""

import copy
import logging
import lxml.etree
import os
import pickle
import posixpath
import re
import sys
import threading
import Bcfg2.Server
from Bcfg2.Bcfg2Py3k import ConfigParser

import Bcfg2.Options

# py3k compatibility
if sys.hexversion >= 0x03000000:
    from functools import reduce
    from io import FileIO as BUILTIN_FILE_TYPE
else:
    BUILTIN_FILE_TYPE = file
from Bcfg2.Bcfg2Py3k import Queue
from Bcfg2.Bcfg2Py3k import Empty
from Bcfg2.Bcfg2Py3k import Full

# make encoding available
encparse = Bcfg2.Options.OptionParser({'encoding': Bcfg2.Options.ENCODING})
encparse.parse([])
encoding = encparse['encoding']

# grab default metadata info from bcfg2.conf
opts = {'owner': Bcfg2.Options.MDATA_OWNER,
        'group': Bcfg2.Options.MDATA_GROUP,
        'perms': Bcfg2.Options.MDATA_PERMS,
        'secontext': Bcfg2.Options.MDATA_SECONTEXT,
        'important': Bcfg2.Options.MDATA_IMPORTANT,
        'paranoid': Bcfg2.Options.MDATA_PARANOID,
        'sensitive': Bcfg2.Options.MDATA_SENSITIVE}
mdata_setup = Bcfg2.Options.OptionParser(opts)
mdata_setup.parse([])
del mdata_setup['args']

logger = logging.getLogger('Bcfg2.Server.Plugin')

default_file_metadata = mdata_setup

info_regex = re.compile( \
    'encoding:(\s)*(?P<encoding>\w+)|' +
    'group:(\s)*(?P<group>\S+)|' +
    'important:(\s)*(?P<important>\S+)|' +
    'mtime:(\s)*(?P<mtime>\w+)|' +
    'owner:(\s)*(?P<owner>\S+)|' +
    'paranoid:(\s)*(?P<paranoid>\S+)|' +
    'perms:(\s)*(?P<perms>\w+)|' +
    'secontext:(\s)*(?P<secontext>\S+)|' +
    'sensitive:(\s)*(?P<sensitive>\S+)|')

def bind_info(entry, metadata, infoxml=None, default=default_file_metadata):
    for attr, val in list(default.items()):
        entry.set(attr, val)
    if infoxml:
        mdata = dict()
        infoxml.pnode.Match(metadata, mdata, entry=entry)
        if 'Info' not in mdata:
            msg = "Failed to set metadata for file %s" % entry.get('name')
            logger.error(msg)
            raise PluginExecutionError(msg)
        for attr, val in list(mdata['Info'][None].items()):
            entry.set(attr, val)


class PluginInitError(Exception):
    """Error raised in cases of Plugin initialization errors."""
    pass


class PluginExecutionError(Exception):
    """Error raised in case of Plugin execution errors."""
    pass


class Debuggable(object):
    __rmi__ = ['toggle_debug']

    def __init__(self, name=None):
        if name is None:
            name = "%s.%s" % (self.__class__.__module__,
                              self.__class__.__name__)
        self.debug_flag = False
        self.logger = logging.getLogger(name)

    def toggle_debug(self):
        self.debug_flag = not self.debug_flag
        self.debug_log("%s: debug_flag = %s" % (self.__class__.__name__,
                                                self.debug_flag),
                       flag=True)
        return self.debug_flag

    def debug_log(self, message, flag=None):
        if (flag is None and self.debug_flag) or flag:
            self.logger.error(message)


class DatabaseBacked(object):
    def __init__(self):
        pass


class PluginDatabaseModel(object):
    class Meta:
        app_label = "Server"


class Plugin(Debuggable):
    """This is the base class for all Bcfg2 Server plugins.
    Several attributes must be defined in the subclass:
    name : the name of the plugin
    __author__ : the author/contact for the plugin

    Plugins can provide three basic types of functionality:
      - Structure creation (overloading BuildStructures)
      - Configuration entry binding (overloading HandlesEntry, or loads the Entries table)
      - Data collection (overloading GetProbes/ReceiveData)
    """
    name = 'Plugin'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    experimental = False
    deprecated = False
    conflicts = []

    # Default sort_order to 500. Plugins of the same type are
    # processed in order of ascending sort_order value. Plugins with
    # the same sort_order are sorted alphabetically by their name.
    sort_order = 500

    def __init__(self, core, datastore):
        """Initialize the plugin.

        :param core: the Bcfg2.Server.Core initializing the plugin
        :param datastore: the filesystem path of Bcfg2's repository
        """
        object.__init__(self)
        self.Entries = {}
        self.core = core
        self.data = os.path.join(datastore, self.name)
        self.running = True
        Debuggable.__init__(self, name=self.name)

    @classmethod
    def init_repo(cls, repo):
        os.makedirs(os.path.join(repo, cls.name))

    def shutdown(self):
        self.running = False

    def __str__(self):
        return "%s Plugin" % self.__class__.__name__


class Generator(object):
    """Generator plugins contribute to literal client configurations."""
    def HandlesEntry(self, entry, metadata):
        """This is the slow path method for routing configuration binding requests."""
        return False

    def HandleEntry(self, entry, metadata):
        """This is the slow-path handler for configuration entry binding."""
        raise PluginExecutionError


class Structure(object):
    """Structure Plugins contribute to abstract client configurations."""
    def BuildStructures(self, metadata):
        """Return a list of abstract goal structures for client."""
        raise PluginExecutionError


class Metadata(object):
    """Signal metadata capabilities for this plugin"""
    def add_client(self, client_name):
        """Add client."""
        pass

    def remove_client(self, client_name):
        """Remove client."""
        pass

    def viz(self, hosts, bundles, key, colors):
        """Create viz str for viz admin mode."""
        pass

    def _handle_default_event(self, event):
        pass

    def get_initial_metadata(self, client_name):
        raise PluginExecutionError

    def merge_additional_data(self, imd, source, groups, data):
        raise PluginExecutionError


class Connector(object):
    """Connector Plugins augment client metadata instances."""
    def get_additional_groups(self, metadata):
        """Determine additional groups for metadata."""
        return list()

    def get_additional_data(self, metadata):
        """Determine additional data for metadata instances."""
        return dict()


class Probing(object):
    """Signal probe capability for this plugin."""
    def GetProbes(self, _):
        """Return a set of probes for execution on client."""
        return []

    def ReceiveData(self, _, dummy):
        """Receive probe results pertaining to client."""
        pass


class Statistics(object):
    """Signal statistics handling capability."""
    def process_statistics(self, client, xdata):
        pass


class ThreadedStatistics(Statistics,
                         threading.Thread):
    """Threaded statistics handling capability."""
    def __init__(self, core, datastore):
        Statistics.__init__(self)
        threading.Thread.__init__(self)
        # Event from the core signaling an exit
        self.terminate = core.terminate
        self.work_queue = Queue(100000)
        self.pending_file = "%s/etc/%s.pending" % (datastore, self.__class__.__name__)
        self.daemon = False
        self.start()

    def save(self):
        """Save any pending data to a file."""
        pending_data = []
        try:
            while not self.work_queue.empty():
                (metadata, data) = self.work_queue.get_nowait()
                try:
                    pending_data.append((metadata.hostname, lxml.etree.tostring(data)))
                except:
                    self.logger.warning("Dropping interaction for %s" % metadata.hostname)
        except Empty:
            pass

        try:
            savefile = open(self.pending_file, 'w')
            pickle.dump(pending_data, savefile)
            savefile.close()
            self.logger.info("Saved pending %s data" % self.__class__.__name__)
        except:
            self.logger.warning("Failed to save pending data")

    def load(self):
        """Load any pending data to a file."""
        if not os.path.exists(self.pending_file):
            return True
        pending_data = []
        try:
            savefile = open(self.pending_file, 'r')
            pending_data = pickle.load(savefile)
            savefile.close()
        except Exception:
            e = sys.exc_info()[1]
            self.logger.warning("Failed to load pending data: %s" % e)
        for (pmetadata, pdata) in pending_data:
            # check that shutdown wasnt called early
            if self.terminate.isSet():
                return False

            try:
                while True:
                    try:
                        metadata = self.core.build_metadata(pmetadata)
                        break
                    except Bcfg2.Server.Plugins.Metadata.MetadataRuntimeError:
                        pass

                    self.terminate.wait(5)
                    if self.terminate.isSet():
                        return False

                self.work_queue.put_nowait((metadata,
                                            lxml.etree.XML(pdata,
                                                           parser=Bcfg2.Server.XMLParser)))
            except Full:
                self.logger.warning("Queue.Full: Failed to load queue data")
                break
            except lxml.etree.LxmlError:
                lxml_error = sys.exc_info()[1]
                self.logger.error("Unable to load save interaction: %s" % lxml_error)
            except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
                self.logger.error("Unable to load metadata for save interaction: %s" % pmetadata)
        try:
            os.unlink(self.pending_file)
        except:
            self.logger.error("Failed to unlink save file: %s" % self.pending_file)
        self.logger.info("Loaded pending %s data" % self.__class__.__name__)
        return True

    def run(self):
        if not self.load():
            return
        while not self.terminate.isSet() and self.work_queue != None:
            try:
                (xdata, client) = self.work_queue.get(block=True, timeout=2)
            except Empty:
                continue
            except Exception:
                e = sys.exc_info()[1]
                self.logger.error("ThreadedStatistics: %s" % e)
                continue
            self.handle_statistic(xdata, client)
        if self.work_queue != None and not self.work_queue.empty():
            self.save()

    def process_statistics(self, metadata, data):
        warned = False
        try:
            self.work_queue.put_nowait((metadata, copy.copy(data)))
            warned = False
        except Full:
            if not warned:
                self.logger.warning("%s: Queue is full.  Dropping interactions." % self.__class__.__name__)
            warned = True

    def handle_statistics(self, metadata, data):
        """Handle stats here."""
        pass


class PullSource(object):
    def GetExtra(self, client):
        return []

    def GetCurrentEntry(self, client, e_type, e_name):
        raise PluginExecutionError


class PullTarget(object):
    def AcceptChoices(self, entry, metadata):
        raise PluginExecutionError

    def AcceptPullData(self, specific, new_entry, verbose):
        """This is the null per-plugin implementation
        of bcfg2-admin pull."""
        raise PluginExecutionError


class Decision(object):
    """Signal decision handling capability."""
    def GetDecisions(self, metadata, mode):
        return []


class ValidationError(Exception):
    pass


class StructureValidator(object):
    """Validate/modify goal structures."""
    def validate_structures(self, metadata, structures):
        raise ValidationError("not implemented")


class GoalValidator(object):
    """Validate/modify configuration goals."""
    def validate_goals(self, metadata, goals):
        raise ValidationError("not implemented")


class Version(object):
    """Interact with various version control systems."""
    def get_revision(self):
        return []

    def commit_data(self, file_list, comment=None):
        pass


class ClientRunHooks(object):
    """ Provides hooks to interact with client runs """
    def start_client_run(self, metadata):
        pass

    def end_client_run(self, metadata):
        pass

    def end_statistics(self, metadata):
        pass

# the rest of the file contains classes for coherent file caching

class FileBacked(object):
    """This object caches file data in memory.
    HandleEvent is called whenever fam registers an event.
    Index can parse the data into member data as required.
    This object is meant to be used as a part of DirectoryBacked.
    """

    def __init__(self, name, fam=None):
        object.__init__(self)
        self.data = ''
        self.name = name
        self.fam = fam

    def HandleEvent(self, event=None):
        """Read file upon update."""
        if event and event.code2str() not in ['exists', 'changed', 'created']:
            return
        try:
            self.data = BUILTIN_FILE_TYPE(self.name).read()
            self.Index()
        except IOError:
            err = sys.exc_info()[1]
            logger.error("Failed to read file %s: %s" % (self.name, err))

    def Index(self):
        """Update local data structures based on current file state"""
        pass

    def __repr__(self):
        return "%s: %s" % (self.__class__.__name__, self.name)


class DirectoryBacked(object):
    """This object is a coherent cache for a filesystem hierarchy of files."""
    __child__ = FileBacked
    patterns = re.compile('.*')

    def __init__(self, data, fam):
        """Initialize the DirectoryBacked object.

        :param self: the object being initialized.
        :param data: the path to the data directory that will be
        monitored.
        :param fam: The FileMonitor object used to receive
        notifications of changes.
        """
        object.__init__(self)

        self.data = os.path.normpath(data)
        self.fam = fam

        # self.entries contains information about the files monitored
        # by this object.... The keys of the dict are the relative
        # paths to the files. The values are the objects (of type
        # __child__) that handle their contents.
        self.entries = {}

        # self.handles contains information about the directories
        # monitored by this object. The keys of the dict are the
        # values returned by the initial fam.AddMonitor() call (which
        # appear to be integers). The values are the relative paths of
        # the directories.
        self.handles = {}

        # Monitor everything in the plugin's directory
        self.add_directory_monitor('')

    def __getitem__(self, key):
        return self.entries[key]

    def __iter__(self):
        return iter(list(self.entries.items()))

    def add_directory_monitor(self, relative):
        """Add a new directory to FAM structures for monitoring.

        :param relative: Path name to monitor. This must be relative
        to the plugin's directory. An empty string value ("") will
        cause the plugin directory itself to be monitored.
        """
        dirpathname = os.path.join(self.data, relative)
        if relative not in self.handles.values():
            if not posixpath.isdir(dirpathname):
                logger.error("Failed to open directory %s" % (dirpathname))
                return
            reqid = self.fam.AddMonitor(dirpathname, self)
            self.handles[reqid] = relative

    def add_entry(self, relative, event):
        """Add a new file to our structures for monitoring.

        :param relative: Path name to monitor. This must be relative
        to the plugin's directory.
        :param event: File Monitor event that caused this entry to be
        added.
        """
        self.entries[relative] = self.__child__(os.path.join(self.data,
                                                             relative),
                                                self.fam)
        self.entries[relative].HandleEvent(event)

    def HandleEvent(self, event):
        """Handle FAM/Gamin events.

        This method is invoked by FAM/Gamin when it detects a change
        to a filesystem object we have requsted to be monitored.

        This method manages the lifecycle of events related to the
        monitored objects, adding them to our indiciess and creating
        objects of type __child__ that actually do the domain-specific
        processing. When appropriate, it propogates events those
        objects by invoking their HandleEvent in turn.
        """
        action = event.code2str()

        # Clean up the absolute path names passed in
        event.filename = os.path.normpath(event.filename)
        if event.filename.startswith(self.data):
            event.filename = event.filename[len(self.data)+1:]

        # Exclude events for actions we don't care about
        if action == 'endExist':
            return

        if event.requestID not in self.handles:
            logger.warn("Got %s event with unknown handle (%s) for %s" %
                        (action, event.requestID, event.filename))
            return

        # Calculate the absolute and relative paths this event refers to
        abspath = os.path.join(self.data, self.handles[event.requestID],
                               event.filename)
        relpath = os.path.join(self.handles[event.requestID], event.filename)

        if action == 'deleted':
            for key in self.entries.keys():
                if key.startswith(relpath):
                    del self.entries[key]
            # We remove values from self.entries, but not
            # self.handles, because the FileMonitor doesn't stop
            # watching a directory just because it gets deleted. If it
            # is recreated, we will start getting notifications for it
            # again without having to add a new monitor.
        elif posixpath.isdir(abspath):
            # Deal with events for directories
            if action in ['exists', 'created']:
                self.add_directory_monitor(relpath)
            elif action == 'changed':
                if relpath in self.entries:
                    # Ownerships, permissions or timestamps changed on
                    # the directory. None of these should affect the
                    # contents of the files, though it could change
                    # our ability to access them.
                    #
                    # It seems like the right thing to do is to cancel
                    # monitoring the directory and then begin
                    # monitoring it again. But the current FileMonitor
                    # class doesn't support canceling, so at least let
                    # the user know that a restart might be a good
                    # idea.
                    logger.warn("Directory properties for %s changed, please " +
                                " consider restarting the server" % (abspath))
                else:
                    # Got a "changed" event for a directory that we
                    # didn't know about. Go ahead and treat it like a
                    # "created" event, but log a warning, because this
                    # is unexpected.
                    logger.warn("Got %s event for unexpected dir %s" %
                                (action, abspath))
                    self.add_directory_monitor(relpath)
            else:
                logger.warn("Got unknown dir event %s %s %s" %
                            (event.requestID, event.code2str(), abspath))
        else:
            if action in ['exists', 'created']:
                self.add_entry(relpath, event)
            elif action == 'changed':
                if relpath in self.entries:
                    self.entries[relpath].HandleEvent(event)
                else:
                    # Got a "changed" event for a file that we didn't
                    # know about. Go ahead and treat it like a
                    # "created" event, but log a warning, because this
                    # is unexpected.
                    logger.warn("Got %s event for unexpected file %s" %
                                (action,
                                 abspath))
                    self.add_entry(relpath, event)
            else:
                logger.warn("Got unknown file event %s %s %s" %
                            (event.requestID, event.code2str(), abspath))


class XMLFileBacked(FileBacked):
    """
    This object is a coherent cache for an XML file to be used as a
    part of DirectoryBacked.
    """
    __identifier__ = 'name'

    def __init__(self, filename, fam=None, should_monitor=False):
        FileBacked.__init__(self, filename)
        self.label = ""
        self.entries = []
        self.extras = []
        self.fam = fam
        self.should_monitor = should_monitor
        if fam and should_monitor:
            self.fam.AddMonitor(filename, self)

    def _follow_xincludes(self, fname=None, xdata=None):
        ''' follow xincludes, adding included files to self.extras '''
        if xdata is None:
            if fname is None:
                xdata = self.xdata.getroottree()
            else:
                xdata = lxml.etree.parse(fname)
        included = [el for el in xdata.findall('//%sinclude' %
                                               Bcfg2.Server.XI_NAMESPACE)]
        for el in included:
            name = el.get("href")
            if name not in self.extras:
                if name.startswith("/"):
                    fpath = name
                else:
                    fpath = os.path.join(os.path.dirname(self.name), name)
                if os.path.exists(fpath):
                    self._follow_xincludes(fname=fpath)
                    self.add_monitor(fpath, name)
                else:
                    msg = "%s: %s does not exist, skipping" % (self.name, name)
                    if el.findall('./%sfallback' % Bcfg2.Server.XI_NAMESPACE):
                        self.logger.debug(msg)
                    else:
                        self.logger.warning(msg)

    def Index(self):
        """Build local data structures."""
        try:
            self.xdata = lxml.etree.XML(self.data, base_url=self.name,
                                        parser=Bcfg2.Server.XMLParser)
        except lxml.etree.XMLSyntaxError:
            err = sys.exc_info()[1]
            logger.error("Failed to parse %s: %s" % (self.name, err))
            raise Bcfg2.Server.Plugin.PluginInitError

        self._follow_xincludes()
        if self.extras:
            try:
                self.xdata.getroottree().xinclude()
            except lxml.etree.XIncludeError:
                err = sys.exc_info()[1]
                logger.error("XInclude failed on %s: %s" % (self.name, err))

        self.entries = self.xdata.getchildren()
        if self.__identifier__ is not None:
            self.label = self.xdata.attrib[self.__identifier__]

    def add_monitor(self, fpath, fname):
        self.extras.append(fname)
        if self.fam and self.should_monitor:
            self.fam.AddMonitor(fpath, self)

    def __iter__(self):
        return iter(self.entries)

    def __str__(self):
        return "%s at %s" % (self.__class__.__name__, self.name)


class StructFile(XMLFileBacked):
    """This file contains a set of structure file formatting logic."""
    __identifier__ = None

    def _include_element(self, item, metadata):
        """ determine if an XML element matches the metadata """
        negate = item.get('negate', 'false').lower() == 'true'
        if item.tag == 'Group':
            return ((negate and item.get('name') not in metadata.groups) or
                    (not negate and item.get('name') in metadata.groups))
        elif item.tag == 'Client':
            return ((negate and item.get('name') != metadata.hostname) or
                    (not negate and item.get('name') == metadata.hostname))
        elif isinstance(item, lxml.etree._Comment):
            return False
        else:
            return True

    def _match(self, item, metadata):
        """ recursive helper for Match() """
        if self._include_element(item, metadata):
            if item.tag == 'Group' or item.tag == 'Client':
                rv = []
                if self._include_element(item, metadata):
                    for child in item.iterchildren():
                        rv.extend(self._match(child, metadata))
                return rv
            else:
                rv = copy.copy(item)
                for child in rv.iterchildren():
                    rv.remove(child)
                for child in item.iterchildren():
                    rv.extend(self._match(child, metadata))
                return [rv]
        else:
            return []

    def Match(self, metadata):
        """Return matching fragments of independent."""
        rv = []
        for child in self.entries:
            rv.extend(self._match(child, metadata))
        return rv

    def _xml_match(self, item, metadata):
        """ recursive helper for XMLMatch """
        if self._include_element(item, metadata):
            if item.tag == 'Group' or item.tag == 'Client':
                for child in item.iterchildren():
                    item.remove(child)
                    item.getparent().append(child)
                    self._xml_match(child, metadata)
                item.getparent().remove(item)
            else:
                for child in item.iterchildren():
                    self._xml_match(child, metadata)
        else:
            item.getparent().remove(item)

    def XMLMatch(self, metadata):
        """ Return a rebuilt XML document that only contains the
        matching portions """
        rv = copy.deepcopy(self.xdata)
        for child in rv.iterchildren():
            self._xml_match(child, metadata)
        return rv


class INode:
    """
    LNodes provide lists of things available at a particular
    group intersection.
    """
    raw = {'Client': "lambda m, e:'%(name)s' == m.hostname and predicate(m, e)",
           'Group': "lambda m, e:'%(name)s' in m.groups and predicate(m, e)"}
    nraw = {'Client': "lambda m, e:'%(name)s' != m.hostname and predicate(m, e)",
            'Group': "lambda m, e:'%(name)s' not in m.groups and predicate(m, e)"}
    containers = ['Group', 'Client']
    ignore = []

    def __init__(self, data, idict, parent=None):
        self.data = data
        self.contents = {}
        if parent == None:
            self.predicate = lambda m, d: True
        else:
            predicate = parent.predicate
            if data.get('negate', 'false') in ['true', 'True']:
                psrc = self.nraw
            else:
                psrc = self.raw
            if data.tag in list(psrc.keys()):
                self.predicate = eval(psrc[data.tag] %
                                      {'name': data.get('name')},
                                      {'predicate': predicate})
            else:
                raise Exception
        mytype = self.__class__
        self.children = []
        for item in data.getchildren():
            if item.tag in self.ignore:
                continue
            elif item.tag in self.containers:
                self.children.append(mytype(item, idict, self))
            else:
                try:
                    self.contents[item.tag][item.get('name')] = item.attrib
                except KeyError:
                    self.contents[item.tag] = {item.get('name'): item.attrib}
                if item.text:
                    self.contents[item.tag]['__text__'] = item.text
                try:
                    idict[item.tag].append(item.get('name'))
                except KeyError:
                    idict[item.tag] = [item.get('name')]

    def Match(self, metadata, data, entry=lxml.etree.Element("None")):
        """Return a dictionary of package mappings."""
        if self.predicate(metadata, entry):
            for key in self.contents:
                try:
                    data[key].update(self.contents[key])
                except:
                    data[key] = {}
                    data[key].update(self.contents[key])
            for child in self.children:
                child.Match(metadata, data, entry=entry)


class InfoNode (INode):
    """ INode implementation that includes <Path> tags """
    raw = {'Client': "lambda m, e:'%(name)s' == m.hostname and predicate(m, e)",
           'Group': "lambda m, e:'%(name)s' in m.groups and predicate(m, e)",
           'Path': "lambda m, e:('%(name)s' == e.get('name') or '%(name)s' == e.get('realname')) and predicate(m, e)"}
    nraw = {'Client': "lambda m, e:'%(name)s' != m.hostname and predicate(m, e)",
            'Group': "lambda m, e:'%(name)s' not in m.groups and predicate(m, e)",
            'Path': "lambda m, e:('%(name)s' != e.get('name') and '%(name)s' != e.get('realname')) and predicate(m, e)"}
    containers = ['Group', 'Client', 'Path']


class XMLSrc(XMLFileBacked):
    """XMLSrc files contain a LNode hierarchy that returns matching entries."""
    __node__ = INode
    __cacheobj__ = dict

    def __init__(self, filename, fam=None, should_monitor=False, noprio=False):
        XMLFileBacked.__init__(self, filename, fam, should_monitor)
        self.items = {}
        self.cache = None
        self.pnode = None
        self.priority = -1
        self.noprio = noprio

    def HandleEvent(self, _=None):
        """Read file upon update."""
        try:
            data = BUILTIN_FILE_TYPE(self.name).read()
        except IOError:
            logger.error("Failed to read file %s" % (self.name))
            return
        self.items = {}
        try:
            xdata = lxml.etree.XML(data, parser=Bcfg2.Server.XMLParser)
        except lxml.etree.XMLSyntaxError:
            logger.error("Failed to parse file %s" % (self.name))
            return
        self.pnode = self.__node__(xdata, self.items)
        self.cache = None
        try:
            self.priority = int(xdata.get('priority'))
        except (ValueError, TypeError):
            if not self.noprio:
                logger.error("Got bogus priority %s for file %s" %
                             (xdata.get('priority'), self.name))
        del xdata, data

    def Cache(self, metadata):
        """Build a package dict for a given host."""
        if self.cache == None or self.cache[0] != metadata:
            cache = (metadata, self.__cacheobj__())
            if self.pnode == None:
                logger.error("Cache method called early for %s; forcing data load" % (self.name))
                self.HandleEvent()
                return
            self.pnode.Match(metadata, cache[1])
            self.cache = cache

    def __str__(self):
        return str(self.items)


class InfoXML(XMLSrc):
    __node__ = InfoNode


class XMLDirectoryBacked(DirectoryBacked):
    """Directorybacked for *.xml."""
    patterns = re.compile('.*\.xml')
    __child__ = XMLFileBacked


class PrioDir(Plugin, Generator, XMLDirectoryBacked):
    """This is a generator that handles package assignments."""
    name = 'PrioDir'
    __child__ = XMLSrc

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        Generator.__init__(self)
        try:
            XMLDirectoryBacked.__init__(self, self.data, self.core.fam)
        except OSError:
            self.logger.error("Failed to load %s indices" % (self.name))
            raise PluginInitError

    def HandleEvent(self, event):
        """Handle events and update dispatch table."""
        XMLDirectoryBacked.HandleEvent(self, event)
        self.Entries = {}
        for src in list(self.entries.values()):
            for itype, children in list(src.items.items()):
                for child in children:
                    try:
                        self.Entries[itype][child] = self.BindEntry
                    except KeyError:
                        self.Entries[itype] = {child: self.BindEntry}

    def _matches(self, entry, metadata, rules):
        return entry.get('name') in rules

    def BindEntry(self, entry, metadata):
        attrs = self.get_attrs(entry, metadata)
        for key, val in list(attrs.items()):
            entry.attrib[key] = val

    def get_attrs(self, entry, metadata):
        """ get a list of attributes to add to the entry during the bind """
        for src in self.entries.values():
            src.Cache(metadata)

        matching = [src for src in list(self.entries.values())
                    if (src.cache and
                        entry.tag in src.cache[1] and
                        self._matches(entry, metadata,
                                      src.cache[1][entry.tag]))]
        if len(matching) == 0:
            raise PluginExecutionError('No matching source for entry when retrieving attributes for %s(%s)' % (entry.tag, entry.attrib.get('name')))
        elif len(matching) == 1:
            index = 0
        else:
            prio = [int(src.priority) for src in matching]
            if prio.count(max(prio)) > 1:
                self.logger.error("Found conflicting sources with "
                                  "same priority for %s, %s %s" %
                                  (metadata.hostname,
                                   entry.tag.lower(), entry.get('name')))
                self.logger.error([item.name for item in matching])
                self.logger.error("Priority was %s" % max(prio))
                raise PluginExecutionError
            index = prio.index(max(prio))

        for rname in list(matching[index].cache[1][entry.tag].keys()):
            if self._matches(entry, metadata, [rname]):
                data = matching[index].cache[1][entry.tag][rname]
                break
        else:
            # Fall back on __getitem__. Required if override used
            data = matching[index].cache[1][entry.tag][entry.get('name')]
        if '__text__' in data:
            entry.text = data['__text__']
        if '__children__' in data:
            [entry.append(copy.copy(item)) for item in data['__children__']]

        return dict([(key, data[key])
                     for key in list(data.keys())
                     if not key.startswith('__')])


# new unified EntrySet backend
class SpecificityError(Exception):
    """Thrown in case of filename parse failure."""
    pass


class Specificity:

    def __init__(self, all=False, group=False, hostname=False, prio=0, delta=False):
        self.hostname = hostname
        self.all = all
        self.group = group
        self.prio = prio
        self.delta = delta

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def matches(self, metadata):
        return self.all or \
               self.hostname == metadata.hostname or \
               self.group in metadata.groups

    def __cmp__(self, other):
        """Sort most to least specific."""
        if self.all:
            return 1
        if self.group:
            if other.hostname:
                return 1
            if other.group and other.prio > self.prio:
                return 1
            if other.group and other.prio == self.prio:
                return 0
        return -1

    def more_specific(self, other):
        """Test if self is more specific than other."""
        if self.all:
            True
        elif self.group:
            if other.hostname:
                return True
            elif other.group and other.prio > self.prio:
                return True
        return False


class SpecificData(object):
    def __init__(self, name, specific, encoding):
        self.name = name
        self.specific = specific

    def handle_event(self, event):
        if event.code2str() == 'deleted':
            return
        try:
            self.data = open(self.name).read()
        except UnicodeDecodeError:
            self.data = open(self.name, mode='rb').read()
        except:
            logger.error("Failed to read file %s" % self.name)


class EntrySet(Debuggable):
    """Entry sets deal with the host- and group-specific entries."""
    ignore = re.compile("^(\.#.*|.*~|\\..*\\.(sw[px])|.*\\.genshi_include)$")

    def __init__(self, basename, path, entry_type, encoding):
        Debuggable.__init__(self, name=basename)
        self.path = path
        self.entry_type = entry_type
        self.entries = {}
        self.metadata = default_file_metadata.copy()
        self.infoxml = None
        self.encoding = encoding
        pattern = '(.*/)?%s(\.((H_(?P<hostname>\S+))|' % basename
        pattern += '(G(?P<prio>\d+)_(?P<group>\S+))))?$'
        self.specific = re.compile(pattern)

    def sort_by_specific(self, one, other):
        return cmp(one.specific, other.specific)

    def get_matching(self, metadata):
        return [item for item in list(self.entries.values())
                if item.specific.matches(metadata)]

    def best_matching(self, metadata, matching=None):
        """ Return the appropriate interpreted template from the set of
        available templates. """
        if matching is None:
            matching = self.get_matching(metadata)

        hspec = [ent for ent in matching if ent.specific.hostname]
        if hspec:
            return hspec[0]

        gspec = [ent for ent in matching if ent.specific.group]
        if gspec:
            gspec.sort(self.group_sortfunc)
            return gspec[-1]

        aspec = [ent for ent in matching if ent.specific.all]
        if aspec:
            return aspec[0]

        raise PluginExecutionError

    def handle_event(self, event):
        """Handle FAM events for the TemplateSet."""
        action = event.code2str()

        if event.filename in ['info', 'info.xml', ':info']:
            if action in ['exists', 'created', 'changed']:
                self.update_metadata(event)
            elif action == 'deleted':
                self.reset_metadata(event)
            return

        if action in ['exists', 'created']:
            self.entry_init(event)
        else:
            if event.filename not in self.entries:
                logger.warning("Got %s event for unknown file %s" %
                               (action, event.filename))
                if action == 'changed':
                    # received a bogus changed event; warn, but treat
                    # it like a created event
                    self.entry_init(event)
                return
            if action == 'changed':
                self.entries[event.filename].handle_event(event)
            elif action == 'deleted':
                del self.entries[event.filename]

    def entry_init(self, event, entry_type=None, specific=None):
        """Handle template and info file creation."""
        if entry_type is None:
            entry_type = self.entry_type

        if event.filename in self.entries:
            logger.warn("Got duplicate add for %s" % event.filename)
        else:
            fpath = os.path.join(self.path, event.filename)
            try:
                spec = self.specificity_from_filename(event.filename,
                                                      specific=specific)
            except SpecificityError:
                if not self.ignore.match(event.filename):
                    logger.error("Could not process filename %s; ignoring" %
                                 fpath)
                return
            self.entries[event.filename] = entry_type(fpath, spec,
                                                      self.encoding)
        self.entries[event.filename].handle_event(event)

    def specificity_from_filename(self, fname, specific=None):
        """Construct a specificity instance from a filename and regex."""
        if specific is None:
            specific = self.specific
        data = specific.match(fname)
        if not data:
            raise SpecificityError(fname)
        kwargs = {}
        if data.group('hostname'):
            kwargs['hostname'] = data.group('hostname')
        elif data.group('group'):
            kwargs['group'] = data.group('group')
            kwargs['prio'] = int(data.group('prio'))
        else:
            kwargs['all'] = True
        if 'delta' in data.groupdict():
            kwargs['delta'] = data.group('delta')
        return Specificity(**kwargs)

    def update_metadata(self, event):
        """Process info and info.xml files for the templates."""
        fpath = os.path.join(self.path, event.filename)
        if event.filename == 'info.xml':
            if not self.infoxml:
                self.infoxml = InfoXML(fpath, True)
            self.infoxml.HandleEvent(event)
        elif event.filename in [':info', 'info']:
            for line in open(fpath).readlines():
                match = info_regex.match(line)
                if not match:
                    logger.warning("Failed to match line in %s: %s" % (fpath,
                                                                       line))
                    continue
                else:
                    mgd = match.groupdict()
                    for key, value in list(mgd.items()):
                        if value:
                            self.metadata[key] = value
                    if len(self.metadata['perms']) == 3:
                        self.metadata['perms'] = "0%s" % \
                                                 (self.metadata['perms'])

    def reset_metadata(self, event):
        """Reset metadata to defaults if info or info.xml removed."""
        if event.filename == 'info.xml':
            self.infoxml = None
        elif event.filename in [':info', 'info']:
            self.metadata = default_file_metadata.copy()

    def group_sortfunc(self, x, y):
        """sort groups by their priority"""
        return cmp(x.specific.prio, y.specific.prio)

    def bind_info_to_entry(self, entry, metadata):
        bind_info(entry, metadata, infoxml=self.infoxml, default=self.metadata)

    def bind_entry(self, entry, metadata):
        """Return the appropriate interpreted template from the set of available templates."""
        self.bind_info_to_entry(entry, metadata)
        return self.best_matching(metadata).bind_entry(entry, metadata)


class GroupSpool(Plugin, Generator):
    """Unified interface for handling group-specific data (e.g. .G## files)."""
    name = 'GroupSpool'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    filename_pattern = ""
    es_child_cls = object
    es_cls = EntrySet
    entry_type = 'Path'

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        Generator.__init__(self)
        if self.data[-1] == '/':
            self.data = self.data[:-1]
        self.Entries[self.entry_type] = {}
        self.entries = {}
        self.handles = {}
        self.AddDirectoryMonitor('')
        self.encoding = core.encoding

    def add_entry(self, event):
        epath = self.event_path(event)
        ident = self.event_id(event)
        if posixpath.isdir(epath):
            self.AddDirectoryMonitor(epath[len(self.data):])
        if ident not in self.entries and posixpath.isfile(epath):
            dirpath = "".join([self.data, ident])
            self.entries[ident] = self.es_cls(self.filename_pattern,
                                              dirpath,
                                              self.es_child_cls,
                                              self.encoding)
            self.Entries[self.entry_type][ident] = \
                self.entries[ident].bind_entry
        if not posixpath.isdir(epath):
            # do not pass through directory events
            self.entries[ident].handle_event(event)

    def event_path(self, event):
        return "".join([self.data, self.handles[event.requestID],
                        event.filename])

    def event_id(self, event):
        epath = self.event_path(event)
        if posixpath.isdir(epath):
            return self.handles[event.requestID] + event.filename
        else:
            return self.handles[event.requestID][:-1]

    def toggle_debug(self):
        for entry in self.entries.values():
            if hasattr(entry, "toggle_debug"):
                entry.toggle_debug()
        return Plugin.toggle_debug()

    def HandleEvent(self, event):
        """Unified FAM event handler for GroupSpool."""
        action = event.code2str()
        if event.filename[0] == '/':
            return
        ident = self.event_id(event)

        if action in ['exists', 'created']:
            self.add_entry(event)
        if action == 'changed':
            if ident in self.entries:
                self.entries[ident].handle_event(event)
            else:
                # got a changed event for a file we didn't know
                # about. go ahead and process this as a 'created', but
                # warn
                self.logger.warning("Got changed event for unknown file %s" %
                                    ident)
                self.add_entry(event)
        elif action == 'deleted':
            fbase = self.handles[event.requestID] + event.filename
            if fbase in self.entries:
                # a directory was deleted
                del self.entries[fbase]
                del self.Entries[self.entry_type][fbase]
            elif ident in self.entries:
                self.entries[ident].handle_event(event)
            elif ident not in self.entries:
                self.logger.warning("Got deleted event for unknown file %s" %
                                    ident)

    def AddDirectoryMonitor(self, relative):
        """Add new directory to FAM structures."""
        if not relative.endswith('/'):
            relative += '/'
        name = self.data + relative
        if relative not in list(self.handles.values()):
            if not posixpath.isdir(name):
                self.logger.error("Failed to open directory %s" % name)
                return
            reqid = self.core.fam.AddMonitor(name, self)
            self.handles[reqid] = relative
