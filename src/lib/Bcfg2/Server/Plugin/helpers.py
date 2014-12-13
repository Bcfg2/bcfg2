""" Helper classes for Bcfg2 server plugins """

import os
import re
import sys
import time
import copy
import glob
import logging
import genshi
import operator
import lxml.etree
import Bcfg2.Server
import Bcfg2.Options
import Bcfg2.Server.FileMonitor
from Bcfg2.Logger import Debuggable
from Bcfg2.Compat import CmpMixin, wraps
from Bcfg2.Server.Plugin.base import Plugin
from Bcfg2.Server.Plugin.interfaces import Generator, TemplateDataProvider
from Bcfg2.Server.Plugin.exceptions import SpecificityError, \
    PluginExecutionError, PluginInitError

try:
    import Bcfg2.Server.Encryption
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    import django  # pylint: disable=W0611
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

LOGGER = logging.getLogger(__name__)


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
                Bcfg2.Server.Statistics.stats.add_value(name,
                                                        time.time() - start)

        return inner


def rmi_list_argument(func):
    """ Decorater to mark methods that need one list argument.
    A RMI call will translate a list of arguments to an argument
    of one list. """
    func.list_argument = True
    return func


def handle_rmi_list_argument(func):
    """ Automatically handle list arguments. For calls that are marked
    with `rmi_list_argument` the arguments get converted. All other calls
    are simply passed throught. """

    @wraps(func)
    def inner(*args):
        """ Convert a list of arguments to one list argument. """
        return func(list(args))

    if getattr(func, 'list_argument', False):
        return inner
    else:
        return func


def removecomment(stream):
    """ A Genshi filter that removes comments from the stream.  This
    function is a generator.

    :param stream: The Genshi stream to remove comments from
    :type stream: genshi.core.Stream
    :returns: tuple of ``(kind, data, pos)``, as when iterating
              through a Genshi stream
    """
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


def bind_info(entry, metadata, infoxml=None, default=None):
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
    if default is None:
        default = default_path_metadata()
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


def default_path_metadata():
    """ Get the default Path entry metadata from the config.

    :returns: dict of metadata attributes and their default values
    """
    return dict([(k, getattr(Bcfg2.Options.setup, "default_%s" % k))
                 for k in ['owner', 'group', 'mode', 'secontext', 'important',
                           'paranoid', 'sensitive']])


class DefaultTemplateDataProvider(TemplateDataProvider):
    """ A base
    :class:`Bcfg2.Server.Plugin.interfaces.TemplateDataProvider` that
    provides default data for text and XML templates.

    Note that, since Cheetah and Genshi text templates treat the
    ``path`` variable differently, this is overridden, by
    :class:`Bcfg2.Server.Plugins.Cfg.CfgCheetahGenerator.DefaultCheetahDataProvider`
    and
    :class:`Bcfg2.Server.Plugins.Cfg.CfgGenshiGenerator.DefaultGenshiDataProvider`,
    respectively. """

    def get_template_data(self, entry, metadata, template):
        return dict(name=entry.get('realname', entry.get('name')),
                    metadata=metadata,
                    source_path=template,
                    repo=Bcfg2.Options.setup.repository)

    def get_xml_template_data(self, _, metadata):
        return dict(metadata=metadata,
                    repo=Bcfg2.Options.setup.repository)

_sentinel = object()  # pylint: disable=C0103


def _get_template_data(func_name, args, default=_sentinel):
    """ Generic template data getter for both text and XML templates.

    :param func_name: The name of the function to call on
                      :class:`Bcfg2.Server.Plugin.interfaces.TemplateDataProvider`
                      objects to get data for this template type.
                      Should be one of either ``get_template_data``
                      for text templates, or ``get_xml_template_data``
                      for XML templates.
    :type func_name: string
    :param args: The arguments to pass to the data retrieval function
    :type args: list
    :param default: An object that provides a set of base values. If
                    this is not provided, an instance of
                    :class:`Bcfg2.Server.Plugin.helpers.DefaultTemplateDataProvider`
                    is used. This can be set to None to avoid setting
                    any base values at all.
    :type default: Bcfg2.Server.Plugin.interfaces.TemplateDataProvider
    """
    if default is _sentinel:
        default = DefaultTemplateDataProvider()
    providers = Bcfg2.Server.core.plugins_by_type(TemplateDataProvider)
    if default is not None:
        providers.insert(0, default)

    rv = dict()
    source = dict()
    for prov in providers:
        pdata = getattr(prov, func_name)(*args)
        for key, val in pdata.items():
            if key not in rv:
                rv[key] = val
                source[key] = prov
            else:
                LOGGER.warning("Duplicate template variable %s provided by "
                               "both %s and %s" % (key, prov, source[key]))
    return rv


def get_template_data(entry, metadata, template, default=_sentinel):
    """ Get all template variables for a text (i.e., Cfg) template """
    return _get_template_data("get_template_data", [entry, metadata, template],
                              default=default)


def get_xml_template_data(structfile, metadata, default=_sentinel):
    """ Get all template variables for an XML template """
    return _get_template_data("get_xml_template_data", [structfile, metadata],
                              default=default)


class DatabaseBacked(Plugin):
    """ Provides capabilities for a plugin to read and write to a
    database. The plugin must add an option to flag database use with
    something like:

    options = Bcfg2.Server.Plugin.Plugins.options + [
        Bcfg2.Options.BooleanOption(
            cf=('metadata', 'use_database'), dest="metadata_db",
            help="Use database capabilities of the Metadata plugin")

    This must be done manually due to various limitations in Python.

    .. private-include: _use_db
    .. private-include: _must_lock
    """

    def __init__(self, core):
        Plugin.__init__(self, core)
        use_db = getattr(Bcfg2.Options.setup, "%s_db" % self.name.lower(),
                         False)
        if use_db and not HAS_DJANGO:
            raise PluginInitError("%s is configured to use the database but "
                                  "Django libraries are not found" % self.name)
        elif use_db and not self.core.database_available:
            raise PluginInitError("%s is configured to use the database but "
                                  "the database is unavailable due to prior "
                                  "errors" % self.name)

    @property
    def _use_db(self):
        """ Whether or not this plugin is configured to use the
        database. """
        use_db = getattr(Bcfg2.Options.setup, "%s_db" % self.name.lower(),
                         False)
        if use_db and HAS_DJANGO and self.core.database_available:
            return True
        else:
            return False

    @property
    def _must_lock(self):
        """ Whether or not the backend database must acquire a thread
        lock before writing, because it does not allow multiple
        threads to write."""
        return self._use_db and Bcfg2.Options.setup.db_engine == 'sqlite3'

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

    class Meta(object):  # pylint: disable=W0232
        """ Model metadata options """
        app_label = "Server"


class FileBacked(Debuggable):
    """ This object caches file data in memory. FileBacked objects are
    principally meant to be used as a part of
    :class:`Bcfg2.Server.Plugin.helpers.DirectoryBacked`. """

    def __init__(self, name):
        """
        :param name: The full path to the file to cache and monitor
        :type name: string
        """
        Debuggable.__init__(self)

        #: A string containing the raw data in this file
        self.data = ''

        #: The full path to the file
        self.name = name

        #: The FAM object used to receive notifications of changes
        self.fam = Bcfg2.Server.FileMonitor.get_fam()

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

    def __init__(self, data):
        """
        :param data: The path to the data directory that will be
                     monitored
        :type data: string

        .. -----
        .. autoattribute:: __child__
        """
        Debuggable.__init__(self)

        self.data = os.path.normpath(data)
        self.fam = Bcfg2.Server.FileMonitor.get_fam()

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
                                                             relative))
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

    def __init__(self, filename, should_monitor=False, create=None):
        """
        :param filename: The full path to the file to cache and monitor
        :type filename: string
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
        FileBacked.__init__(self, filename)

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
        if should_monitor:
            self.fam.AddMonitor(filename, self)

    def _follow_xincludes(self, fname=None, xdata=None):
        """ follow xincludes, adding included files to self.extras """
        xinclude = '%sinclude' % Bcfg2.Server.XI_NAMESPACE

        if xdata is None:
            if fname is None:
                xdata = self.xdata.getroottree()
            else:
                xdata = lxml.etree.parse(fname)
        for el in xdata.findall('//' + xinclude):
            name = el.get("href")
            if name.startswith("/"):
                fpath = name
            else:
                rel = fname or self.name
                fpath = os.path.join(os.path.dirname(rel), name)

            # expand globs in xinclude, a bcfg2-specific extension
            extras = glob.glob(fpath)
            if not extras:
                msg = "%s: %s does not exist, skipping" % (self.name, name)
                if el.findall('./%sfallback' % Bcfg2.Server.XI_NAMESPACE):
                    self.logger.debug(msg)
                else:
                    self.logger.error(msg)
                # add a FAM monitor for this path.  this isn't perfect
                # -- if there's an xinclude of "*.xml", we'll watch
                # the literal filename "*.xml".  but for non-globbing
                # filenames, it works fine.
                if fpath not in self.extra_monitors:
                    self.add_monitor(fpath)

            parent = el.getparent()
            parent.remove(el)
            for extra in extras:
                if extra != self.name:
                    lxml.etree.SubElement(parent, xinclude, href=extra)
                    if extra not in self.extras:
                        self.extras.append(extra)
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
        """ Add a FAM monitor to a file that has been XIncluded.

        :param fpath: The full path to the file to monitor
        :type fpath: string
        :returns: None
        """
        self.extra_monitors.append(fpath)
        self.fam.AddMonitor(fpath, self)

    def __iter__(self):
        return iter(self.entries)

    def __str__(self):
        return "%s at %s" % (self.__class__.__name__, self.name)


class StructFile(XMLFileBacked):
    """ StructFiles are XML files that contain a set of structure file
    formatting logic for handling ``<Group>`` and ``<Client>``
    tags.

    .. -----
    .. autoattribute:: __identifier__
    .. automethod:: _include_element
    """

    #: If ``__identifier__`` is not None, then it must be the name of
    #: an XML attribute that will be required on the top-level tag of
    #: the file being cached
    __identifier__ = None

    #: Whether or not to enable encryption
    encryption = True

    #: Callbacks used to determine if children of items with the given
    #: tags should be included in the return value of
    #: :func:`Bcfg2.Server.Plugin.helpers.StructFile.Match` and
    #: :func:`Bcfg2.Server.Plugin.helpers.StructFile.XMLMatch`.  Each
    #: callback is passed the same arguments as
    #: :func:`Bcfg2.Server.Plugin.helpers.StructFile._include_element`.
    #: It should return True if children of the element should be
    #: included in the match, False otherwise.  The callback does
    #: *not* need to consider negation; that will be handled in
    #: :func:`Bcfg2.Server.Plugin.helpers.StructFile._include_element`
    _include_tests = \
        dict(Group=lambda el, md, *args: el.get('name') in md.groups,
             Client=lambda el, md, *args: el.get('name') == md.hostname)

    def __init__(self, filename, should_monitor=False, create=None):
        XMLFileBacked.__init__(self, filename, should_monitor=should_monitor,
                               create=create)
        self.template = None

    def Index(self):
        XMLFileBacked.Index(self)
        if (self.name.endswith('.genshi') or
            ('py' in self.xdata.nsmap and
             self.xdata.nsmap['py'] == 'http://genshi.edgewall.org/')):
            try:
                loader = genshi.template.TemplateLoader()
                self.template = \
                    loader.load(self.name,
                                cls=genshi.template.MarkupTemplate,
                                encoding=Bcfg2.Options.setup.encoding)
            except LookupError:
                err = sys.exc_info()[1]
                self.logger.error('Genshi lookup error in %s: %s' % (self.name,
                                                                     err))
            except genshi.template.TemplateError:
                err = sys.exc_info()[1]
                self.logger.error('Genshi template error in %s: %s' %
                                  (self.name, err))
            except genshi.input.ParseError:
                err = sys.exc_info()[1]
                self.logger.error('Genshi parse error in %s: %s' % (self.name,
                                                                    err))

        if HAS_CRYPTO and self.encryption:
            for el in self.xdata.xpath("//*[@encrypted]"):
                try:
                    el.text = self._decrypt(el).encode('ascii',
                                                       'xmlcharrefreplace')
                except UnicodeDecodeError:
                    self.logger.info("%s: Decrypted %s to gibberish, skipping"
                                     % (self.name, el.tag))
                except Bcfg2.Server.Encryption.EVPError:
                    lax_decrypt = self.xdata.get(
                        "lax_decryption",
                        str(Bcfg2.Options.setup.lax_decryption)).lower() == \
                        "true"
                    msg = "Failed to decrypt %s element in %s" % (el.tag,
                                                                  self.name)
                    if lax_decrypt:
                        self.logger.debug(msg)
                    else:
                        raise PluginExecutionError(msg)
    Index.__doc__ = XMLFileBacked.Index.__doc__

    def _decrypt(self, element):
        """ Decrypt a single encrypted properties file element """
        if not element.text or not element.text.strip():
            return
        passes = Bcfg2.Options.setup.passphrases
        try:
            passphrase = passes[element.get("encrypted")]
            return Bcfg2.Server.Encryption.ssl_decrypt(element.text,
                                                       passphrase)
        except KeyError:
            raise Bcfg2.Server.Encryption.EVPError("No passphrase named '%s'" %
                                                   element.get("encrypted"))
        raise Bcfg2.Server.Encryption.EVPError("Failed to decrypt")

    def _include_element(self, item, metadata, *args):
        """ Determine if an XML element matches the other arguments.

        The first argument is always the XML element to match, and the
        second will always be a single
        :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata` object
        representing the metadata to match against.  Subsequent
        arguments are as given to
        :func:`Bcfg2.Server.Plugin.helpers.StructFile.Match` or
        :func:`Bcfg2.Server.Plugin.helpers.StructFile.XMLMatch`.  In
        the base StructFile implementation, there are no additional
        arguments; in classes that inherit from StructFile, see the
        :func:`Match` and :func:`XMLMatch` method signatures."""
        if isinstance(item, lxml.etree._Comment):  # pylint: disable=W0212
            return False
        if item.tag in self._include_tests:
            negate = item.get('negate', 'false').lower() == 'true'
            return negate != self._include_tests[item.tag](item, metadata,
                                                           *args)
        else:
            return True

    def _render(self, metadata):
        """ Render the template for the given client metadata

        :param metadata: Client metadata to match against.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: lxml.etree._Element object representing the rendered
                  XML data
        """
        stream = self.template.generate(
            **get_xml_template_data(self, metadata)).filter(removecomment)
        return lxml.etree.XML(stream.render('xml',
                                            strip_whitespace=False).encode(),
                              parser=Bcfg2.Server.XMLParser)

    def _match(self, item, metadata, *args):
        """ recursive helper for
        :func:`Bcfg2.Server.Plugin.helpers.StructFile.Match` """
        if self._include_element(item, metadata, *args):
            if item.tag in self._include_tests.keys():
                rv = []
                if self._include_element(item, metadata, *args):
                    for child in item.iterchildren():
                        rv.extend(self._match(child, metadata, *args))
                return rv
            else:
                rv = copy.deepcopy(item)
                for child in rv.iterchildren():
                    rv.remove(child)
                for child in item.iterchildren():
                    rv.extend(self._match(child, metadata, *args))
                return [rv]
        else:
            return []

    def _do_match(self, metadata, *args):
        """ Helper for
        :func:`Bcfg2.Server.Plugin.helpers.StructFile.Match` that lets
        a subclass of StructFile easily redefine the public Match()
        interface to accept a different number of arguments.  This
        provides a sane prototype for the Match() function while
        keeping the internals consistent. """
        rv = []
        if self.template is None:
            entries = self.entries
        else:
            entries = self._render(metadata).getchildren()
        for child in entries:
            rv.extend(self._match(child, metadata, *args))
        return rv

    def Match(self, metadata):
        """ Return matching fragments of the data in this file.  A tag
        is considered to match if all ``<Group>`` and ``<Client>``
        tags that are its ancestors match the metadata given.  Since
        tags are included unmodified, it's possible for a tag to
        itself match while containing non-matching children.
        Consequently, only the tags contained in the list returned by
        Match() (and *not* their descendents) should be considered to
        match the metadata.

        Match() returns matching fragments in document order.

        :param metadata: Client metadata to match against.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: list of lxml.etree._Element objects """
        return self._do_match(metadata)

    def _xml_match(self, item, metadata, *args):
        """ recursive helper for
        :func:`Bcfg2.Server.Plugin.helpers.StructFile.XMLMatch` """
        if self._include_element(item, metadata, *args):
            if item.tag in self._include_tests.keys():
                for child in item.iterchildren():
                    item.remove(child)
                    item.getparent().append(child)
                    self._xml_match(child, metadata, *args)
                if item.text:
                    if item.getparent().text is None:
                        item.getparent().text = item.text
                    else:
                        item.getparent().text += item.text
                item.getparent().remove(item)
            else:
                for child in item.iterchildren():
                    self._xml_match(child, metadata, *args)
        else:
            item.getparent().remove(item)

    def _do_xmlmatch(self, metadata, *args):
        """ Helper for
        :func:`Bcfg2.Server.Plugin.helpers.StructFile.XMLMatch` that lets
        a subclass of StructFile easily redefine the public Match()
        interface to accept a different number of arguments.  This
        provides a sane prototype for the Match() function while
        keeping the internals consistent. """
        if self.template is None:
            rv = copy.deepcopy(self.xdata)
        else:
            rv = self._render(metadata)
        for child in rv.iterchildren():
            self._xml_match(child, metadata, *args)
        return rv

    def XMLMatch(self, metadata):
        """ Return a rebuilt XML document that only contains the
        matching portions of the original file.  A tag is considered
        to match if all ``<Group>`` and ``<Client>`` tags that are its
        ancestors match the metadata given.  Unlike :func:`Match`, the
        document returned by XMLMatch will only contain matching data.
        All ``<Group>`` and ``<Client>`` tags will have been stripped
        out.

        The new document produced by XMLMatch() is not necessarily in
        the same order as the original document.

        :param metadata: Client metadata to match against.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: lxml.etree._Element """
        return self._do_xmlmatch(metadata)


class InfoXML(StructFile):
    """ InfoXML files contain Group, Client, and Path tags to set the
    metadata (permissions, owner, etc.) of files. """
    encryption = False

    _include_tests = copy.copy(StructFile._include_tests)
    _include_tests['Path'] = lambda el, md, entry, *args: \
        entry.get('realname', entry.get('name')) == el.get("name")

    def Match(self, metadata, entry):  # pylint: disable=W0221
        """ Implementation of
        :func:`Bcfg2.Server.Plugin.helpers.StructFile.Match` that
        considers Path tags to allow ``info.xml`` files to set
        different file metadata for different file paths. """
        return self._do_match(metadata, entry)

    def XMLMatch(self, metadata, entry):  # pylint: disable=W0221
        """ Implementation of
        :func:`Bcfg2.Server.Plugin.helpers.StructFile.XMLMatch` that
        considers Path tags to allow ``info.xml`` files to set
        different file metadata for different file paths. """
        return self._do_xmlmatch(metadata, entry)

    def BindEntry(self, entry, metadata):
        """ Bind the matching file metadata for this client and entry
        to the entry.

        :param entry: The abstract entry to bind the info to. This
                      will be modified in place
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to get info for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        fileinfo = self.Match(metadata, entry)
        if len(fileinfo) == 0:
            raise PluginExecutionError("No metadata found in %s for %s" %
                                       (self.name, entry.get('name')))
        elif len(fileinfo) > 1:
            self.logger.warning("Multiple file metadata found in %s for %s" %
                                (self.name, entry.get('name')))
        for attr, val in fileinfo[0].attrib.items():
            entry.set(attr, val)


class XMLDirectoryBacked(DirectoryBacked):
    """ :class:`Bcfg2.Server.Plugin.helpers.DirectoryBacked` for XML files. """

    #: Only track and include files whose names (not paths) match this
    #: compiled regex.
    patterns = re.compile(r'^.*\.xml$')

    #: The type of child objects to create for files contained within
    #: the directory that is tracked.  Default is
    #: :class:`Bcfg2.Server.Plugin.helpers.XMLFileBacked`
    __child__ = XMLFileBacked


class PriorityStructFile(StructFile):
    """ A StructFile where each file has a priority, given as a
    top-level XML attribute. """

    def __init__(self, filename, should_monitor=False):
        StructFile.__init__(self, filename, should_monitor=should_monitor)
        self.priority = -1
    __init__.__doc__ = StructFile.__init__.__doc__

    def Index(self):
        StructFile.Index(self)
        try:
            self.priority = int(self.xdata.get('priority'))
        except (ValueError, TypeError):
            raise PluginExecutionError("Got bogus priority %s for file %s" %
                                       (self.xdata.get('priority'), self.name))
    Index.__doc__ = StructFile.Index.__doc__


class PrioDir(Plugin, Generator, XMLDirectoryBacked):
    """ PrioDir handles a directory of XML files where each file has a
    set priority.

    .. -----
    .. autoattribute:: __child__
    """

    #: The type of child objects to create for files contained within
    #: the directory that is tracked.  Default is
    #: :class:`Bcfg2.Server.Plugin.helpers.PriorityStructFile`
    __child__ = PriorityStructFile

    def __init__(self, core):
        Plugin.__init__(self, core)
        Generator.__init__(self)
        XMLDirectoryBacked.__init__(self, self.data)
    __init__.__doc__ = Plugin.__init__.__doc__

    def HandleEvent(self, event):
        XMLDirectoryBacked.HandleEvent(self, event)
        self.Entries = {}
        for src in self.entries.values():
            for child in src.xdata.iterchildren():
                if child.tag in ['Group', 'Client']:
                    continue
                if child.tag not in self.Entries:
                    self.Entries[child.tag] = dict()
                self.Entries[child.tag][child.get("name")] = self.BindEntry
    HandleEvent.__doc__ = XMLDirectoryBacked.HandleEvent.__doc__

    def _matches(self, entry, metadata, candidate):  # pylint: disable=W0613
        """ Whether or not a given candidate matches the abstract
        entry given.  By default this does strict matching (i.e., the
        entry name matches the candidate name), but this can be
        overridden to provide regex matching, etc.

        :param entry: The entry to find a match for
        :type entry: lxml.etree._Element
        :param metadata: The metadata to get attributes for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :candidate: A candidate concrete entry to match with
        :type candidate: lxml.etree._Element
        :returns: bool
        """
        return (entry.tag == candidate.tag and
                entry.get('name') == candidate.get('name'))

    def BindEntry(self, entry, metadata):
        """ Bind the attributes that apply to an entry to it.  The
        entry is modified in-place.

        :param entry: The entry to add attributes to.
        :type entry: lxml.etree._Element
        :param metadata: The metadata to get attributes for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        matching = []
        for src in self.entries.values():
            for candidate in src.XMLMatch(metadata).xpath("//%s" % entry.tag):
                if self._matches(entry, metadata, candidate):
                    matching.append((src, candidate))
        if len(matching) == 0:
            raise PluginExecutionError("No matching source for entry when "
                                       "retrieving attributes for %s:%s" %
                                       (entry.tag, entry.get('name')))
        elif len(matching) == 1:
            data = matching[0][1]
        else:
            prio = [int(m[0].priority) for m in matching]
            priority = max(prio)
            if prio.count(priority) > 1:
                msg = "Found conflicting sources with same priority (%s) " \
                    "for %s:%s for %s" % (priority, entry.tag,
                                          entry.get("name"), metadata.hostname)
                self.logger.error(msg)
                self.logger.error([m[0].name for m in matching])
                raise PluginExecutionError(msg)

            for src, candidate in matching:
                if int(src.priority) == priority:
                    data = candidate
                    break

        entry.text = data.text
        for item in data.getchildren():
            entry.append(copy.copy(item))

        for key, val in list(data.attrib.items()):
            if key not in entry.attrib:
                entry.attrib[key] = val


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


class SpecificData(Debuggable):
    """ A file that is specific to certain clients, groups, or all
    clients. """

    def __init__(self, name, specific):  # pylint: disable=W0613
        """
        :param name: The full path to the file
        :type name: string
        :param specific: A
                         :class:`Bcfg2.Server.Plugin.helpers.Specificity`
                         object describing what clients this file
                         applies to.
        :type specific: Bcfg2.Server.Plugin.helpers.Specificity
        """
        Debuggable.__init__(self)
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
            self.logger.error("Failed to read file %s" % self.name)


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

    def __init__(self, basename, path, entry_type):
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

        The ``entry_type`` callable must have the following signature::

            entry_type(filepath, specificity)

        Where the parameters are:

        :param filepath: Full path to file
        :type filepath: string
        :param specific: A
                         :class:`Bcfg2.Server.Plugin.helpers.Specificity`
                         object describing what clients this file
                         applies to.
        :type specific: Bcfg2.Server.Plugin.helpers.Specificity

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
        self.metadata = default_path_metadata()
        self.infoxml = None

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

    def set_debug(self, debug):
        rv = Debuggable.set_debug(self, debug)
        for entry in self.entries.values():
            entry.set_debug(debug)
        return rv

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

        if event.filename == 'info.xml':
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
            self.entries[event.filename] = entry_type(fpath, spec)
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
        """ Process changes to or creation of info.xml files for the
        EntrySet.

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

    def reset_metadata(self, event):
        """ Reset metadata to defaults if info.xml is removed.

        :param event: An event that applies to an info handled by this
                      EntrySet
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        if event.filename == 'info.xml':
            self.infoxml = None

    def bind_info_to_entry(self, entry, metadata):
        """ Bind the metadata for the given client in the base
        info.xml for this EntrySet to the entry.

        :param entry: The abstract entry to bind the info to. This
                      will be modified in place
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to get info for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        for attr, val in list(self.metadata.items()):
            entry.set(attr, val)
        if self.infoxml is not None:
            self.infoxml.BindEntry(entry, metadata)

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

    def __init__(self, core):
        Plugin.__init__(self, core)
        Generator.__init__(self)

        self.fam = Bcfg2.Server.FileMonitor.get_fam()

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
                                              self.es_child_cls)
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
            reqid = self.fam.AddMonitor(name, self)
            self.handles[reqid] = relative
