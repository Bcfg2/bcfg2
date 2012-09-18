""" ``_Collection`` objects represent the set of
:class:`Bcfg2.Server.Plugins.Packages.Source.Source` objects that apply
to a given client, and can be used to query all software repositories
for a client in aggregate.  In some cases this can give faster or more
accurate results.

In most cases, ``_Collection`` methods have been designed to defer the
call to the Sources in the ``_Collection`` and aggregate the results
as appropriate.  The simplest ``_Collection`` implemention is thus
often a simple subclass that adds no additional functionality.

Overriding Methods
------------------

As noted above, the ``_Collection`` object is written expressly so
that you can subclass it and override no methods or attributes, and it
will work by deferring all calls to the Source objects it contains.
If you do choose to override methods, there are two approaches:

#. Keep :func:`_Collection.complete` intact, and override the methods
   it calls: :func:`_Collection.is_package`,
   :func:`_Collection.is_virtual_package`,
   :func:`_Collection.get_deps`, :func:`_Collection.get_provides`,
   :func:`_Collection.get_vpkgs`, and :func:`_Collection.setup_data`.

#. Provide your own implementation of :func:`_Collection.complete`, in
   which case you do not have to override the above methods.  You may
   want to override :func:`_Collection.packages_from_entry`,
   :func:`_Collection.packages_to_entry`, and
   :func:`_Collection.get_new_packages`.

In either case, you may want to override
:func:`_Collection.get_groups`, :func:`_Collection.get_group`,
:func:`_Collection.get_essential`, :func:`_Collection.get_config`,
:func:`_Collection.filter_unknown`, and
:func:`_Collection.build_extra_structures`.

.. _pkg-objects:

Conversion Between Package Objects and XML Entries
--------------------------------------------------

_Collection objects have to translate Bcfg2 entries,
:class:`lxml.etree._Element` objects, into objects suitable for use by
the backend for resolving dependencies.  This is handled by two
functions:

* :func:`_Collection.packages_from_entry` is called to translate an
  XML entry into a list of packages;
* :func:`_Collection.packages_to_entry` is called to translate a list
  of packages back into an XML entry.

Because of this translation layer, the return type of any functions
below that return packages (e.g., :func:`_Collection.get_group`) is
actually indeterminate; they must return an object suitable for
passing to :func:`_Collection.packages_to_entry`.  Similarly,
functions that take a package as an argument (e.g.,
:func:`_Collection.is_package`) take the appropriate package object.
In the documentation below, the actual parameter return type (usually
.``string``) used in this base implementation is noted, as well as this
fact.

The Collection Module
---------------------
"""

import sys
import copy
import logging
import lxml.etree
import Bcfg2.Server.Plugin
from Bcfg2.Compat import any, md5

LOGGER = logging.getLogger(__name__)

#: We cache _Collection objects in ``COLLECTIONS`` so that calling
#: :func:`Bcfg2.Server.Plugins.Packages.Packages.Refresh` or
#: :func:`Bcfg2.Server.Plugins.Packages.Packages.Reload` can tell the
#: collection objects to clean up their cache, but we don't actually
#: use the cache to return a _Collection object when one is requested,
#: because that prevents new machines from working, since a
#: _Collection object gets created by
#: :func:`Bcfg2.Server.Plugins.Packages.Packages.get_additional_data`,
#: which is called for all clients at server startup.  (It would also
#: prevent machines that change groups from working properly; e.g., if
#: you reinstall a machine with a new OS, then returning a cached
#: _Collection object would give the wrong sources to that client.)
#: These are keyed by the collection :attr:`_Collection.cachekey`, a
#: unique key identifying the collection by its *config*, which could
#: be shared among multiple clients.
COLLECTIONS = dict()

#: CLIENTS is a cache mapping of hostname ->
#: :attr:`_Collection.cachekey`.  This _is_ used to return a
#: _Collection object when one is requested, so each entry is very
#: short-lived -- it's purged at the end of each client run.
CLIENTS = dict()


class _Collection(list, Bcfg2.Server.Plugin.Debuggable):
    """ ``_Collection`` objects represent the set of
    :class:`Bcfg2.Server.Plugins.Packages.Source` objects that apply
    to a given client, and can be used to query all software
    repositories for a client in aggregate.  In some cases this can
    give faster or more accurate results.

    Note that the name of this class starts with an underscore; the
    factory function :func:`Collection` must be used to instantiate
    the correct subclass of ``_Collection`` when creating an actual
    collection object. """

    #: Whether or not this Packages backend supports package groups
    __package_groups__ = False

    def __init__(self, metadata, sources, basepath, debug=False):
        """ Don't call ``__init__`` directly; use :func:`Collection`
        to instantiate a new ``_Collection`` object.

        :param metadata: The client metadata for this collection
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param sources: A list of all sources known to the server that
                        will be used to generate the list of sources
                        that apply to this client
        :type sources: list of
                       :class:`Bcfg2.Server.Plugins.Packages.Source.Source`
                       objects
        :param basepath: The base filesystem path where cache and
                         other temporary data will be stored
        :type basepath: string
        :param debug: Enable debugging output
        :type debug: bool
        """
        Bcfg2.Server.Plugin.Debuggable.__init__(self)
        list.__init__(self, sources)
        self.debug_flag = debug
        self.metadata = metadata
        self.basepath = basepath
        self.virt_pkgs = dict()

        try:
            self.setup = sources[0].setup
            self.cachepath = sources[0].basepath
            self.ptype = sources[0].ptype
        except IndexError:
            self.setup = None
            self.cachepath = None
            self.ptype = "unknown"

        self.cachefile = None

    @property
    def cachekey(self):
        """ A unique identifier for the set of sources contained in
        this ``_Collection`` object.  This is unique to a set of
        sources, **not** necessarily to the client, which lets clients
        with identical sources share cache data."""
        return md5(self.sourcelist().encode('UTF-8')).hexdigest()

    def get_config(self):
        """ Get the configuration for the package tool used by this
        source type.  This should be a config appropriate for use on
        either the server (to resolve dependencies) or the client.

        Subclasses must override this method.  By default it logs an
        error and returns the empty string.

        :returns: string """
        self.logger.error("Packages: Cannot generate config for host %s with "
                          "no sources or multiple source types" %
                          self.metadata.hostname)
        return ""

    def sourcelist(self):
        """ Get a human-readable list of sources in this collection,
        including some information about each source.

        :returns: string """
        srcs = []
        for source in self:
            for url_map in source.url_map:
                if url_map['arch'] not in self.metadata.groups:
                    continue
                reponame = source.get_repo_name(url_map)
                srcs.append("Name: %s" % reponame)
                srcs.append("  Type: %s" % source.ptype)
                if url_map['url']:
                    srcs.append("  URL: %s" % url_map['url'])
                elif url_map['rawurl']:
                    srcs.append("  RAWURL: %s" % url_map['rawurl'])
                if source.gpgkeys:
                    srcs.append("  GPG Key(s): %s" % ", ".join(source.gpgkeys))
                else:
                    srcs.append("  GPG Key(s): None")
                if len(source.blacklist):
                    srcs.append("  Blacklist: %s" %
                                ", ".join(source.blacklist))
                if len(source.whitelist):
                    srcs.append("  Whitelist: %s" %
                                ", ".join(source.whitelist))
                srcs.append("")
        return "\n".join(srcs)

    def get_relevant_groups(self):
        """ Get all groups that might be relevant to determining which
        sources apply to this collection's client.

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.get_relevant_groups`.

        :return: list of strings - group names"""
        groups = []
        for source in self:
            groups.extend(source.get_relevant_groups(self.metadata))
        return sorted(list(set(groups)))

    @property
    def basegroups(self):
        """ Get a list of group names used by this Collection type in
        resolution of
        :ref:`server-plugins-generators-packages-magic-groups`.

        The base implementation simply aggregates the results of
        :attr:`Bcfg2.Server.Plugins.Packages.Source.Source.basegroups`."""
        groups = set()
        for source in self:
            groups.update(source.basegroups)
        return list(groups)

    @property
    def cachefiles(self):
        """ Geta list of the full path to all cachefiles used by this
        collection.

        The base implementation simply aggregates the results of
        :attr:`Bcfg2.Server.Plugins.Packages.Source.Source.cachefiles`."""
        cachefiles = set([self.cachepath])
        for source in self:
            cachefiles.add(source.cachefile)
        return list(cachefiles)

    def get_groups(self, grouplist):
        """ Given a list of package group names, return a dict of
        ``<group name>: <list of packages>``.  This method is provided
        since some backends may be able to query multiple groups at
        once faster than serially.

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.get_groups`.

        :param grouplist: The list of groups to query
        :type grouplist: list of strings - group names
        :returns: dict of ``<group name>: <list of packages>``

        In this implementation the packages will be strings, but see
        :ref:`pkg-objects`."""
        rv = dict()
        for group, ptype in grouplist:
            rv[group] = self.get_group(group, ptype)
        return rv

    def get_group(self, group, ptype=None):
        """ Get the list of packages of the given type in a package
        group.

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.get_group`.

        :param group: The name of the group to query
        :type group: string
        :param ptype: The type of packages to get, for backends that
                      support multiple package types in package groups
                      (e.g., "recommended," "optional," etc.)
        :type ptype: string
        :returns: list of strings - package names, but see 
                  :ref:`pkg-objects`
        """
        if not self.__package_groups__:
            self.logger.error("Packages: Package groups are not supported by %s"
                              % self.__class__.__name__)
            return []

        for source in self:
            pkgs = source.get_group(self.metadata, group, ptype=ptype)
            if pkgs:
                return pkgs
        self.logger.warning("Packages: '%s' is not a valid group" % group)
        return []

    def is_package(self, package):
        """ Return True if a package is a package, False otherwise.

        The base implementation returns True if any Source object's
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.is_package`
        returns True.

        :param package: The name of the package, but see :ref:`pkg-objects`
        :type package: string
        :returns: bool
        """
        return any(source.is_package(self.metadata, package)
                   for source in self)

    def is_virtual_package(self, package):
        """ Return True if a name is a virtual package (i.e., is a
        symbol provided by a real package), False otherwise.

        The base implementation returns True if any Source object's
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.is_virtual_package`
        returns True.

        :param package: The name of the symbol, but see :ref:`pkg-objects`
        :type package: string
        :returns: bool
        """
        return any(source.is_virtual_package(self.metadata, package)
                   for source in self)

    def get_deps(self, package):
        """ Get a list of the dependencies of the given package.

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.get_deps`.

        :param package: The name of the symbol, but see :ref:`pkg-objects`
        :type package: string
        :returns: list of strings, but see :ref:`pkg-objects`
        """
        for source in self:
            if source.is_package(self.metadata, package):
                return source.get_deps(self.metadata, package)
        return []

    def get_essential(self):
        """ Get a list of packages that are essential to the repository.

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.get_essential`.

        :returns: list of strings, but see :ref:`pkg-objects`
        """
        essential = set()
        for source in self:
            essential |= source.essentialpkgs
        return essential

    def get_provides(self, package):
        """ Get a list of all symbols provided by the given package.

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.get_provides`.

        :param package: The name of the package, but see :ref:`pkg-objects`
        :type package: string
        :returns: list of strings, but see :ref:`pkg-objects`
        """
        for source in self:
            providers = source.get_provides(self.metadata, package)
            if providers:
                return providers
        return []

    def get_vpkgs(self):
        """ Get a list of all virtual packages provided by all sources.

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.get_vpkgs`.

        :returns: list of strings, but see :ref:`pkg-objects`
        """
        vpkgs = dict()
        for source in self:
            s_vpkgs = source.get_vpkgs(self.metadata)
            for name, prov_set in list(s_vpkgs.items()):
                if name not in vpkgs:
                    vpkgs[name] = set(prov_set)
                else:
                    vpkgs[name].update(prov_set)
        return vpkgs

    def filter_unknown(self, unknown):
        """ After :func:`complete`, filter out packages that appear in
        the list of unknown packages but should not be presented to
        the user.  E.g., packages that you expect to be unknown.

        :param unknown: A set of unknown packages.  The set should be
                        modified in place.
        :type unknown: set of strings, but see :ref:`pkg-objects`
        """
        for source in self:
            source.filter_unknown(unknown)

    def magic_groups_match(self):
        """ Returns True if the client's
        :ref:`server-plugins-generators-packages-magic-groups` match
        the magic groups for any of the sources contained in this
        Collection.

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.magic_groups_match`.

        :returns: bool
        """
        return any(s.magic_groups_match(self.metadata) for s in self)

    def build_extra_structures(self, independent):
        """ Add additional entries to the ``<Independent/>`` section
        of the final configuration.  This can be used to handle, e.g.,
        GPG keys and other entries besides packages that need to be
        handled for a complete client configuration.

        :param independent: The XML tag to add extra entries to.  This
                            should be modified in place.
        :type independent: lxml.etree._Element
        """
        pass

    def get_additional_data(self):
        """ Get additional Connector data to be supplied to
        :func:`Bcfg2.Server.Plugins.Packages.Packages.get_additional_data`
        (and thence to client metadata objects).

        The base implementation simply aggregates the results of
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.get_additional_data`

        :returns: list of additional Connector data
        """
        sdata = []
        for source in self:
            sdata.extend(copy.deepcopy(source.url_map))
        return sdata

    def setup_data(self, force_update=False):
        """ Do any collection-level data setup tasks. This is called
        when sources are loaded or reloaded by
        :class:`Bcfg2.Server.Plugins.Packages.Packages`.

        The base implementation is a no-op; the child
        :class:`Bcfg2.Server.Plugins.Packages.Source.Source` objects
        will handle all data setup.

        :param force_update: Ignore all local cache and setup data
                             from its original upstream sources (i.e.,
                             the package repositories)
        :type force_update: bool
        """
        pass

    def packages_from_entry(self, entry):
        """ Given a Package or BoundPackage entry, get a list of the
        package(s) described by it in a format appropriate for passing
        to :func:`Bcfg2.Server.Plugins.Packages.Packages.complete`.
        By default, that's just the name; only the
        :mod:`Bcfg2.Server.Plugins.Packages.Yum` backend supports
        versions or other extended data. See :ref:`pkg-objects` for
        more details.

        :param entry: The XML entry describing the package or packages.
        :type entry: lxml.etree._Element
        :returns: list of strings, but see :ref:`pkg-objects`
        """
        return [entry.get("name")]

    def packages_to_entry(self, pkglist, entry):
        """ Given a list of package objects as returned by
        :func:`packages_from_entry` or
        :func:`Bcfg2.Server.Plugins.Packages.Packages.complete`,
        return an XML tree describing the BoundPackage entries that
        should be included in the client configuration. See
        :ref:`pkg-objects` for more details.

        :param pkglist: A list of packages as returned by 
                        :func:`Bcfg2.Server.Plugins.Packages.Packages.complete`
        :type pkglist: list of strings, but see :ref:`pkg-objects`
        :param entry: The base XML entry to add all of the Package
                      entries to.  This should be modified in place.
        :type entry: lxml.etree._Element
        """
        for pkg in pkglist:
            lxml.etree.SubElement(entry, 'BoundPackage', name=pkg,
                                  version=self.setup.cfp.get("packages",
                                                             "version",
                                                             default="auto"),
                                  type=self.ptype, origin='Packages')

    def get_new_packages(self, initial, complete):
        """ Compute the difference between the complete package list
        (as returned by
        :func:`Bcfg2.Server.Plugins.Packages.Packages.complete`) and
        the initial package list computed from the specification.
        This is necessary because the format may be different between
        the two lists due to :func:`packages_to_entry` and
        :func:`packages_from_entry`. See :ref:`pkg-objects` for more
        details.

        :param initial: The initial package list
        :type initial: set of strings, but see :ref:`pkg-objects`
        :param complete: The final package list
        :type complete: set of strings, but see :ref:`pkg-objects`
        :return: set of strings, but see :ref:`pkg-objects` - the set
                 of packages that are in ``complete`` but not in
                 ``initial``
        """
        return list(complete.difference(initial))

    def complete(self, packagelist):
        """ Build a complete list of all packages and their dependencies.

        :param packagelist: Set of initial packages computed from the
                            specification.
        :type packagelist: set of strings, but see :ref:`pkg-objects`
        :returns: tuple of sets - The first element contains a set of
                  strings (but see :ref:`pkg-objects`) describing the
                  complete package list, and the second element is a
                  set of symbols whose dependencies could not be
                  resolved.
        """
        # setup vpkg cache
        pgrps = tuple(self.get_relevant_groups())
        if pgrps not in self.virt_pkgs:
            self.virt_pkgs[pgrps] = self.get_vpkgs()
        vpkg_cache = self.virt_pkgs[pgrps]

        # unclassified is set of unsatisfied requirements (may be pkg
        # for vpkg)
        unclassified = set(packagelist)
        vpkgs = set()
        both = set()
        pkgs = set(packagelist)

        packages = set()
        examined = set()
        unknown = set()

        final_pass = False
        really_done = False
        # do while unclassified or vpkgs or both or pkgs
        while unclassified or pkgs or both or final_pass:
            if really_done:
                break
            if len(unclassified) + len(pkgs) + len(both) == 0:
                # one more pass then exit
                really_done = True

            while unclassified:
                current = unclassified.pop()
                examined.add(current)
                is_pkg = False
                if self.is_package(current):
                    is_pkg = True

                is_vpkg = current in vpkg_cache

                if is_pkg and is_vpkg:
                    both.add(current)
                elif is_pkg and not is_vpkg:
                    pkgs.add(current)
                elif is_vpkg and not is_pkg:
                    vpkgs.add(current)
                elif not is_vpkg and not is_pkg:
                    unknown.add(current)

            while pkgs:
                # direct packages; current can be added, and all deps
                # should be resolved
                current = pkgs.pop()
                self.debug_log("Packages: handling package requirement %s" %
                               current)
                packages.add(current)
                deps = self.get_deps(current)
                newdeps = set(deps).difference(examined)
                if newdeps:
                    self.debug_log("Packages: Package %s added requirements %s"
                                   % (current, newdeps))
                unclassified.update(newdeps)

            satisfied_vpkgs = set()
            for current in vpkgs:
                # virtual dependencies, satisfied if one of N in the
                # config, or can be forced if only one provider
                if len(vpkg_cache[current]) == 1:
                    self.debug_log("Packages: requirement %s satisfied by %s" %
                                   (current, vpkg_cache[current]))
                    unclassified.update(vpkg_cache[current].difference(examined))
                    satisfied_vpkgs.add(current)
                else:
                    satisfiers = [item for item in vpkg_cache[current]
                                  if item in packages]
                    self.debug_log("Packages: requirement %s satisfied by %s" %
                                   (current, satisfiers))
                    satisfied_vpkgs.add(current)
            vpkgs.difference_update(satisfied_vpkgs)

            satisfied_both = set()
            for current in both:
                # packages that are both have virtual providers as
                # well as a package with that name. allow use of virt
                # through explicit specification, then fall back to
                # forcing current on last pass
                satisfiers = [item for item in vpkg_cache[current]
                              if item in packages]
                if satisfiers:
                    self.debug_log("Packages: requirement %s satisfied by %s" %
                                   (current, satisfiers))
                    satisfied_both.add(current)
                elif current in packagelist or final_pass:
                    pkgs.add(current)
                    satisfied_both.add(current)
            both.difference_update(satisfied_both)

            if len(unclassified) + len(pkgs) == 0:
                final_pass = True
            else:
                final_pass = False

            self.filter_unknown(unknown)
        return packages, unknown


def _get_collection_class(source_type):
    """ Given a source type, determine the class of _Collection object
    that should be used to contain these sources.  Note that
    ``source_type`` is *not* a
    :class:`Bcfg2.Server.Plugins.Packages.Source.Source` subclass;
    it's the name of a source type as given in ``sources.xml``.

    :param source_type: The type of source, e.g., "yum" or "apt"
    :type source_type: string
    :returns: type - the _Collection subclass that should be used to
              instantiate an object to contain sources of the given type. """
    modname = "Bcfg2.Server.Plugins.Packages.%s" % source_type.title()
    try:
        module = sys.modules[modname]
    except KeyError:
        try:
            module = __import__(modname).Server.Plugins.Packages
        except ImportError:
            msg = "Packages: Unknown source type %s" % source_type
            LOGGER.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

    try:
        cclass = getattr(module, source_type.title() + "Collection")
    except AttributeError:
        msg = "Packages: No collection class found for %s sources" % source_type
        LOGGER.error(msg)
        raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
    return cclass


def clear_cache():
    """ Clear the caches kept by this
    module. (:attr:`Bcfg2.Server.Plugins.Packages.Collection.COLLECTIONS`
    and:attr:`Bcfg2.Server.Plugins.Packages.Collection.CLIENTS`) """
    global COLLECTIONS, CLIENTS  # pylint: disable=W0603
    COLLECTIONS = dict()
    CLIENTS = dict()


def Collection(metadata, sources, basepath, debug=False):
    """ Object factory for subclasses of
    :class:`Bcfg2.Server.Plugins.Packages.Collection._Collection`.

    :param metadata: The client metadata to create a _Collection
                     object for
    :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
    :param sources: A list of all sources known to the server that
                    will be used to generate the list of sources that
                    apply to this client
    :type sources: list of
                   :class:`Bcfg2.Server.Plugins.Packages.Source.Source`
                   objects
    :param basepath: The base filesystem path where cache and other
                     temporary data will be stored
    :type basepath: string
    :param debug: Enable debugging output
    :type debug: bool
    :return: An instance of the appropriate subclass of
             :class:`Bcfg2.Server.Plugins.Packages.Collection._Collection`
             that contains all relevant sources that apply to the
             given client
    """
    global COLLECTIONS  # pylint: disable=W0602

    if not sources.loaded:
        # if sources.xml has not received a FAM event yet, defer;
        # instantiate a dummy _Collection object
        return _Collection(metadata, [], basepath)

    if metadata.hostname in CLIENTS:
        return COLLECTIONS[CLIENTS[metadata.hostname]]

    sclasses = set()
    relevant = list()

    for source in sources:
        if source.applies(metadata):
            relevant.append(source)
            sclasses.update([source.__class__])

    if len(sclasses) > 1:
        LOGGER.warning("Packages: Multiple source types found for %s: %s" %
                       ",".join([s.__name__ for s in sclasses]))
        cclass = _Collection
    elif len(sclasses) == 0:
        LOGGER.error("Packages: No sources found for %s" % metadata.hostname)
        cclass = _Collection
    else:
        cclass = _get_collection_class(sclasses.pop().__name__.replace("Source",
                                                                       ""))

    if debug:
        LOGGER.error("Packages: Using %s for Collection of sources for %s" %
                     (cclass.__name__, metadata.hostname))

    collection = cclass(metadata, relevant, basepath, debug=debug)
    ckey = collection.cachekey
    CLIENTS[metadata.hostname] = ckey
    COLLECTIONS[ckey] = collection
    return collection
