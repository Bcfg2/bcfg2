""" Helper classes for Bcfg2 server plugins """

import os
import re
import sys
import copy
import time
import glob
import logging
import operator
import lxml.etree
import Bcfg2.Server
import Bcfg2.Options
import Bcfg2.Statistics
from Bcfg2.Compat import CmpMixin, wraps
from Bcfg2.Server.Plugin.base import Debuggable, Plugin
from Bcfg2.Server.Plugin.interfaces import Generator
from Bcfg2.Server.Plugin.exceptions import SpecificityError, \
    PluginExecutionError

try:
    import django  # pylint: disable=W0611
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

#: A dict containing default metadata for Path entries from bcfg2.conf
DEFAULT_FILE_METADATA = Bcfg2.Options.OptionParser(
    dict(configfile=Bcfg2.Options.CFILE,
         owner=Bcfg2.Options.MDATA_OWNER,
         group=Bcfg2.Options.MDATA_GROUP,
         mode=Bcfg2.Options.MDATA_MODE,
         secontext=Bcfg2.Options.MDATA_SECONTEXT,
         important=Bcfg2.Options.MDATA_IMPORTANT,
         paranoid=Bcfg2.Options.MDATA_PARANOID,
         sensitive=Bcfg2.Options.MDATA_SENSITIVE))
DEFAULT_FILE_METADATA.parse([Bcfg2.Options.CFILE.cmd, Bcfg2.Options.CFILE])
del DEFAULT_FILE_METADATA['args']
del DEFAULT_FILE_METADATA['configfile']

LOGGER = logging.getLogger(__name__)

#: a compiled regular expression for parsing info and :info files
INFO_REGEX = re.compile(r'owner:\s*(?P<owner>\S+)|' +
                        r'group:\s*(?P<group>\S+)|' +
                        r'mode:\s*(?P<mode>\w+)|' +
                        r'secontext:\s*(?P<secontext>\S+)|' +
                        r'paranoid:\s*(?P<paranoid>\S+)|' +
                        r'sensitive:\s*(?P<sensitive>\S+)|' +
                        r'encoding:\s*(?P<encoding>\S+)|' +
                        r'important:\s*(?P<important>\S+)|' +
                        r'mtime:\s*(?P<mtime>\w+)')


def bind_info(entry, metadata, infoxml=None, default=DEFAULT_FILE_METADATA):
    """ Bind the file metadata in the given
    :class:`Bcfg2.Server.Plugin.helpers.InfoXML` object to the given
    entry.

    :param entry: The abstract entry to bind the info to
    :type entry: lxml.etree._Element
    :param metadata: The client metadata to get info for
    :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
    :param infoxml: The info.xml file to pull file metadata from
    :type infoxml: Bcfg2.Server.Plugin.helpers.InfoXML
    :param default: Default metadata to supply when the info.xml file
                    does not include a particular attribute
    :type default: dict
    :returns: None
    :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginExecutionError`
    """
    for attr, val in list(default.items()):
        entry.set(attr, val)
    if infoxml:
        mdata = dict()
        infoxml.pnode.Match(metadata, mdata, entry=entry)
        if 'Info' not in mdata:
            msg = "Failed to set metadata for file %s" % entry.get('name')
            LOGGER.error(msg)
            raise PluginExecutionError(msg)
        for attr, val in list(mdata['Info'][None].items()):
            entry.set(attr, val)


class track_statistics(object):  # pylint: disable=C0103
    """ Decorator that tracks execution time for the given
    :class:`Plugin` method with :mod:`Bcfg2.Statistics` for reporting
    via ``bcfg2-admin perf`` """

    def __init__(self, name=None):
        """
        :param name: The name under which statistics for this function
                     will be tracked.  By default, the name will be
                     the name of the function concatenated with the
                     name of the class the function is a member of.
        :type name: string
        """
        # if this is None, it will be set later during __call_
        self.name = name

    def __call__(self, func):
        if self.name is None:
            self.name = func.__name__

        @wraps(func)
        def inner(obj, *args, **kwargs):
            """ The decorated function """
            name = "%s:%s" % (obj.__class__.__name__, self.name)

            start = time.time()
            try:
                return func(obj, *args, **kwargs)
            finally:
                Bcfg2.Statistics.stats.add_value(name, time.time() - start)

        return inner


class DatabaseBacked(Plugin):
    """ Provides capabilities for a plugin to read and write to a
    database.

    .. private-include: _use_db
    .. private-include: _must_lock
    """

    #: The option to look up in :attr:`section` to determine whether or
    #: not to use the database capabilities of this plugin.  The option
    #: is retrieved with
    #: :py:func:`ConfigParser.SafeConfigParser.getboolean`, and so must
    #: conform to the possible values that function can handle.
    option = "use_database"

    def _section(self):
        """ The section to look in for :attr:`DatabaseBacked.option`
        """
        return self.name.lower()
    section = property(_section)

    @property
    def _use_db(self):
        """ Whether or not this plugin is configured to use the
        database. """
        use_db = self.core.setup.cfp.getboolean(self.section,
                                                self.option,
                                                default=False)
        if use_db and HAS_DJANGO and self.core.database_available:
            return True
        elif not use_db:
            return False
        else:
            self.logger.error("%s is true but django not found" % self.option)
            return False

    @property
    def _must_lock(self):
        """ Whether or not the backend database must acquire a thread
        lock before writing, because it does not allow multiple
        threads to write."""
        engine = \
            self.core.setup.cfp.get(Bcfg2.Options.DB_ENGINE.cf[0],
                                    Bcfg2.Options.DB_ENGINE.cf[1],
                                    default=Bcfg2.Options.DB_ENGINE.default)
        return engine == 'sqlite3'

    @staticmethod
    def get_db_lock(func):
        """ Decorator to be used by a method of a
        :class:`DatabaseBacked` plugin that will update database data. """

        @wraps(func)
        def _acquire_and_run(self, *args, **kwargs):
            """ The decorated function """
            if self._must_lock:  # pylint: disable=W0212
                try:
                    self.core.db_write_lock.acquire()
                    rv = func(self, *args, **kwargs)
                finally:
                    self.core.db_write_lock.release()
            else:
                rv = func(self, *args, **kwargs)
            return rv
        return _acquire_and_run


class PluginDatabaseModel(object):
    """ A database model mixin that all database models used by
    :class:`Bcfg2.Server.Plugin.helpers.DatabaseBacked` plugins must
    inherit from.  This is just a mixin; models must also inherit from
    django.db.models.Model to be valid Django models."""

    class Meta:  # pylint: disable=C0111,W0232
        app_label = "Server"


class FileBacked(Debuggable):
    """ This object caches file data in memory. FileBacked objects are
    principally meant to be used as a part of
    :class:`Bcfg2.Server.Plugin.helpers.DirectoryBacked`. """

    def __init__(self, name, fam=None):
        """
        :param name: The full path to the file to cache and monitor
        :type name: string
        :param fam: The FAM object used to receive notifications of
                    changes
        :type fam: Bcfg2.Server.FileMonitor.FileMonitor
        """
        Debuggable.__init__(self)

        #: A string containing the raw data in this file
        self.data = ''

        #: The full path to the file
        self.name = name

        #: The FAM object used to receive notifications of changes
        self.fam = fam

    def HandleEvent(self, event=None):
        """ HandleEvent is called whenever the FAM registers an event.

        :param event: The event object
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        if event and event.code2str() not in ['exists', 'changed', 'created']:
            return
        try:
            self.data = open(self.name).read()
            self.Index()
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Failed to read file %s: %s" % (self.name, err))
        except:
            err = sys.exc_info()[1]
            self.logger.error("Failed to parse file %s: %s" % (self.name, err))

    def Index(self):
        """ Index() is called by :func:`HandleEvent` every time the
        data changes, and parses the data into usable data as
        required."""
        pass

    def __repr__(self):
        return "%s: %s" % (self.__class__.__name__, self.name)


class DirectoryBacked(Debuggable):
    """ DirectoryBacked objects represent a directory that contains
    files, represented by objects of the type listed in
    :attr:`__child__`, and other directories recursively.  It monitors
    for new files and directories to be added, and creates new objects
    as required to track those."""

    #: The type of child objects to create for files contained within
    #: the directory that is tracked.  Default is
    #: :class:`Bcfg2.Server.Plugin.helpers.FileBacked`
    __child__ = FileBacked

    #: Only track and include files whose names (not paths) match this
    #: compiled regex.
    patterns = re.compile('.*')

    #: Preemptively ignore files whose names (not paths) match this
    #: compiled regex.  ``ignore`` can be set to ``None`` to ignore no
    #: files.  If a file is encountered that does not match
    #: :attr:`patterns` or ``ignore``, then a warning will be produced.
    ignore = None

    def __init__(self, data, fam):
        """
        :param data: The path to the data directory that will be
                     monitored
        :type data: string
        :param fam: The FAM object used to receive notifications of
                    changes
        :type fam: Bcfg2.Server.FileMonitor.FileMonitor

        .. -----
        .. autoattribute:: __child__
        """
        Debuggable.__init__(self)

        self.data = os.path.normpath(data)
        self.fam = fam

        #: self.entries contains information about the files monitored
        #: by this object. The keys of the dict are the relative
        #: paths to the files. The values are the objects (of type
        #: :attr:`__child__`) that handle their contents.
        self.entries = {}

        #: self.handles contains information about the directories
        #: monitored by this object. The keys of the dict are the
        #: values returned by the initial fam.AddMonitor() call (which
        #: appear to be integers). The values are the relative paths of
        #: the directories.
        self.handles = {}

        # Monitor everything in the plugin's directory
        if not os.path.exists(self.data):
            self.logger.warning("%s does not exist, creating" % self.data)
            os.makedirs(self.data)
        self.add_directory_monitor('')

    def set_debug(self, debug):
        for entry in self.entries.values():
            if isinstance(entry, Debuggable):
                entry.set_debug(debug)
        return Debuggable.set_debug(self, debug)

    def __getitem__(self, key):
        return self.entries[key]

    def __len__(self):
        return len(self.entries)

    def __delitem__(self, key):
        del self.entries[key]

    def __setitem__(self, key, val):
        self.entries[key] = val

    def __iter__(self):
        return iter(list(self.entries.items()))

    def add_directory_monitor(self, relative):
        """ Add a new directory to the FAM for monitoring.

        :param relative: Path name to monitor. This must be relative
                         to the plugin's directory. An empty string
                         value ("") will cause the plugin directory
                         itself to be monitored.
        :type relative: string
        :returns: None
        """
        dirpathname = os.path.join(self.data, relative)
        if relative not in self.handles.values():
            if not os.path.isdir(dirpathname):
                self.logger.error("%s is not a directory" % dirpathname)
                return
            reqid = self.fam.AddMonitor(dirpathname, self)
            self.handles[reqid] = relative

    def add_entry(self, relative, event):
        """ Add a new file to our tracked entries, and to our FAM for
        monitoring.

        :param relative: Path name to monitor. This must be relative
                         to the plugin's directory.
        :type relative: string:
        :param event: FAM event that caused this entry to be added.
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        self.entries[relative] = self.__child__(os.path.join(self.data,
                                                             relative),
                                                self.fam)
        self.entries[relative].HandleEvent(event)

    def HandleEvent(self, event):  # pylint: disable=R0912
        """ Handle FAM events.

        This method is invoked by the FAM when it detects a change to
        a filesystem object we have requsted to be monitored.

        This method manages the lifecycle of events related to the
        monitored objects, adding them to our list of entries and
        creating objects of type :attr:`__child__` that actually do
        the domain-specific processing. When appropriate, it
        propogates events those objects by invoking their HandleEvent
        method in turn.

        :param event: FAM event that caused this entry to be added.
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        action = event.code2str()

        # Exclude events for actions we don't care about
        if action == 'endExist':
            return

        if event.requestID not in self.handles:
            self.logger.warn("Got %s event with unknown handle (%s) for %s" %
                             (action, event.requestID, event.filename))
            return

        # Clean up path names
        event.filename = os.path.normpath(event.filename)
        if event.filename.startswith(self.data):
            # the first event we get is on the data directory itself
            event.filename = event.filename[len(self.data) + 1:]

        if self.ignore and self.ignore.search(event.filename):
            self.logger.debug("Ignoring event %s" % event.filename)
            return

        # Calculate the absolute and relative paths this event refers to
        abspath = os.path.join(self.data, self.handles[event.requestID],
                               event.filename)
        relpath = os.path.join(self.handles[event.requestID],
                               event.filename).lstrip('/')

        if action == 'deleted':
            for key in list(self.entries.keys()):
                if key.startswith(relpath):
                    del self.entries[key]
            # We remove values from self.entries, but not
            # self.handles, because the FileMonitor doesn't stop
            # watching a directory just because it gets deleted. If it
            # is recreated, we will start getting notifications for it
            # again without having to add a new monitor.
        elif os.path.isdir(abspath):
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
                    self.logger.warn("Directory properties for %s changed, "
                                     "please consider restarting the server" %
                                     abspath)
                else:
                    # Got a "changed" event for a directory that we
                    # didn't know about. Go ahead and treat it like a
                    # "created" event, but log a warning, because this
                    # is unexpected.
                    self.logger.warn("Got %s event for unexpected dir %s" %
                                     (action, abspath))
                    self.add_directory_monitor(relpath)
            else:
                self.logger.warn("Got unknown dir event %s %s %s" %
                                 (event.requestID, event.code2str(), abspath))
        elif self.patterns.search(event.filename):
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
                    self.logger.warn("Got %s event for unexpected file %s" %
                                     (action, abspath))
                    self.add_entry(relpath, event)
            else:
                self.logger.warn("Got unknown file event %s %s %s" %
                                 (event.requestID, event.code2str(), abspath))
        else:
            self.logger.warn("Could not process filename %s; ignoring" %
                             event.filename)


class XMLFileBacked(FileBacked):
    """ This object parses and caches XML file data in memory.  It can
    be used as a standalone object or as a part of
    :class:`Bcfg2.Server.Plugin.helpers.XMLDirectoryBacked`
    """

    #: If ``__identifier__`` is set, then a top-level tag with the
    #: specified name will be required on the file being cached.  Its
    #: value will be available as :attr:`label`.  To disable this
    #: behavior, set ``__identifier__`` to ``None``.
    __identifier__ = 'name'

    #: If ``create`` is set, then it overrides the ``create`` argument
    #: to the constructor.
    create = None

    def __init__(self, filename, fam=None, should_monitor=False, create=None):
        """
        :param filename: The full path to the file to cache and monitor
        :type filename: string
        :param fam: The FAM object used to receive notifications of
                    changes
        :type fam: Bcfg2.Server.FileMonitor.FileMonitor
        :param should_monitor: Whether or not to monitor this file for
                               changes. It may be useful to disable
                               monitoring when, for instance, the file
                               is monitored by another object (e.g.,
                               an
                               :class:`Bcfg2.Server.Plugin.helpers.XMLDirectoryBacked`
                               object).
        :type should_monitor: bool
        :param create: Create the file if it doesn't exist.
                       ``create`` can be either an
                       :class:`lxml.etree._Element` object, which will
                       be used as initial content, or a string, which
                       will be used as the name of the (empty) tag
                       that will be the initial content of the file.
        :type create: lxml.etree._Element or string

        .. -----
        .. autoattribute:: __identifier__
        """
        FileBacked.__init__(self, filename, fam=fam)

        #: The raw XML data contained in the file as an
        #: :class:`lxml.etree.ElementTree` object, with XIncludes
        #: processed.
        self.xdata = None

        #: The label of this file.  This is determined from the
        #: top-level tag in the file, which must have an attribute
        #: specified by :attr:`__identifier__`.
        self.label = ""

        #: All entries in this file.  By default, all immediate
        #: children of the top-level XML tag.
        self.entries = []

        #: "Extra" files included in this file by XInclude.
        self.extras = []

        #: Extra FAM monitors set by this object for files included by
        #: XInclude.
        self.extra_monitors = []

        if ((create is not None or self.create not in [None, False]) and
            not os.path.exists(self.name)):
            toptag = create or self.create
            self.logger.warning("%s does not exist, creating" % self.name)
            if hasattr(toptag, "getroottree"):
                el = toptag
            else:
                el = lxml.etree.Element(toptag)
            el.getroottree().write(self.name, xml_declaration=False,
                                   pretty_print=True)

        #: Whether or not to monitor this file for changes.
        self.should_monitor = should_monitor
        if fam and should_monitor:
            self.fam.AddMonitor(filename, self)

    def _follow_xincludes(self, fname=None, xdata=None):
        """ follow xincludes, adding included files to self.extras """
        xinclude = '%sinclude' % Bcfg2.Server.XI_NAMESPACE

        if xdata is None:
            if fname is None:
                xdata = self.xdata.getroottree()
            else:
                xdata = lxml.etree.parse(fname)
        included = [el for el in xdata.findall('//' + xinclude)]
        for el in included:
            name = el.get("href")
            if name.startswith("/"):
                fpath = name
            else:
                if fname:
                    rel = fname
                else:
                    rel = self.name
                fpath = os.path.join(os.path.dirname(rel), name)

            # expand globs in xinclude, a bcfg2-specific extension
            extras = glob.glob(fpath)
            if not extras:
                msg = "%s: %s does not exist, skipping" % (self.name, name)
                if el.findall('./%sfallback' % Bcfg2.Server.XI_NAMESPACE):
                    self.logger.debug(msg)
                else:
                    self.logger.warning(msg)

            parent = el.getparent()
            parent.remove(el)
            for extra in extras:
                if extra != self.name and extra not in self.extras:
                    self.extras.append(extra)
                    lxml.etree.SubElement(parent, xinclude, href=extra)
                    self._follow_xincludes(fname=extra)
                    if extra not in self.extra_monitors:
                        self.add_monitor(extra)

    def Index(self):
        self.xdata = lxml.etree.XML(self.data, base_url=self.name,
                                    parser=Bcfg2.Server.XMLParser)
        self.extras = []
        self._follow_xincludes()
        if self.extras:
            try:
                self.xdata.getroottree().xinclude()
            except lxml.etree.XIncludeError:
                err = sys.exc_info()[1]
                self.logger.error("XInclude failed on %s: %s" % (self.name,
                                                                 err))

        self.entries = self.xdata.getchildren()
        if self.__identifier__ is not None:
            self.label = self.xdata.attrib[self.__identifier__]
    Index.__doc__ = FileBacked.Index.__doc__

    def add_monitor(self, fpath):
        """ Add a FAM monitor to a file that has been XIncluded.  This
        is only done if the constructor got both a ``fam`` object and
        ``should_monitor`` set to True.

        :param fpath: The full path to the file to monitor
        :type fpath: string
        :returns: None
        """
        self.extra_monitors.append(fpath)
        if self.fam and self.should_monitor:
            self.fam.AddMonitor(fpath, self)

    def __iter__(self):
        return iter(self.entries)

    def __str__(self):
        return "%s at %s" % (self.__class__.__name__, self.name)


class StructFile(XMLFileBacked):
    """ StructFiles are XML files that contain a set of structure file
    formatting logic for handling ``<Group>`` and ``<Client>``
    tags. """

    #: If ``__identifier__`` is not None, then it must be the name of
    #: an XML attribute that will be required on the top-level tag of
    #: the file being cached
    __identifier__ = None

    def _include_element(self, item, metadata):
        """ determine if an XML element matches the metadata """
        if isinstance(item, lxml.etree._Comment):  # pylint: disable=W0212
            return False
        negate = item.get('negate', 'false').lower() == 'true'
        if item.tag == 'Group':
            return negate == (item.get('name') not in metadata.groups)
        elif item.tag == 'Client':
            return negate == (item.get('name') != metadata.hostname)
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
                rv = copy.deepcopy(item)
                for child in rv.iterchildren():
                    rv.remove(child)
                for child in item.iterchildren():
                    rv.extend(self._match(child, metadata))
                return [rv]
        else:
            return []

    def Match(self, metadata):
        """ Return matching fragments of the data in this file.  A tag
        is considered to match if all ``<Group>`` and ``<Client>``
        tags that are its ancestors match the metadata given.  Since
        tags are included unmodified, it's possible for a tag to
        itself match while containing non-matching children.
        Consequently, only the tags contained in the list returned by
        Match() (and *not* their descendents) should be considered to
        match the metadata.

        :param metadata: Client metadata to match against.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: list of lxml.etree._Element objects """
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
                if item.text:
                    if item.getparent().text is None:
                        item.getparent().text = item.text
                    else:
                        item.getparent().text += item.text
                item.getparent().remove(item)
            else:
                for child in item.iterchildren():
                    self._xml_match(child, metadata)
        else:
            item.getparent().remove(item)

    def XMLMatch(self, metadata):
        """ Return a rebuilt XML document that only contains the
        matching portions of the original file.  A tag is considered
        to match if all ``<Group>`` and ``<Client>`` tags that are its
        ancestors match the metadata given.  Unlike :func:`Match`, the
        document returned by XMLMatch will only contain matching data.
        All ``<Group>`` and ``<Client>`` tags will have been stripped
        out.

        :param metadata: Client metadata to match against.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: lxml.etree._Element """
        rv = copy.deepcopy(self.xdata)
        for child in rv.iterchildren():
            self._xml_match(child, metadata)
        return rv


class INode(object):
    """ INodes provide lists of things available at a particular group
    intersection.  INodes are deprecated; new plugins should use
    :class:`Bcfg2.Server.Plugin.helpers.StructFile` instead. """

    raw = dict(
        Client="lambda m, e:'%(name)s' == m.hostname and predicate(m, e)",
        Group="lambda m, e:'%(name)s' in m.groups and predicate(m, e)")
    nraw = dict(
        Client="lambda m, e:'%(name)s' != m.hostname and predicate(m, e)",
        Group="lambda m, e:'%(name)s' not in m.groups and predicate(m, e)")
    containers = ['Group', 'Client']
    ignore = []

    def __init__(self, data, idict, parent=None):
        self.data = data
        self.contents = {}
        if parent is None:
            self.predicate = lambda m, e: True
        else:
            predicate = parent.predicate
            if data.get('negate', 'false').lower() == 'true':
                psrc = self.nraw
            else:
                psrc = self.raw
            if data.tag in list(psrc.keys()):
                self.predicate = eval(psrc[data.tag] %
                                      {'name': data.get('name')},
                                      {'predicate': predicate})
            else:
                raise PluginExecutionError("Unknown tag: %s" % data.tag)
        self.children = []
        self._load_children(data, idict)

    def _load_children(self, data, idict):
        """ load children """
        for item in data.getchildren():
            if item.tag in self.ignore:
                continue
            elif item.tag in self.containers:
                self.children.append(self.__class__(item, idict, self))
            else:
                try:
                    self.contents[item.tag][item.get('name')] = \
                        dict(item.attrib)
                except KeyError:
                    self.contents[item.tag] = \
                        {item.get('name'): dict(item.attrib)}
                if item.text:
                    self.contents[item.tag][item.get('name')]['__text__'] = \
                        item.text
                if item.getchildren():
                    self.contents[item.tag][item.get('name')]['__children__'] \
                        = item.getchildren()
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
                except:  # pylint: disable=W0702
                    data[key] = {}
                    data[key].update(self.contents[key])
            for child in self.children:
                child.Match(metadata, data, entry=entry)


class InfoNode (INode):
    """ :class:`Bcfg2.Server.Plugin.helpers.INode` implementation that
    includes ``<Path>`` tags, suitable for use with :file:`info.xml`
    files."""

    raw = dict(
        Client="lambda m, e: '%(name)s' == m.hostname and predicate(m, e)",
        Group="lambda m, e: '%(name)s' in m.groups and predicate(m, e)",
        Path="lambda m, e: ('%(name)s' == e.get('name') or " +
        "'%(name)s' == e.get('realname')) and " +
        "predicate(m, e)")
    nraw = dict(
        Client="lambda m, e: '%(name)s' != m.hostname and predicate(m, e)",
        Group="lambda m, e: '%(name)s' not in m.groups and predicate(m, e)",
        Path="lambda m, e: '%(name)s' != e.get('name') and " +
        "'%(name)s' != e.get('realname') and " +
        "predicate(m, e)")
    containers = ['Group', 'Client', 'Path']


class XMLSrc(XMLFileBacked):
    """ XMLSrc files contain a
    :class:`Bcfg2.Server.Plugin.helpers.INode` hierarchy that returns
    matching entries. XMLSrc objects are deprecated and
    :class:`Bcfg2.Server.Plugin.helpers.StructFile` should be
    preferred where possible."""
    __node__ = INode
    __cacheobj__ = dict
    __priority_required__ = True

    def __init__(self, filename, fam=None, should_monitor=False, create=None):
        XMLFileBacked.__init__(self, filename, fam, should_monitor, create)
        self.items = {}
        self.cache = None
        self.pnode = None
        self.priority = -1

    def HandleEvent(self, _=None):
        """Read file upon update."""
        try:
            data = open(self.name).read()
        except IOError:
            msg = "Failed to read file %s: %s" % (self.name, sys.exc_info()[1])
            self.logger.error(msg)
            raise PluginExecutionError(msg)
        self.items = {}
        try:
            xdata = lxml.etree.XML(data, parser=Bcfg2.Server.XMLParser)
        except lxml.etree.XMLSyntaxError:
            msg = "Failed to parse file %s: %s" % (self.name,
                                                   sys.exc_info()[1])
            self.logger.error(msg)
            raise PluginExecutionError(msg)
        self.pnode = self.__node__(xdata, self.items)
        self.cache = None
        try:
            self.priority = int(xdata.get('priority'))
        except (ValueError, TypeError):
            if self.__priority_required__:
                msg = "Got bogus priority %s for file %s" % \
                    (xdata.get('priority'), self.name)
                self.logger.error(msg)
                raise PluginExecutionError(msg)

        del xdata, data

    def Cache(self, metadata):
        """Build a package dict for a given host."""
        if self.cache is None or self.cache[0] != metadata:
            cache = (metadata, self.__cacheobj__())
            if self.pnode is None:
                self.logger.error("Cache method called early for %s; "
                                  "forcing data load" % self.name)
                self.HandleEvent()
                return
            self.pnode.Match(metadata, cache[1])
            self.cache = cache

    def __str__(self):
        return str(self.items)


class InfoXML(XMLSrc):
    """ InfoXML files contain a
    :class:`Bcfg2.Server.Plugin.helpers.InfoNode` hierarchy that
    returns matching entries, suitable for use with :file:`info.xml`
    files."""
    __node__ = InfoNode
    __priority_required__ = False


class XMLDirectoryBacked(DirectoryBacked):
    """ :class:`Bcfg2.Server.Plugin.helpers.DirectoryBacked` for XML files. """

    #: Only track and include files whose names (not paths) match this
    #: compiled regex.
    patterns = re.compile(r'^.*\.xml$')

    #: The type of child objects to create for files contained within
    #: the directory that is tracked.  Default is
    #: :class:`Bcfg2.Server.Plugin.helpers.XMLFileBacked`
    __child__ = XMLFileBacked


class PrioDir(Plugin, Generator, XMLDirectoryBacked):
    """ PrioDir handles a directory of XML files where each file has a
    set priority.

    .. -----
    .. autoattribute:: __child__
    """

    #: The type of child objects to create for files contained within
    #: the directory that is tracked.  Default is
    #: :class:`Bcfg2.Server.Plugin.helpers.XMLSrc`
    __child__ = XMLSrc

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        Generator.__init__(self)
        XMLDirectoryBacked.__init__(self, self.data, self.core.fam)
    __init__.__doc__ = Plugin.__init__.__doc__

    def HandleEvent(self, event):
        XMLDirectoryBacked.HandleEvent(self, event)
        self.Entries = {}
        for src in list(self.entries.values()):
            for itype, children in list(src.items.items()):
                for child in children:
                    try:
                        self.Entries[itype][child] = self.BindEntry
                    except KeyError:
                        self.Entries[itype] = {child: self.BindEntry}
    HandleEvent.__doc__ = XMLDirectoryBacked.HandleEvent.__doc__

    def _matches(self, entry, metadata, rules):  # pylint: disable=W0613
        """ Whether or not a given entry has a matching entry in this
        PrioDir.  By default this does strict matching (i.e., the
        entry name is in ``rules.keys()``), but this can be overridden
        to provide regex matching, etc.

        :param entry: The entry to find a match for
        :type entry: lxml.etree._Element
        :param metadata: The metadata to get attributes for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :rules: A dict of rules to look in for a matching rule
        :type rules: dict
        :returns: bool
        """
        return entry.get('name') in rules

    def BindEntry(self, entry, metadata):
        """ Bind the attributes that apply to an entry to it.  The
        entry is modified in-place.

        :param entry: The entry to add attributes to.
        :type entry: lxml.etree._Element
        :param metadata: The metadata to get attributes for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        attrs = self.get_attrs(entry, metadata)
        for key, val in list(attrs.items()):
            entry.attrib[key] = val

    def get_attrs(self, entry, metadata):
        """ Get a list of attributes to add to the entry during the
        bind.  This is a complex method, in that it both modifies the
        entry, and returns attributes that need to be added to the
        entry.  That seems sub-optimal, and should probably be changed
        at some point.  Namely:

        * The return value includes all XML attributes that need to be
          added to the entry, but it does not add them.
        * If text contents or child tags need to be added to the
          entry, they are added to the entry in place.

        :param entry: The entry to add attributes to.
        :type entry: lxml.etree._Element
        :param metadata: The metadata to get attributes for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: dict of <attr name>:<attr value>
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginExecutionError`
        """
        for src in self.entries.values():
            src.Cache(metadata)

        matching = [src for src in list(self.entries.values())
                    if (src.cache and
                        entry.tag in src.cache[1] and
                        self._matches(entry, metadata,
                                      src.cache[1][entry.tag]))]
        if len(matching) == 0:
            raise PluginExecutionError("No matching source for entry when "
                                       "retrieving attributes for %s(%s)" %
                                       (entry.tag, entry.attrib.get('name')))
        elif len(matching) == 1:
            index = 0
        else:
            prio = [int(src.priority) for src in matching]
            if prio.count(max(prio)) > 1:
                msg = "Found conflicting sources with same priority for " + \
                    "%s:%s for %s" % (entry.tag, entry.get("name"),
                                      metadata.hostname)
                self.logger.error(msg)
                self.logger.error([item.name for item in matching])
                self.logger.error("Priority was %s" % max(prio))
                raise PluginExecutionError(msg)
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
            for item in data['__children__']:
                entry.append(copy.copy(item))

        return dict([(key, data[key])
                     for key in list(data.keys())
                     if not key.startswith('__')])


class Specificity(CmpMixin):
    """ Represent the specificity of an object; i.e., what client(s)
    it applies to.  It can be group- or client-specific, or apply to
    all clients.

    Specificity objects are sortable; objects that are less specific
    are considered less than objects that are more specific.  Objects
    that apply to all clients are the least specific; objects that
    apply to a single client are the most specific.  Objects that
    apply to groups are sorted by priority. """

    def __init__(self, all=False, group=False,  # pylint: disable=W0622
                 hostname=False, prio=0, delta=False):
        """
        :param all: The object applies to all clients.
        :type all: bool
        :param group: The object applies only to the given group.
        :type group: string or False
        :param hostname: The object applies only to the named client.
        :type hostname: string or False
        :param prio: The object has the given priority relative to
                     other objects that also apply to the same group.
                     ``<group>`` must be specified with ``<prio>``.
        :type prio: int
        :param delta: The object is a delta (i.e., a .cat or .diff
                      file, not a full file).  Deltas are deprecated.
        :type delta: bool

        Exactly one of {all|group|hostname} should be given.
        """
        CmpMixin.__init__(self)
        self.hostname = hostname
        self.all = all
        self.group = group
        self.prio = prio
        self.delta = delta

    def matches(self, metadata):
        """ Return True if the object described by this Specificity
        object applies to the given client.  That is, if this
        Specificity applies to all clients, or to a group the client
        is a member of, or to the client individually.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: bool
        """
        return (self.all or
                self.hostname == metadata.hostname or
                self.group in metadata.groups)

    def __cmp__(self, other):  # pylint: disable=R0911
        """Sort most to least specific."""
        if self.all:
            if other.all:
                return 0
            else:
                return 1
        elif other.all:
            return -1
        elif self.group:
            if other.hostname:
                return 1
            if other.group and other.prio > self.prio:
                return 1
            if other.group and other.prio == self.prio:
                return 0
        elif other.group:
            return -1
        elif self.hostname and other.hostname:
            return 0
        return -1

    def __str__(self):
        rv = [self.__class__.__name__, ': ']
        if self.all:
            rv.append("all")
        elif self.group:
            rv.append("Group %s, priority %s" % (self.group, self.prio))
        elif self.hostname:
            rv.append("Host %s" % self.hostname)
        if self.delta:
            rv.append(", delta=%s" % self.delta)
        return "".join(rv)


class SpecificData(object):
    """ A file that is specific to certain clients, groups, or all
    clients. """

    def __init__(self, name, specific, encoding):  # pylint: disable=W0613
        """
        :param name: The full path to the file
        :type name: string
        :param specific: A
                         :class:`Bcfg2.Server.Plugin.helpers.Specificity`
                         object describing what clients this file
                         applies to.
        :type specific: Bcfg2.Server.Plugin.helpers.Specificity
        :param encoding: The encoding to use for data in this file
        :type encoding: string
        """
        self.name = name
        self.specific = specific
        self.data = None

    def handle_event(self, event):
        """ Handle a FAM event.  Note that the SpecificData object
        itself has no FAM, so this must be produced by a parent object
        (e.g., :class:`Bcfg2.Server.Plugin.helpers.EntrySet`).

        :param event: The event that applies to this file
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        :raises: :exc:`Bcfg2.Server.Plugin.exceptions.PluginExecutionError`
        """
        if event.code2str() == 'deleted':
            return
        try:
            self.data = open(self.name).read()
        except UnicodeDecodeError:
            self.data = open(self.name, mode='rb').read()
        except:  # pylint: disable=W0201
            LOGGER.error("Failed to read file %s" % self.name)


class EntrySet(Debuggable):
    """ EntrySets deal with a collection of host- and group-specific
    files (e.g., :class:`Bcfg2.Server.Plugin.helpers.SpecificData`
    objects) in a single directory. EntrySets are usually used as part
    of :class:`Bcfg2.Server.Plugin.helpers.GroupSpool` objects."""

    #: Preemptively ignore files whose names (not paths) match this
    #: compiled regex.  ``ignore`` cannot be set to ``None``.  If a
    #: file is encountered that does not match the ``basename``
    #: argument passed to the constructor or ``ignore``, then a
    #: warning will be produced.
    ignore = re.compile(r'^(\.#.*|.*~|\..*\.(sw[px])|.*\.genshi_include)$')

    # The ``basename`` argument passed to the constructor will be
    #: processed as a string that contains a regular expression (i.e.,
    #: *not* a compiled regex object) if ``basename_is_regex`` is True,
    #: and all files that match the regex will be cincluded in the
    #: EntrySet.  If ``basename_is_regex`` is False, then it will be
    #: considered a plain string and filenames must match exactly.
    basename_is_regex = False

    def __init__(self, basename, path, entry_type, encoding):
        """
        :param basename: The filename or regular expression that files
                         in this EntrySet must match.  See
                         :attr:`basename_is_regex` for more details.
        :type basename: string
        :param path: The full path to the directory containing files
                     for this EntrySet
        :type path: string
        :param entry_type: A callable that returns an object that
                           represents files in this EntrySet.  This
                           will usually be a class object, but it can
                           be an object factory or similar callable.
                           See below for the expected signature.
        :type entry_type: callable
        :param encoding: The encoding of all files in this entry set.
        :type encoding: string

        The ``entry_type`` callable must have the following signature::

            entry_type(filepath, specificity, encoding)

        Where the parameters are:

        :param filepath: Full path to file
        :type filepath: string
        :param specific: A
                         :class:`Bcfg2.Server.Plugin.helpers.Specificity`
                         object describing what clients this file
                         applies to.
        :type specific: Bcfg2.Server.Plugin.helpers.Specificity
        :param encoding: The encoding to use for data in this file
        :type encoding: string

        Additionally, the object returned by ``entry_type`` must have
        a ``specific`` attribute that is sortable (e.g., a
        :class:`Bcfg2.Server.Plugin.helpers.Specificity` object).

        See :class:`Bcfg2.Server.Plugin.helpers.SpecificData` for an
        example of a class that can be used as an ``entry_type``.
        """
        Debuggable.__init__(self, name=basename)
        self.path = path
        self.entry_type = entry_type
        self.entries = {}
        self.metadata = DEFAULT_FILE_METADATA.copy()
        self.infoxml = None
        self.encoding = encoding

        if self.basename_is_regex:
            base_pat = basename
        else:
            base_pat = re.escape(basename)
        pattern = r'(.*/)?' + base_pat + \
            r'(\.((H_(?P<hostname>\S+))|(G(?P<prio>\d+)_(?P<group>\S+))))?$'

        #: ``specific`` is a regular expression that is used to
        #: determine the specificity of a file in this entry set.  It
        #: must have three named groups: ``hostname``, ``prio`` (the
        #: priority of a group-specific file), and ``group``.  The base
        #: regex is constructed from the ``basename`` argument. It can
        #: be overridden on a per-entry basis in :func:`entry_init`.
        self.specific = re.compile(pattern)

    def get_matching(self, metadata):
        """ Get a list of all entries that apply to the given client.
        This gets all matching entries; for example, there could be an
        entry that applies to all clients, multiple group-specific
        entries, and a client-specific entry, all of which would be
        returned by get_matching().  You can use :func:`best_matching`
        to get the single best matching entry.

        :param metadata: The client metadata to get matching entries for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: list -- all matching ``entry_type`` objects (see the
                  constructor docs for more details)
        """
        return [item for item in list(self.entries.values())
                if item.specific.matches(metadata)]

    def best_matching(self, metadata, matching=None):
        """ Return the single most specific matching entry from the
        set of matching entries.  You can use :func:`get_matching` to
        get all matching entries.

        :param metadata: The client metadata to get matching entries for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param matching: The set of matching entries to pick from.  If
                         this is not provided, :func:`get_matching`
                         will be called.
        :type matching: list of ``entry_type`` objects (see the constructor
                        docs for more details)
        :returns: a single object from the list of matching
                  ``entry_type`` objects
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginExecutionError`
                 if no matching entries are found
        """
        if matching is None:
            matching = self.get_matching(metadata)

        if matching:
            matching.sort(key=operator.attrgetter("specific"))
            return matching[0]
        else:
            raise PluginExecutionError("No matching entries available for %s "
                                       "for %s" % (self.path,
                                                   metadata.hostname))

    def handle_event(self, event):
        """ Dispatch a FAM event to the appropriate function or child
        ``entry_type`` object.  This will probably be handled by a
        call to :func:`update_metadata`, :func:`reset_metadata`,
        :func:`entry_init`, or to the ``entry_type``
        ``handle_event()`` function.

        :param event: An event that applies to a file handled by this
                      EntrySet
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
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
                self.logger.warning("Got %s event for unknown file %s" %
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
        """ Handle the creation of a file on the filesystem and the
        creation of an object in this EntrySet to track it.

        :param event: An event that applies to a file handled by this
                      EntrySet
        :type event: Bcfg2.Server.FileMonitor.Event
        :param entry_type: Override the default ``entry_type`` for
                           this EntrySet object and create a different
                           object for this entry.  See the constructor
                           docs for more information on
                           ``entry_type``.
        :type entry_type: callable
        :param specific: Override the default :attr:`specific` regular
                         expression used by this object with a custom
                         regular expression that will be used to
                         determine the specificity of this entry.
        :type specific: compiled regular expression object
        :returns: None
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.SpecificityError`
        """
        if entry_type is None:
            entry_type = self.entry_type

        if event.filename in self.entries:
            self.logger.warn("Got duplicate add for %s" % event.filename)
        else:
            fpath = os.path.join(self.path, event.filename)
            try:
                spec = self.specificity_from_filename(event.filename,
                                                      specific=specific)
            except SpecificityError:
                if not self.ignore.match(event.filename):
                    self.logger.error("Could not process filename %s; ignoring"
                                      % fpath)
                return
            self.entries[event.filename] = entry_type(fpath, spec,
                                                      self.encoding)
        self.entries[event.filename].handle_event(event)

    def specificity_from_filename(self, fname, specific=None):
        """ Construct a
        :class:`Bcfg2.Server.Plugin.helpers.Specificity` object from a
        filename and regex. See :attr:`specific` for details on the
        regex.

        :param fname: The filename (not full path) of a file that is
                      in this EntrySet's directory.  It is not
                      necessary to determine first if the filename
                      matches this EntrySet's basename; that can be
                      done by catching
                      :class:`Bcfg2.Server.Plugin.exceptions.SpecificityError`
                      from this function.
        :type fname: string
        :param specific: Override the default :attr:`specific` regular
                         expression used by this object with a custom
                         regular expression that will be used to
                         determine the specificity of this entry.
        :type specific: compiled regular expression object
        :returns: Object representing the specificity of the file
        :rtype: :class:`Bcfg2.Server.Plugin.helpers.Specificity`
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.SpecificityError`
                 if the regex does not match the filename
        """
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
        """ Process changes to or creation of info, :info, and
        info.xml files for the EntrySet.

        :param event: An event that applies to an info handled by this
                      EntrySet
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        fpath = os.path.join(self.path, event.filename)
        if event.filename == 'info.xml':
            if not self.infoxml:
                self.infoxml = InfoXML(fpath)
            self.infoxml.HandleEvent(event)
        elif event.filename in [':info', 'info']:
            for line in open(fpath).readlines():
                match = INFO_REGEX.match(line)
                if not match:
                    self.logger.warning("Failed to match line in %s: %s" %
                                        (fpath, line))
                    continue
                else:
                    mgd = match.groupdict()
                    for key, value in list(mgd.items()):
                        if value:
                            self.metadata[key] = value
                    if len(self.metadata['mode']) == 3:
                        self.metadata['mode'] = "0%s" % self.metadata['mode']

    def reset_metadata(self, event):
        """ Reset metadata to defaults if info. :info, or info.xml are
        removed.

        :param event: An event that applies to an info handled by this
                      EntrySet
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        if event.filename == 'info.xml':
            self.infoxml = None
        elif event.filename in [':info', 'info']:
            self.metadata = DEFAULT_FILE_METADATA.copy()

    def bind_info_to_entry(self, entry, metadata):
        """ Shortcut to call :func:`bind_info` with the base
        info/info.xml for this EntrySet.

        :param entry: The abstract entry to bind the info to. This
                      will be modified in place
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to get info for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        bind_info(entry, metadata, infoxml=self.infoxml, default=self.metadata)

    def bind_entry(self, entry, metadata):
        """ Return the single best fully-bound entry from the set of
        available entries for the specified client.

        :param entry: The abstract entry to bind the info to
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to get info for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: lxml.etree._Element - the fully-bound entry
        """
        self.bind_info_to_entry(entry, metadata)
        return self.best_matching(metadata).bind_entry(entry, metadata)


class GroupSpool(Plugin, Generator):
    """ A GroupSpool is a collection of
    :class:`Bcfg2.Server.Plugin.helpers.EntrySet` objects -- i.e., a
    directory tree, each directory in which may contain files that are
    specific to groups/clients/etc. """

    #: ``filename_pattern`` is used as the ``basename`` argument to the
    #: :attr:`es_cls` callable.  It may or may not be a regex,
    #: depending on the :attr:`EntrySet.basename_is_regex` setting.
    filename_pattern = ""

    #: ``es_child_cls`` is a callable that will be used as the
    #: ``entry_type`` argument to the :attr:`es_cls` callable.  It must
    #: return objects that will represent individual files in the
    #: GroupSpool.  For instance,
    #: :class:`Bcfg2.Server.Plugin.helpers.SpecificData`.
    es_child_cls = object

    #: ``es_cls`` is a callable that must return objects that will be
    #: used to represent directories (i.e., sets of entries) within the
    #: GroupSpool.  E.g.,
    #: :class:`Bcfg2.Server.Plugin.helpers.EntrySet`.  The returned
    #: object must implement a callable called ``bind_entry`` that has
    #: the same signature as :attr:`EntrySet.bind_entry`.
    es_cls = EntrySet

    #: The entry type (i.e., the XML tag) handled by this GroupSpool
    #: object.
    entry_type = 'Path'

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        Generator.__init__(self)

        #: See :class:`Bcfg2.Server.Plugins.interfaces.Generator` for
        #: details on the Entries attribute.
        self.Entries[self.entry_type] = {}

        #: ``entries`` is a dict whose keys are :func:`event_id` return
        #: values and whose values are :attr:`es_cls` objects. It ties
        #: the directories handled by this GroupSpools to the
        #: :attr:`es_cls` objects that handle each directory.
        self.entries = {}
        self.handles = {}
        self.AddDirectoryMonitor('')
        self.encoding = core.setup['encoding']
    __init__.__doc__ = Plugin.__init__.__doc__

    def add_entry(self, event):
        """ This method handles two functions:

        * Adding a new entry of type :attr:`es_cls` to track a new
          directory.
        * Passing off an event on a file to the correct entry object
          to handle it.

        :param event: An event that applies to a file or directory
                      handled by this GroupSpool
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        epath = self.event_path(event)
        ident = self.event_id(event)
        if os.path.isdir(epath):
            self.AddDirectoryMonitor(epath[len(self.data):])
        if ident not in self.entries and os.path.isfile(epath):
            dirpath = self.data + ident
            self.entries[ident] = self.es_cls(self.filename_pattern,
                                              dirpath,
                                              self.es_child_cls,
                                              self.encoding)
            self.Entries[self.entry_type][ident] = \
                self.entries[ident].bind_entry
        if not os.path.isdir(epath):
            # do not pass through directory events
            self.entries[ident].handle_event(event)

    def event_path(self, event):
        """ Return the full path to the filename affected by an event.
        :class:`Bcfg2.Server.FileMonitor.Event` objects just contain
        the filename, not the full path, so this function reconstructs
        the fill path based on the path to the :attr:`es_cls` object
        that handles the event.

        :param event: An event that applies to a file or directory
                      handled by this GroupSpool
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: string
        """
        return os.path.join(self.data,
                            self.handles[event.requestID].lstrip("/"),
                            event.filename)

    def event_id(self, event):
        """ Return a string that can be used to relate the event
        unambiguously to a single :attr:`es_cls` object in the
        :attr:`entries` dict.  In practice, this means:

        * If the event is on a directory, ``event_id`` returns the
          full path to the directory.
        * If the event is on a file, ``event_id`` returns the full
          path to the directory the file is in.

        :param event: An event that applies to a file or directory
                      handled by this GroupSpool
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: string
        """
        epath = self.event_path(event)
        if os.path.isdir(epath):
            return os.path.join(self.handles[event.requestID].lstrip("/"),
                                event.filename)
        else:
            return self.handles[event.requestID].rstrip("/")

    def set_debug(self, debug):
        for entry in self.entries.values():
            if hasattr(entry, "set_debug"):
                entry.set_debug(debug)
        return Plugin.set_debug(self, debug)
    set_debug.__doc__ = Plugin.set_debug.__doc__

    def HandleEvent(self, event):
        """ HandleEvent is the event dispatcher for GroupSpool
        objects.  It receives all events and dispatches them the
        appropriate handling object (e.g., one of the :attr:`es_cls`
        objects in :attr:`entries`), function (e.g.,
        :func:`add_entry`), or behavior (e.g., deleting an entire
        entry set).

        :param event: An event that applies to a file or directory
                      handled by this GroupSpool
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        action = event.code2str()
        if event.filename[0] == '/':
            return
        ident = self.event_id(event)

        if action in ['exists', 'created']:
            self.add_entry(event)
        elif action == 'changed':
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
        """ Add a FAM monitor to a new directory and set the
        appropriate event handler.

        :param relative: The path to the directory relative to the
                         base data directory of the GroupSpool object.
        :type relative: string
        :returns: None
        """
        if not relative.endswith('/'):
            relative += '/'
        name = self.data + relative
        if relative not in list(self.handles.values()):
            if not os.path.isdir(name):
                self.logger.error("Failed to open directory %s" % name)
                return
            reqid = self.core.fam.AddMonitor(name, self)
            self.handles[reqid] = relative
