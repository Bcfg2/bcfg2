""" Packages resolves Package entries on the Bcfg2 server in order to
present a complete list of Package entries to the client in order to
determine the completeness of the client configuration. """

import os
import sys
import glob
import shutil
import lxml.etree
import Bcfg2.Logger
import Bcfg2.Server.Plugin
from Bcfg2.Compat import ConfigParser, urlopen, HTTPError, URLError
from Bcfg2.Server.Plugins.Packages.Collection import Collection, \
    get_collection_class
from Bcfg2.Server.Plugins.Packages.PackagesSources import PackagesSources

#: The default path for generated yum configs
YUM_CONFIG_DEFAULT = "/etc/yum.repos.d/bcfg2.repo"

#: The default path for generated apt configs
APT_CONFIG_DEFAULT = \
    "/etc/apt/sources.list.d/bcfg2-packages-generated-sources.list"


class Packages(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.StructureValidator,
               Bcfg2.Server.Plugin.Generator,
               Bcfg2.Server.Plugin.Connector,
               Bcfg2.Server.Plugin.ClientRunHooks):
    """ Packages resolves Package entries on the Bcfg2 server in order
    to present a complete list of Package entries to the client in
    order to determine the completeness of the client configuration.
    It does so by delegating control of package version information to
    a number of backends, which may parse repository metadata directly
    or defer to package manager libraries for truly dynamic
    resolution.

    .. private-include: _build_packages"""

    #: Packages is an alternative to
    #: :mod:`Bcfg2.Server.Plugins.Pkgmgr` and conflicts with it.
    conflicts = ['Pkgmgr']

    #: Packages exposes two additional XML-RPC calls, :func:`Refresh`
    #: and :func:`Reload`
    __rmi__ = Bcfg2.Server.Plugin.Plugin.__rmi__ + ['Refresh', 'Reload']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.StructureValidator.__init__(self)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.ClientRunHooks.__init__(self)

        #: Packages does a potentially tremendous amount of on-disk
        #: caching.  ``cachepath`` holds the base directory to where
        #: data should be cached.
        self.cachepath = \
            self.core.setup.cfp.get("packages", "cache",
                                    default=os.path.join(self.data, 'cache'))

        #: Where Packages should store downloaded GPG key files
        self.keypath = os.path.join(self.cachepath, 'keys')
        if not os.path.exists(self.keypath):
            # create key directory if needed
            os.makedirs(self.keypath)

        # warn about deprecated magic groups
        if self.core.setup.cfp.getboolean("packages", "magic_groups",
                                          default=False):
            self.logger.warning("Packages: Magic groups are deprecated and "
                                "will be removed in a future release")
            self.logger.warning("You can disable magic groups by setting "
                                "magic_groups=0 in [packages] in bcfg2.conf")

        # pylint: disable=C0301
        #: The
        #: :class:`Bcfg2.Server.Plugins.Packages.PackagesSources.PackagesSources`
        #: object used to generate
        #: :class:`Bcfg2.Server.Plugins.Packages.Source.Source` objects for
        #: this plugin.
        self.sources = PackagesSources(os.path.join(self.data, "sources.xml"),
                                       self.cachepath, core.fam, self,
                                       self.core.setup)

        #: We cache
        #: :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
        #: objects in ``collections`` so that calling :func:`Refresh`
        #: or :func:`Reload` can tell the collection objects to clean
        #: up their cache, but we don't actually use the cache to
        #: return a ``Collection`` object when one is requested,
        #: because that prevents new machines from working, since a
        #: ``Collection`` object gets created by
        #: :func:`get_additional_data`, which is called for all
        #: clients at server startup and various other times.  (It
        #: would also prevent machines that change groups from working
        #: properly; e.g., if you reinstall a machine with a new OS,
        #: then returning a cached ``Collection`` object would give
        #: the wrong sources to that client.)  These are keyed by the
        #: collection
        #: :attr:`Bcfg2.Server.Plugins.Packages.Collection.Collection.cachekey`,
        #: a unique key identifying the collection by its *config*,
        #: which could be shared among multiple clients.
        self.collections = dict()

        #: clients is a cache mapping of hostname ->
        #: :attr:`Bcfg2.Server.Plugins.Packages.Collection.Collection.cachekey`
        #: Unlike :attr:`collections`, this _is_ used to return a
        #: :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
        #: object when one is requested, so each entry is very
        #: short-lived -- it's purged at the end of each client run.
        self.clients = dict()
        # pylint: enable=C0301

    __init__.__doc__ = Bcfg2.Server.Plugin.Plugin.__init__.__doc__

    def set_debug(self, debug):
        rv = Bcfg2.Server.Plugin.Plugin.set_debug(self, debug)
        self.sources.set_debug(debug)
        for collection in self.collections.values():
            collection.set_debug(debug)
        return rv
    set_debug.__doc__ = Bcfg2.Server.Plugin.Plugin.set_debug.__doc__

    @property
    def disableResolver(self):
        """ Report the state of the resolver.  This can be disabled in
        the configuration.  Note that disabling metadata (see
        :attr:`disableMetaData`) implies disabling the resolver.

        This property cannot be set. """
        if self.disableMetaData:
            # disabling metadata without disabling the resolver Breaks
            # Things
            return True
        try:
            return not self.core.setup.cfp.getboolean("packages", "resolver")
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return False
        except ValueError:
            # for historical reasons we also accept "enabled" and
            # "disabled", which are not handled according to the
            # Python docs but appear to be handled properly by
            # ConfigParser in at least some versions
            return self.core.setup.cfp.get(
                "packages",
                "resolver",
                default="enabled").lower() == "disabled"

    @property
    def disableMetaData(self):
        """ Report whether or not metadata processing is enabled.

        This property cannot be set. """
        try:
            return not self.core.setup.cfp.getboolean("packages", "resolver")
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return False
        except ValueError:
            # for historical reasons we also accept "enabled" and
            # "disabled"
            return self.core.setup.cfp.get(
                "packages",
                "metadata",
                default="enabled").lower() == "disabled"

    def create_config(self, entry, metadata):
        """ Create yum/apt config for the specified client.

        :param entry: The base entry to bind.  This will be modified
                      in place.
        :type entry: lxml.etree._Element
        :param metadata: The client to create the config for.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        attrib = dict(encoding='ascii',
                      owner='root',
                      group='root',
                      type='file',
                      mode='0644',
                      important='true')

        collection = self.get_collection(metadata)
        entry.text = collection.get_config()
        for (key, value) in list(attrib.items()):
            entry.attrib.__setitem__(key, value)

    def get_config(self, metadata):
        """ Get yum/apt config, as a string, for the specified client.

        :param metadata: The client to create the config for.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        return self.get_collection(metadata).get_config()

    def HandleEntry(self, entry, metadata):
        """ Bind configuration entries.  ``HandleEntry`` handles
        entries two different ways:

        * All ``Package`` entries have their ``version`` and ``type``
          attributes set according to the appropriate
          :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
          object for this client.
        * ``Path`` entries are delegated to :func:`create_config`

        :param entry: The entry to bind
        :type entry: lxml.etree._Element
        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: lxml.etree._Element - The fully bound entry
        """
        if entry.tag == 'Package':
            collection = self.get_collection(metadata)
            entry.set('version', self.core.setup.cfp.get("packages",
                                                         "version",
                                                         default="auto"))
            entry.set('type', collection.ptype)
        elif entry.tag == 'Path':
            self.create_config(entry, metadata)
        return entry

    def HandlesEntry(self, entry, metadata):
        """ Determine if the given entry can be handled.  Packages
        handles two kinds of entries:

        * ``Package`` entries are handled if the client has any
          sources at all.
        * ``Path`` entries are handled if they match the paths that
          are handled by a backend that can produce client
          configurations, e.g., :attr:`YUM_CONFIG_DEFAULT`,
          :attr:`APT_CONFIG_DEFAULT`, or the overridden value of
          either of those from the configuration.

        :param entry: The entry to bind
        :type entry: lxml.etree._Element
        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: bool - Whether or not this plugin can handle the entry
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginExecutionError`
        """
        if entry.tag == 'Package':
            if self.core.setup.cfp.getboolean("packages", "magic_groups",
                                              default=False):
                collection = self.get_collection(metadata)
                if collection.magic_groups_match():
                    return True
            else:
                return True
        elif entry.tag == 'Path':
            # managed entries for yum/apt configs
            if (entry.get("name") ==
                self.core.setup.cfp.get("packages",
                                        "yum_config",
                                        default=YUM_CONFIG_DEFAULT) or
                entry.get("name") ==
                self.core.setup.cfp.get("packages",
                                        "apt_config",
                                        default=APT_CONFIG_DEFAULT)):
                return True
        return False

    @Bcfg2.Server.Plugin.track_statistics()
    def validate_structures(self, metadata, structures):
        """ Do the real work of Packages.  This does two things:

        #. Given the full list of all packages that apply to this
           client from the specification, calls
           :func:`_build_packages` to resolve dependencies, determine
           unknown packages (i.e., those that are not in any
           repository that applies to this client), and build a
           complete package list.

        #. Calls
           :func:`Bcfg2.Server.Plugins.Packages.Collection.Collection.build_extra_structures`
           to add any other extra data required by the backend (e.g.,
           GPG keys)

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param structures: A list of lxml.etree._Element objects
                           describing the structures (i.e., bundles)
                           for this client.  This can be modified in
                           place.
        :type structures: list of lxml.etree._Element objects
        :returns: None
        """
        collection = self.get_collection(metadata)
        indep = lxml.etree.Element('Independent')
        self._build_packages(metadata, indep, structures,
                             collection=collection)
        collection.build_extra_structures(indep)
        structures.append(indep)

    @Bcfg2.Server.Plugin.track_statistics()
    def _build_packages(self, metadata, independent, structures,
                        collection=None):
        """ Perform dependency resolution and build the complete list
        of packages that need to be included in the specification by
        :func:`validate_structures`, based on the initial list of
        packages.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param independent: The XML tag to add package entries
                            generated by dependency resolution to.
                            This will be modified in place.
        :type independent: lxml.etree._Element
        :param structures: A list of lxml.etree._Element objects
                           describing the structures (i.e., bundles)
                           for this client
        :type structures: list of lxml.etree._Element objects
        :param collection: The collection of sources for this client.
                           If none is given, one will be created with
                           :func:`get_collection`
        :type collection: Bcfg2.Server.Plugins.Packages.Collection.Collection
        """
        if self.disableResolver:
            # Config requests no resolver
            for struct in structures:
                for pkg in struct.xpath('//Package | //BoundPackage'):
                    if pkg.get("group"):
                        if pkg.get("type"):
                            pkg.set("choose", pkg.get("type"))
            return

        if collection is None:
            collection = self.get_collection(metadata)
        initial = set()
        to_remove = []
        groups = []
        for struct in structures:
            for pkg in struct.xpath('//Package | //BoundPackage'):
                if pkg.get("name"):
                    initial.update(collection.packages_from_entry(pkg))
                elif pkg.get("group"):
                    groups.append((pkg.get("group"),
                                   pkg.get("type")))
                    to_remove.append(pkg)
                else:
                    self.logger.error(
                        "Packages: Malformed Package: %s" %
                        lxml.etree.tostring(
                            pkg,
                            xml_declaration=False).decode('UTF-8'))

        # base is the set of initial packages explicitly given in the
        # specification, packages from expanded package groups, and
        # packages essential to the distribution
        base = set(initial)

        # remove package groups
        for el in to_remove:
            el.getparent().remove(el)

        gpkgs = collection.get_groups(groups)
        for pkgs in gpkgs.values():
            base.update(pkgs)

        # essential pkgs are those marked as such by the distribution
        base.update(collection.get_essential())

        packages, unknown = collection.complete(base)
        if unknown:
            self.logger.info("Packages: Got %d unknown entries" % len(unknown))
            self.logger.info("Packages: %s" % list(unknown))
        newpkgs = collection.get_new_packages(initial, packages)
        self.debug_log("Packages: %d base, %d complete, %d new" %
                       (len(base), len(packages), len(newpkgs)))
        newpkgs.sort()
        collection.packages_to_entry(newpkgs, independent)

    @Bcfg2.Server.Plugin.track_statistics()
    def Refresh(self):
        """ Packages.Refresh() => True|False

        Reload configuration specification and download sources """
        self._load_config(force_update=True)
        return True

    @Bcfg2.Server.Plugin.track_statistics()
    def Reload(self):
        """ Packages.Refresh() => True|False

        Reload configuration specification and sources """
        self._load_config()
        return True

    def _load_config(self, force_update=False):
        """
        Load the configuration data and setup sources

        :param force_update: Ignore all locally cached and downloaded
                             data and fetch the metadata anew from the
                             upstream repository.
        :type force_update: bool
        """
        self._load_sources(force_update)
        self._load_gpg_keys(force_update)

    def _load_sources(self, force_update):
        """ Load sources from the config, downloading if necessary.

        :param force_update: Ignore all locally cached and downloaded
                             data and fetch the metadata anew from the
                             upstream repository.
        :type force_update: bool
        """
        cachefiles = set()

        for collection in list(self.collections.values()):
            cachefiles.update(collection.cachefiles)
            if not self.disableMetaData:
                collection.setup_data(force_update)

        # clear Collection caches
        self.clients = dict()
        self.collections = dict()

        for source in self.sources.entries:
            cachefiles.add(source.cachefile)
            if not self.disableMetaData:
                source.setup_data(force_update)

        for cfile in glob.glob(os.path.join(self.cachepath, "cache-*")):
            if cfile not in cachefiles:
                try:
                    if os.path.isdir(cfile):
                        shutil.rmtree(cfile)
                    else:
                        os.unlink(cfile)
                except OSError:
                    err = sys.exc_info()[1]
                    self.logger.error("Packages: Could not remove cache file "
                                      "%s: %s" % (cfile, err))

    def _load_gpg_keys(self, force_update):
        """ Load GPG keys from the config, downloading if necessary.

        :param force_update: Ignore all locally cached and downloaded
                             data and fetch the metadata anew from the
                             upstream repository.
        :type force_update: bool
        """
        keyfiles = []
        keys = []
        for source in self.sources.entries:
            for key in source.gpgkeys:
                localfile = os.path.join(self.keypath,
                                         os.path.basename(key.rstrip("/")))
                if localfile not in keyfiles:
                    keyfiles.append(localfile)
                if ((force_update and key not in keys) or
                    not os.path.exists(localfile)):
                    self.logger.info("Packages: Downloading and parsing %s" %
                                     key)
                    try:
                        open(localfile, 'w').write(urlopen(key).read())
                        keys.append(key)
                    except (URLError, HTTPError):
                        err = sys.exc_info()[1]
                        self.logger.error("Packages: Error downloading %s: %s"
                                          % (key, err))
                    except IOError:
                        err = sys.exc_info()[1]
                        self.logger.error("Packages: Error writing %s to %s: "
                                          "%s" % (key, localfile, err))
                    except:
                        err = sys.exc_info()[1]
                        self.logger.error("Packages: Unknown error fetching "
                                          "%s: %s" % (key, err))

        for kfile in glob.glob(os.path.join(self.keypath, "*")):
            if kfile not in keyfiles:
                os.unlink(kfile)

    @Bcfg2.Server.Plugin.track_statistics()
    def get_collection(self, metadata):
        """ Get a
        :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
        object for this client.

        :param metadata: The client metadata to get a Collection for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: An instance of the appropriate subclass of
                  :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
                  that contains all relevant sources that apply to the
                  given client
        """

        if not self.sources.loaded:
            # if sources.xml has not received a FAM event yet, defer;
            # instantiate a dummy Collection object
            return Collection(metadata, [], self.cachepath, self.data,
                              self.core.fam)

        if metadata.hostname in self.clients:
            return self.collections[self.clients[metadata.hostname]]

        sclasses = set()
        relevant = list()

        for source in self.sources.entries:
            if source.applies(metadata):
                relevant.append(source)
                sclasses.update([source.__class__])

        if len(sclasses) > 1:
            self.logger.warning("Packages: Multiple source types found for "
                                "%s: %s" %
                                (metadata.hostname,
                                 ",".join([s.__name__ for s in sclasses])))
            cclass = Collection
        elif len(sclasses) == 0:
            self.logger.error("Packages: No sources found for %s" %
                              metadata.hostname)
            cclass = Collection
        else:
            cclass = get_collection_class(
                sclasses.pop().__name__.replace("Source", ""))

        if self.debug_flag:
            self.logger.error("Packages: Using %s for Collection of sources "
                              "for %s" % (cclass.__name__, metadata.hostname))

        collection = cclass(metadata, relevant, self.cachepath, self.data,
                            self.core.fam, debug=self.debug_flag)
        ckey = collection.cachekey
        if cclass != Collection:
            self.clients[metadata.hostname] = ckey
            self.collections[ckey] = collection
        return collection

    def get_additional_data(self, metadata):
        """ Return additional data for the given client.  This will be
        a dict containing a single key, ``sources``, whose value is a
        list of data returned from
        :func:`Bcfg2.Server.Plugins.Packages.Collection.Collection.get_additional_data`,
        namely, a list of
        :attr:`Bcfg2.Server.Plugins.Packages.Source.Source.url_map`
        data.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :return: dict of lists of ``url_map`` data
        """
        collection = self.get_collection(metadata)
        return dict(sources=collection.get_additional_data(),
                    get_config=self.get_config)

    def end_client_run(self, metadata):
        """ Hook to clear the cache for this client in
        :attr:`clients`, which must persist only the duration of a
        client run.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        if metadata.hostname in self.clients:
            del self.clients[metadata.hostname]

    def end_statistics(self, metadata):
        """ Hook to clear the cache for this client in :attr:`clients`
        once statistics are processed to ensure that a stray cached
        :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
        object is not built during statistics and preserved until a
        subsequent client run.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        self.end_client_run(metadata)
