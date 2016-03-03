"""This module implements a config file repository."""

import re
import os
import sys
import errno
import operator
import lxml.etree
import Bcfg2.Options
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugin import PluginExecutionError
# pylint: disable=W0622
from Bcfg2.Compat import u_str, unicode, b64encode, any, walk_packages
# pylint: enable=W0622

try:
    import Bcfg2.Server.Encryption
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

_handlers = [m[1]  # pylint: disable=C0103
             for m in walk_packages(path=__path__)]

_CFG = None


def get_cfg():
    """ Get the :class:`Bcfg2.Server.Plugins.Cfg.Cfg` plugin object
    created by the Bcfg2 core.  This is provided so that the handler
    objects can access it as necessary, since the existing
    :class:`Bcfg2.Server.Plugin.helpers.GroupSpool` and
    :class:`Bcfg2.Server.Plugin.helpers.EntrySet` classes have no
    facility for passing it otherwise."""
    return _CFG


class CfgBaseFileMatcher(Bcfg2.Server.Plugin.SpecificData):
    """ .. currentmodule:: Bcfg2.Server.Plugins.Cfg

    CfgBaseFileMatcher is the parent class for all Cfg handler
    objects. """

    #: The set of filenames handled by this handler.  If
    #: ``__basenames__`` is the empty list, then the basename of each
    #: :class:`CfgEntrySet` is used -- i.e., the name of the directory
    #: that contains the file is used for the basename.
    __basenames__ = []

    #: This handler only handles files with the listed extensions
    #: (which come *after* :attr:`CfgBaseFileMatcher.__specific__`
    #: indicators).
    __extensions__ = []

    #: This handler ignores all files with the listed extensions.  A
    #: file that is ignored by a handler will not be handled by any
    #: other handlers; that is, a file is ignored if any handler
    #: ignores it.  Ignoring a file is not simply a means to defer
    #: handling of that file to another handler.
    __ignore__ = []

    #: Whether or not the files handled by this handler are permitted
    #: to have specificity indicators in their filenames -- e.g.,
    #: ``.H_client.example.com`` or ``.G10_foogroup``.
    __specific__ = True

    #: Cfg handlers are checked in ascending order of priority to see
    #: if they handle a given event.  If this explicit priority is not
    #: set, then :class:`CfgPlaintextGenerator.CfgPlaintextGenerator`
    #: would match against nearly every other sort of generator file
    #: if it comes first.  It's not necessary to set ``__priority__``
    #: on handlers where :attr:`CfgBaseFileMatcher.__specific__` is
    #: False, since they don't have a potentially open-ended regex
    __priority__ = 0

    #: Flag to indicate a deprecated handler.
    deprecated = False

    #: Flag to indicate an experimental handler.
    experimental = False

    def __init__(self, name, specific):
        if not self.__specific__ and not specific:
            specific = Bcfg2.Server.Plugin.Specificity(all=True)
        Bcfg2.Server.Plugin.SpecificData.__init__(self, name, specific)
    __init__.__doc__ = Bcfg2.Server.Plugin.SpecificData.__init__.__doc__ + \
        """
.. -----
.. autoattribute:: CfgBaseFileMatcher.__basenames__
.. autoattribute:: CfgBaseFileMatcher.__extensions__
.. autoattribute:: CfgBaseFileMatcher.__ignore__
.. autoattribute:: CfgBaseFileMatcher.__specific__
.. autoattribute:: CfgBaseFileMatcher.__priority__ """

    @classmethod
    def get_regex(cls, basenames):
        """ Get a compiled regular expression to match filenames (not
        full paths) that this handler handles.

        :param basename: The base filename to use if
                         :attr:`CfgBaseFileMatcher.__basenames__`
                         is not defined (i.e., the name of the
                         directory that contains the files the regex
                         will be applied to)
        :type basename: string
        :returns: compiled regex
        """
        components = ['^(?P<basename>%s)' % '|'.join(re.escape(b)
                                                     for b in basenames)]
        if cls.__specific__:
            components.append(r'(|\.H_(?P<hostname>\S+?)|' +
                              r'\.G(?P<prio>\d+)_(?P<group>\S+?))')
        if cls.__extensions__:
            components.append(r'\.(?P<extension>%s)' %
                              r'|'.join(cls.__extensions__))
        components.append(r'$')
        return re.compile("".join(components))

    @classmethod
    def handles(cls, event, basename=None):
        """ Return True if this handler handles the file described by
        ``event``.  This is faster than just applying
        :func:`CfgBaseFileMatcher.get_regex`
        because it tries to do non-regex matching first.

        :param event: The FAM event to check
        :type event: Bcfg2.Server.FileMonitor.Event
        :param basename: The base filename to use if
                         :attr:`CfgBaseFileMatcher.__basenames__`
                         is not defined (i.e., the name of the
                         directory that contains the files the regex
                         will be applied to)
        :type basename: string
        :returns: bool - True if this handler handles the file listed
                  in the event, False otherwise.
        """
        if cls.__basenames__:
            basenames = cls.__basenames__
        else:
            basenames = [os.path.basename(basename)]

        return bool(cls.get_regex(basenames).match(event.filename))

    @classmethod
    def ignore(cls, event, basename=None):  # pylint: disable=W0613
        """ Return True if this handler ignores the file described by
        ``event``.  See
        :attr:`CfgBaseFileMatcher.__ignore__`
        for more information on how ignoring files works.

        :param event: The FAM event to check
        :type event: Bcfg2.Server.FileMonitor.Event
        :param basename: The base filename to use if
                         :attr:`CfgBaseFileMatcher.__basenames__`
                         is not defined (i.e., the name of the
                         directory that contains the files the regex
                         will be applied to)
        :type basename: string
        :returns: bool - True if this handler handles the file listed
                  in the event, False otherwise.
        """
        return any(event.filename.endswith("." + e) for e in cls.__ignore__)

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, self.name)


class CfgGenerator(CfgBaseFileMatcher):
    """ CfgGenerators generate the initial content of a file. Every
    valid :class:`Bcfg2.Server.Plugins.Cfg.CfgEntrySet` must have at
    least one file handled by a CfgGenerator.  Moreover, each
    CfgEntrySet must have one unambiguously best handler for each
    client. See :class:`Bcfg2.Server.Plugin.helpers.EntrySet` for more
    details on how the best handler is chosen."""

    def __init__(self, name, specific):
        # we define an __init__ that just calls the parent __init__,
        # so that we can set the docstring on __init__ to something
        # different from the parent __init__ -- namely, the parent
        # __init__ docstring, minus everything after ``.. -----``,
        # which we use to delineate the actual docs from the
        # .. autoattribute hacks we have to do to get private
        # attributes included in sphinx 1.0 """
        CfgBaseFileMatcher.__init__(self, name, specific)
    __init__.__doc__ = CfgBaseFileMatcher.__init__.__doc__.split(".. -----")[0]

    def get_data(self, entry, metadata):  # pylint: disable=W0613
        """ get_data() returns the initial data of a file.

        :param entry: The entry to generate data for. ``entry`` should
                      not be modified in-place.
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to generate data for.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: string - the contents of the entry
        """
        return self.data


class CfgFilter(CfgBaseFileMatcher):
    """ CfgFilters modify the initial content of a file after it has
    been generated by a :class:`Bcfg2.Server.Plugins.Cfg.CfgGenerator`. """

    def __init__(self, name, specific):
        # see comment on CfgGenerator.__init__ above
        CfgBaseFileMatcher.__init__(self, name, specific)
    __init__.__doc__ = CfgBaseFileMatcher.__init__.__doc__.split(".. -----")[0]

    def modify_data(self, entry, metadata, data):
        """ Return new data for the entry, based on the initial data
        produced by the :class:`Bcfg2.Server.Plugins.Cfg.CfgGenerator`.

        :param entry: The entry to filter data for. ``entry`` should
                      not be modified in-place.
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to filter data for.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param data: The initial contents of the entry produced by the
                      CfgGenerator
        :type data: string
        :returns: string - the new contents of the entry
        """
        raise NotImplementedError


class CfgInfo(CfgBaseFileMatcher):
    """ CfgInfo handlers provide metadata (owner, group, paranoid,
    etc.) for a file entry. """

    #: Whether or not the files handled by this handler are permitted
    #: to have specificity indicators in their filenames -- e.g.,
    #: ``.H_client.example.com`` or ``.G10_foogroup``.  By default
    #: CfgInfo handlers do not allow specificities
    __specific__ = False

    def __init__(self, fname):
        """
        :param name: The full path to the file
        :type name: string

        .. -----
        .. autoattribute:: Bcfg2.Server.Plugins.Cfg.CfgInfo.__specific__
        """
        CfgBaseFileMatcher.__init__(self, fname, None)

    def bind_info_to_entry(self, entry, metadata):
        """ Assign the appropriate attributes to the entry, modifying
        it in place.

        :param entry: The abstract entry to bind the info to
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to get info for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        raise NotImplementedError


class CfgVerifier(CfgBaseFileMatcher):
    """ CfgVerifier handlers validate entry data once it has been
    generated, filtered, and info applied.  Validation can be enabled
    or disabled in the configuration.  Validation can apply to the
    contents of an entry, the attributes on it (e.g., owner, group,
    etc.), or both.
    """

    def __init__(self, name, specific):
        # see comment on CfgGenerator.__init__ above
        CfgBaseFileMatcher.__init__(self, name, specific)
    __init__.__doc__ = CfgBaseFileMatcher.__init__.__doc__.split(".. -----")[0]

    def verify_entry(self, entry, metadata, data):
        """ Perform entry contents. validation.

        :param entry: The entry to validate data for. ``entry`` should
                      not be modified in-place.  Info attributes have
                      been bound to the entry, but the text data has
                      not been set.
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to validate data for.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param data: The contents of the entry
        :type data: string
        :returns: None
        :raises: :exc:`Bcfg2.Server.Plugins.Cfg.CfgVerificationError`
        """
        raise NotImplementedError


class CfgCreator(CfgBaseFileMatcher):
    """ CfgCreator handlers create static entry data if no generator
    was found to generate any.  A CfgCreator runs at most once per
    client, writes its data to disk as a static file, and is not
    called on subsequent runs by the same client. """

    #: CfgCreators generally store their configuration in a single XML
    #: file, and are thus not specific
    __specific__ = False

    def __init__(self, fname):
        """
        :param name: The full path to the file
        :type name: string

        .. -----
        .. autoattribute:: Bcfg2.Server.Plugins.Cfg.CfgInfo.__specific__
        """
        CfgBaseFileMatcher.__init__(self, fname, None)

    def create_data(self, entry, metadata):
        """ Create new data for the given entry and write it to disk
        using :func:`Bcfg2.Server.Plugins.Cfg.CfgCreator.write_data`.

        :param entry: The entry to create data for.
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to create data for.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: string - The contents of the entry
        :raises: :exc:`Bcfg2.Server.Plugins.Cfg.CfgCreationError`
        """
        raise NotImplementedError

    def get_filename(self, host=None, group=None, prio=0, ext=''):
        """ Get the filename where the new data will be written.  If
        ``host`` is given, it will be host-specific.  It will be
        group-specific if ``group`` and ``prio`` are given.  If
        neither ``host`` nor ``group`` is given, the filename will be
        non-specific. In general, this will be called as::

            self.get_filename(**self.get_specificity(metadata))

        :param host: The file applies to the given host
        :type host: bool
        :param group: The file applies to the given group
        :type group: string
        :param prio: The file has the given priority relative to other
                     objects that also apply to the same group.
                     ``group`` must also be specified.
        :type prio: int
        :param ext: An extension to add after the specificity (e.g.,
                    '.crypt', to signal that an encrypted file has
                    been created)
        :type prio: string
        :returns: string - the filename
        """
        basefilename = \
            os.path.join(os.path.dirname(self.name),
                         os.path.basename(os.path.dirname(self.name)))
        if group:
            return "%s.G%02d_%s%s" % (basefilename, prio, group, ext)
        elif host:
            return "%s.H_%s%s" % (basefilename, host, ext)
        else:
            return "%s%s" % (basefilename, ext)

    def write_data(self, data, host=None, group=None, prio=0, ext=''):
        """ Write the new data to disk.  If ``host`` is given, it is
        written as a host-specific file, or as a group-specific file
        if ``group`` and ``prio`` are given.  If neither ``host`` nor
        ``group`` is given, it will be written as a non-specific file.
        In general, this will be called as::

            self.write_data(data, **self.get_specificity(metadata))

        :param data: The data to write
        :type data: string
        :param host: The data applies to the given host
        :type host: bool
        :param group: The data applies to the given group
        :type group: string
        :param prio: The data has the given priority relative to other
                     objects that also apply to the same group.
                     ``group`` must also be specified.
        :type prio: int
        :param ext: An extension to add after the specificity (e.g.,
                    '.crypt', to signal that an encrypted file has
                    been created)
        :type prio: string
        :returns: None
        :raises: :exc:`Bcfg2.Server.Plugins.Cfg.CfgCreationError`
        """
        fileloc = self.get_filename(host=host, group=group, prio=prio, ext=ext)
        self.debug_log("Cfg: Writing new file %s" % fileloc)
        try:
            os.makedirs(os.path.dirname(fileloc))
        except OSError:
            err = sys.exc_info()[1]
            if err.errno != errno.EEXIST:
                raise CfgCreationError("Could not create parent directories "
                                       "for %s: %s" % (fileloc, err))

        try:
            open(fileloc, 'wb').write(data)
        except IOError:
            err = sys.exc_info()[1]
            raise CfgCreationError("Could not write %s: %s" % (fileloc, err))


class XMLCfgCreator(CfgCreator,  # pylint: disable=W0223
                    Bcfg2.Server.Plugin.StructFile):
    """ A CfgCreator that uses XML to describe how data should be
    generated. """

    #: Whether or not the created data from this class can be
    #: encrypted
    encryptable = True

    #: Encryption and creation settings can be stored in bcfg2.conf,
    #: either under the [cfg] section, or under the named section.
    cfg_section = None

    def __init__(self, name):
        CfgCreator.__init__(self, name)
        Bcfg2.Server.Plugin.StructFile.__init__(self, name)

    def handle_event(self, event):
        CfgCreator.handle_event(self, event)
        Bcfg2.Server.Plugin.StructFile.HandleEvent(self, event)

    @property
    def passphrase(self):
        """ The passphrase used to encrypt created data """
        if self.cfg_section:
            localopt = "%s_passphrase" % self.cfg_section
            passphrase = getattr(Bcfg2.Options.setup, localopt,
                                 Bcfg2.Options.setup.cfg_passphrase)
        else:
            passphrase = Bcfg2.Options.setup.cfg_passphrase
        if passphrase is None:
            return None
        try:
            return Bcfg2.Options.setup.passphrases[passphrase]
        except KeyError:
            raise CfgCreationError("%s: No such passphrase: %s" %
                                   (self.__class__.__name__, passphrase))

    @property
    def category(self):
        """ The category to which created data is specific """
        if self.cfg_section:
            localopt = "%s_category" % self.cfg_section
            return getattr(Bcfg2.Options.setup, localopt,
                           Bcfg2.Options.setup.cfg_category)
        else:
            return Bcfg2.Options.setup.cfg_category

    def write_data(self, data, host=None, group=None, prio=0, ext=''):
        if HAS_CRYPTO and self.encryptable and self.passphrase:
            self.debug_log("Cfg: Encrypting created data")
            data = Bcfg2.Server.Encryption.ssl_encrypt(data, self.passphrase)
            ext = '.crypt'
        CfgCreator.write_data(self, data, host=host, group=group, prio=prio,
                              ext=ext)

    def get_specificity(self, metadata):
        """ Get config settings for key generation specificity
        (per-host or per-group).

        :param metadata: The client metadata to create data for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: dict - A dict of specificity arguments suitable for
                  passing to
                  :func:`Bcfg2.Server.Plugins.Cfg.CfgCreator.write_data`
                  or
                  :func:`Bcfg2.Server.Plugins.Cfg.CfgCreator.get_filename`
        """
        category = self.xdata.get("category", self.category)
        if category is None:
            per_host_default = "true"
        else:
            per_host_default = "false"
        per_host = self.xdata.get("perhost",
                                  per_host_default).lower() == "true"

        specificity = dict(host=metadata.hostname)
        if category and not per_host:
            group = metadata.group_in_category(category)
            if group:
                specificity = dict(group=group,
                                   prio=int(self.xdata.get("priority", 50)))
            else:
                self.logger.info("Cfg: %s has no group in category %s, "
                                 "creating host-specific data" %
                                 (metadata.hostname, category))
        return specificity


class CfgVerificationError(Exception):
    """ Raised by
    :func:`Bcfg2.Server.Plugins.Cfg.CfgVerifier.verify_entry` when an
    entry fails verification """
    pass


class CfgCreationError(Exception):
    """ Raised by
    :func:`Bcfg2.Server.Plugins.Cfg.CfgCreator.create_data` when data
    creation fails """
    pass


class CfgDefaultInfo(CfgInfo):
    """ :class:`Bcfg2.Server.Plugins.Cfg.Cfg` handler that supplies a
    default set of file metadata """

    def __init__(self):
        CfgInfo.__init__(self, '')
    __init__.__doc__ = CfgInfo.__init__.__doc__.split(".. -----")[0]

    def bind_info_to_entry(self, entry, _):
        for key, value in Bcfg2.Server.Plugin.default_path_metadata().items():
            entry.attrib[key] = value
    bind_info_to_entry.__doc__ = CfgInfo.bind_info_to_entry.__doc__


class CfgEntrySet(Bcfg2.Server.Plugin.EntrySet):
    """ Handle a collection of host- and group-specific Cfg files with
    multiple different Cfg handlers in a single directory. """

    def __init__(self, basename, path, entry_type):
        Bcfg2.Server.Plugin.EntrySet.__init__(self, basename, path, entry_type)
        self.specific = None
    __init__.__doc__ = Bcfg2.Server.Plugin.EntrySet.__doc__

    def set_debug(self, debug):
        rv = Bcfg2.Server.Plugin.EntrySet.set_debug(self, debug)
        for entry in self.entries.values():
            entry.set_debug(debug)
        return rv

    def handle_event(self, event):
        """ Dispatch a FAM event to :func:`entry_init` or the
        appropriate child handler object.

        :param event: An event that applies to a file handled by this
                      CfgEntrySet
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
        action = event.code2str()

        if event.filename not in self.entries:
            if action not in ['exists', 'created', 'changed']:
                # process a bogus changed event like a created
                return

            for hdlr in Bcfg2.Options.setup.cfg_handlers:
                if hdlr.handles(event, basename=self.path):
                    if action == 'changed':
                        # warn about a bogus 'changed' event, but
                        # handle it like a 'created'
                        self.logger.warning("Got %s event for unknown file %s"
                                            % (action, event.filename))
                    self.debug_log("%s handling %s event on %s" %
                                   (hdlr.__name__, action, event.filename))
                    self.entry_init(event, hdlr)
                    return
                elif hdlr.ignore(event, basename=self.path):
                    return
        # we only get here if event.filename in self.entries, so handle
        # created event like changed
        elif action == 'changed' or action == 'created':
            self.entries[event.filename].handle_event(event)
            return
        elif action == 'deleted':
            del self.entries[event.filename]
            return

        self.logger.error("Could not process event %s for %s; ignoring" %
                          (action, event.filename))

    def get_matching(self, metadata):
        return self.get_handlers(metadata, CfgGenerator)
    get_matching.__doc__ = Bcfg2.Server.Plugin.EntrySet.get_matching.__doc__

    def entry_init(self, event, hdlr):  # pylint: disable=W0221
        """ Handle the creation of a file on the filesystem and the
        creation of a Cfg handler object in this CfgEntrySet to track
        it.

        :param event: An event that applies to a file handled by this
                      CfgEntrySet
        :type event: Bcfg2.Server.FileMonitor.Event
        :param hdlr: The Cfg handler class to be used to create an
                     object for the file described by ``event``
        :type hdlr: class
        :returns: None
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.SpecificityError`
        """
        fpath = os.path.join(self.path, event.filename)
        if hdlr.__basenames__:
            fdesc = "/".join(hdlr.__basenames__)
        elif hdlr.__extensions__:
            fdesc = "." + "/.".join(hdlr.__extensions__)
        if hdlr.deprecated:
            self.logger.warning("Cfg: %s: Use of %s files is deprecated" %
                                (fpath, fdesc))
        elif hdlr.experimental:
            self.logger.warning("Cfg: %s: Use of %s files is experimental" %
                                (fpath, fdesc))

        if hdlr.__specific__:
            if hdlr.__basenames__:
                # specific entry with explicit basenames
                basenames = hdlr.__basenames__
            else:
                # specific entry with no explicit basename; use the
                # directory name as the basename
                basenames = [os.path.basename(self.path)]
            Bcfg2.Server.Plugin.EntrySet.entry_init(
                self, event, entry_type=hdlr,
                specific=hdlr.get_regex(basenames))
        else:
            if event.filename in self.entries:
                self.logger.warn("Got duplicate add for %s" % event.filename)
            else:
                self.entries[event.filename] = hdlr(fpath)
            self.entries[event.filename].handle_event(event)

    def bind_entry(self, entry, metadata):
        self.bind_info_to_entry(entry, metadata)
        data, generator = self._generate_data(entry, metadata)

        if generator is not None:
            # apply no filters if the data was created by a CfgCreator
            for fltr in self.get_handlers(metadata, CfgFilter):
                if fltr.specific <= generator.specific:
                    # only apply filters that are as specific or more
                    # specific than the generator used for this entry.
                    # Note that specificity comparison is backwards in
                    # this sense, since it's designed to sort from
                    # most specific to least specific.
                    data = fltr.modify_data(entry, metadata, data)

        if Bcfg2.Options.setup.cfg_validation:
            try:
                self._validate_data(entry, metadata, data)
            except CfgVerificationError:
                raise PluginExecutionError("Failed to verify %s for %s: %s" %
                                           (entry.get('name'),
                                            metadata.hostname,
                                            sys.exc_info()[1]))

        if entry.get('encoding') == 'base64':
            data = b64encode(data)
        else:
            try:
                if not isinstance(data, unicode):
                    if not isinstance(data, str):
                        data = data.decode('utf-8')
                    data = u_str(data, Bcfg2.Options.setup.encoding)
            except UnicodeDecodeError:
                msg = "Failed to decode %s: %s" % (entry.get('name'),
                                                   sys.exc_info()[1])
                self.logger.error(msg)
                self.logger.error("Please verify you are using the proper "
                                  "encoding")
                raise PluginExecutionError(msg)
            except ValueError:
                msg = "Error in specification for %s: %s" % (entry.get('name'),
                                                             sys.exc_info()[1])
                self.logger.error(msg)
                self.logger.error("You need to specify base64 encoding for %s"
                                  % entry.get('name'))
                raise PluginExecutionError(msg)
            except TypeError:
                # data is already unicode; newer versions of Cheetah
                # seem to return unicode
                pass

        if data:
            entry.text = data
        else:
            entry.set('empty', 'true')
        return entry
    bind_entry.__doc__ = Bcfg2.Server.Plugin.EntrySet.bind_entry.__doc__

    def get_handlers(self, metadata, handler_type):
        """ Get all handlers of the given type for the given metadata.

        :param metadata: The metadata to get all handlers for.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param handler_type: The type of Cfg handler to get
        :type handler_type: type
        :returns: list of Cfg handler classes
        """
        rv = []
        for ent in self.entries.values():
            if (isinstance(ent, handler_type) and
                    (not ent.__specific__ or ent.specific.matches(metadata))):
                rv.append(ent)
        return rv

    def bind_info_to_entry(self, entry, metadata):
        """ Bind entry metadata to the entry with the best CfgInfo
        handler

        :param entry: The abstract entry to bind the info to. This
                      will be modified in place
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to get info for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        """
        info_handlers = self.get_handlers(metadata, CfgInfo)
        CfgDefaultInfo().bind_info_to_entry(entry, metadata)
        if len(info_handlers) > 1:
            self.logger.error("More than one info supplier found for %s: %s" %
                              (entry.get("name"), info_handlers))
        if len(info_handlers):
            info_handlers[0].bind_info_to_entry(entry, metadata)
        if entry.tag == 'Path':
            entry.set('type', 'file')

    def _create_data(self, entry, metadata):
        """ Create data for the given entry on the given client

        :param entry: The abstract entry to create data for.  This
                      will not be modified
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to create data for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: string - the data for the entry
        """
        creator = self.best_matching(metadata,
                                     self.get_handlers(metadata, CfgCreator))

        try:
            return creator.create_data(entry, metadata)
        except CfgCreationError:
            raise PluginExecutionError("Cfg: Error creating data for %s: %s" %
                                       (entry.get("name"), sys.exc_info()[1]))

    def _generate_data(self, entry, metadata):
        """ Generate data for the given entry on the given client

        :param entry: The abstract entry to generate data for.  This
                      will not be modified
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to generate data for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: tuple of (string, generator) - the data for the
                  entry and the generator used to generate it (or
                  None, if data was created)
        """
        try:
            generator = self.best_matching(metadata,
                                           self.get_handlers(metadata,
                                                             CfgGenerator))
        except PluginExecutionError:
            # if no creators or generators exist, _create_data()
            # raises an appropriate exception
            return (self._create_data(entry, metadata), None)

        try:
            return (generator.get_data(entry, metadata), generator)
        except:
            # TODO: the exceptions raised by ``get_data`` are not
            # constrained in any way, so for now this needs to be a
            # blanket except.
            msg = "Cfg: Error rendering %s: %s" % (entry.get("name"),
                                                   sys.exc_info()[1])
            self.logger.error(msg)
            raise PluginExecutionError(msg)

    def _validate_data(self, entry, metadata, data):
        """ Validate data for the given entry on the given client

        :param entry: The abstract entry to validate data for
        :type entry: lxml.etree._Element
        :param metadata: The client metadata validate data for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: None
        :raises: :exc:`Bcfg2.Server.Plugins.Cfg.CfgVerificationError`
        """
        verifiers = self.get_handlers(metadata, CfgVerifier)
        # we can have multiple verifiers, but we only want to use the
        # best matching verifier of each class
        verifiers_by_class = dict()
        for verifier in verifiers:
            cls = verifier.__class__.__name__
            if cls not in verifiers_by_class:
                verifiers_by_class[cls] = [verifier]
            else:
                verifiers_by_class[cls].append(verifier)
        for verifiers in verifiers_by_class.values():
            verifier = self.best_matching(metadata, verifiers)
            verifier.verify_entry(entry, metadata, data)

    def list_accept_choices(self, entry, metadata):
        '''return a list of candidate pull locations'''
        generators = [ent for ent in list(self.entries.values())
                      if (isinstance(ent, CfgGenerator) and
                          ent.specific.matches(metadata))]
        if not generators:
            msg = "No base file found for %s" % entry.get('name')
            self.logger.error(msg)
            raise PluginExecutionError(msg)

        rv = []
        try:
            best = self.best_matching(metadata, generators)
            rv.append(best.specific)
        except PluginExecutionError:
            pass

        if not rv or not rv[0].hostname:
            rv.append(
                Bcfg2.Server.Plugin.Specificity(hostname=metadata.hostname))
        return rv

    def build_filename(self, specific):
        """ Create a filename for pulled file data """
        bfname = self.path + '/' + self.path.split('/')[-1]
        if specific.all:
            return bfname
        elif specific.group:
            return "%s.G%02d_%s" % (bfname, specific.prio, specific.group)
        elif specific.hostname:
            return "%s.H_%s" % (bfname, specific.hostname)

    def write_update(self, specific, new_entry, log):
        """ Write pulled data to the filesystem """
        if 'text' in new_entry:
            name = self.build_filename(specific)
            if os.path.exists("%s.genshi" % name):
                msg = "Cfg: Unable to pull data for genshi types"
                self.logger.error(msg)
                raise PluginExecutionError(msg)
            elif os.path.exists("%s.cheetah" % name):
                msg = "Cfg: Unable to pull data for cheetah types"
                self.logger.error(msg)
                raise PluginExecutionError(msg)
            try:
                etext = new_entry['text'].encode(Bcfg2.Options.setup.encoding)
            except UnicodeDecodeError:
                msg = "Cfg: Cannot encode content of %s as %s" % \
                    (name, Bcfg2.Options.setup.encoding)
                self.logger.error(msg)
                raise PluginExecutionError(msg)
            open(name, 'w').write(etext)
            self.debug_log("Wrote file %s" % name, flag=log)
        badattr = [attr for attr in ['owner', 'group', 'mode']
                   if attr in new_entry]
        if badattr:
            metadata_updates = {}
            metadata_updates.update(self.metadata)
            for attr in badattr:
                metadata_updates[attr] = new_entry.get(attr)
            infoxml = lxml.etree.Element('FileInfo')
            infotag = lxml.etree.SubElement(infoxml, 'Info')
            for attr in metadata_updates:
                infotag.attrib.__setitem__(attr, metadata_updates[attr])
            ofile = open(self.path + "/info.xml", "w")
            ofile.write(lxml.etree.tostring(infoxml, xml_declaration=False,
                                            pretty_print=True).decode('UTF-8'))
            ofile.close()
            self.debug_log("Wrote file %s" % os.path.join(self.path,
                                                          "info.xml"),
                           flag=log)


class CfgHandlerAction(Bcfg2.Options.ComponentAction):
    """ Option parser action to load Cfg handlers """
    bases = ['Bcfg2.Server.Plugins.Cfg']


class Cfg(Bcfg2.Server.Plugin.GroupSpool,
          Bcfg2.Server.Plugin.PullTarget):
    """ The Cfg plugin provides a repository to describe configuration
    file contents for clients. In its simplest form, the Cfg repository is
    just a directory tree modeled off of the directory tree on your client
    machines. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    es_cls = CfgEntrySet
    es_child_cls = Bcfg2.Server.Plugin.SpecificData

    options = Bcfg2.Server.Plugin.GroupSpool.options + [
        Bcfg2.Options.BooleanOption(
            '--cfg-validation', cf=('cfg', 'validation'), default=True,
            dest="cfg_validation",
            help='Run validation on Cfg files'),
        Bcfg2.Options.Option(
            cf=('cfg', 'category'), dest="cfg_category",
            help='The default name of the metadata category that created data '
            'is specific to'),
        Bcfg2.Options.Option(
            cf=('cfg', 'passphrase'), dest="cfg_passphrase",
            help='The default passphrase name used to encrypt created data'),
        Bcfg2.Options.Option(
            cf=("cfg", "handlers"), dest="cfg_handlers",
            help="Cfg handlers to load",
            type=Bcfg2.Options.Types.comma_list, action=CfgHandlerAction,
            default=_handlers)]

    def __init__(self, core):
        global _CFG  # pylint: disable=W0603
        Bcfg2.Server.Plugin.GroupSpool.__init__(self, core)
        Bcfg2.Server.Plugin.PullTarget.__init__(self)
        Bcfg2.Options.setup.cfg_handlers.sort(
            key=operator.attrgetter("__priority__"))
        _CFG = self
    __init__.__doc__ = Bcfg2.Server.Plugin.GroupSpool.__init__.__doc__

    def has_generator(self, entry, metadata):
        """ Return True if the given entry can be generated for the
        given metadata; False otherwise

        :param entry: Determine if a
                      :class:`Bcfg2.Server.Plugins.Cfg.CfgGenerator`
                      object exists that handles this (abstract) entry
        :type entry: lxml.etree._Element
        :param metadata: Determine if a CfgGenerator has data that
                         applies to this client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: bool
        """
        if entry.get('name') not in self.entries:
            return False

        return bool(self.entries[entry.get('name')].get_handlers(metadata,
                                                                 CfgGenerator))

    def AcceptChoices(self, entry, metadata):
        return self.entries[entry.get('name')].list_accept_choices(entry,
                                                                   metadata)
    AcceptChoices.__doc__ = \
        Bcfg2.Server.Plugin.PullTarget.AcceptChoices.__doc__

    def AcceptPullData(self, specific, new_entry, log):
        return self.entries[new_entry.get('name')].write_update(specific,
                                                                new_entry,
                                                                log)
    AcceptPullData.__doc__ = \
        Bcfg2.Server.Plugin.PullTarget.AcceptPullData.__doc__
