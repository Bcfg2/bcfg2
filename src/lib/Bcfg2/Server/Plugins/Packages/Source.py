""" ``Source`` objects represent a single <Source> tag in
``sources.xml``.  Note that a single Source tag can itself describe
multiple repositories (if it uses the "url" attribute instead of
"rawurl"), and so can the ``Source`` object.  This can be the source
(har har) of some confusion.  See
:func:`Bcfg2.Server.Plugins.Packages.Collection.Collection.sourcelist`
for the proper way to get all repos from a ``Source`` object.

Source objects are aggregated into
:class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
objects, which are actually called by
:class:`Bcfg2.Server.Plugins.Packages.Packages`.  This way a more
advanced subclass can query repositories in aggregate rather than
individually, which may give faster or more accurate results.

The base ``Source`` object must be subclassed to handle each
repository type.  How you subclass ``Source`` will depend on how you
subclassed
:class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`; see
:mod:`Bcfg2.Server.Plugins.Packages.Collection` for more details on
different methods for doing that.

If you are using the stock (or a near-stock)
:class:`Bcfg2.Server.Plugins.Packages.Collection.Collection` object,
then you will need to implement the following methods and attributes
in your ``Source`` subclass:

* :func:`Source.urls`
* :func:`Source.read_files`
* :attr:`Source.basegroups`

Additionally, you may want to consider overriding the following
methods and attributes:

* :func:`Source.is_virtual_package`
* :func:`Source.get_group`
* :attr:`Source.unknown_filter`
* :attr:`Source.load_state`
* :attr:`Source.save_state`

For an example of this kind of ``Source`` object, see
:mod:`Bcfg2.Server.Plugins.Packages.Apt`.

If you are overriding the ``Collection`` object in more depth, then
you have more leeway in what you might want to override or implement
in your ``Source`` subclass.  For an example of this kind of
``Source`` object, see :mod:`Bcfg2.Server.Plugins.Packages.Yum`.
"""

import os
import re
import sys
import Bcfg2.Server.Plugin
from Bcfg2.Compat import HTTPError, HTTPBasicAuthHandler, \
    HTTPPasswordMgrWithDefaultRealm, install_opener, build_opener, urlopen, \
    cPickle, md5


def fetch_url(url):
    """ Return the content of the given URL.

    :param url: The URL to fetch content from.
    :type url: string
    :raises: ValueError - Malformed URL
    :raises: URLError - Failure fetching URL
    :returns: string - the content of the page at the given URL """
    if '@' in url:
        mobj = re.match(r'(\w+://)([^:]+):([^@]+)@(.*)$', url)
        if not mobj:
            raise ValueError("Invalid URL")
        user = mobj.group(2)
        passwd = mobj.group(3)
        url = mobj.group(1) + mobj.group(4)
        auth = HTTPBasicAuthHandler(HTTPPasswordMgrWithDefaultRealm())
        auth.add_password(None, url, user, passwd)
        install_opener(build_opener(auth))
    return urlopen(url).read()


class SourceInitError(Exception):
    """ Raised when a :class:`Source` object fails instantiation. """
    pass


#: A regular expression used to determine the base name of a repo from
#: its URL.  This is used when generating repo configs and by
#: :func:`Source.get_repo_name`.  It handles `Pulp
#: <http://www.pulpproject.org/>`_ and `mrepo
#: <http://dag.wieers.com/home-made/mrepo/>`_ repositories specially,
#: and otherwise grabs the last component of the URL (as delimited by
#: slashes).
REPO_RE = re.compile(r'(?:pulp/repos/|/RPMS\.|/)([^/]+)/?$')


class Source(Bcfg2.Server.Plugin.Debuggable):  # pylint: disable=R0902
    """ ``Source`` objects represent a single <Source> tag in
    ``sources.xml``.  Note that a single Source tag can itself
    describe multiple repositories (if it uses the "url" attribute
    instead of "rawurl"), and so can the ``Source`` object.

    Note that a number of the attributes of this object may be more or
    less specific to one backend (e.g., :attr:`essentialpkgs`,
    :attr:`recommended`, :attr:`gpgkeys`, but they are included in the
    superclass to make the parsing of sources from XML more
    consistent, and to make it trivial for other backends to support
    those features.
    """

    #: The list of
    #: :ref:`server-plugins-generators-packages-magic-groups` that
    #: make sources of this type available to clients.
    basegroups = []

    #: The Package type handled by this Source class.  The ``type``
    #: attribute of Package entries will be set to the value ``ptype``
    #: when they are handled by :mod:`Bcfg2.Server.Plugins.Packages`.
    ptype = None

    def __init__(self, basepath, xsource, setup):  # pylint: disable=R0912
        """
        :param basepath: The base filesystem path under which cache
                         data for this source should be stored
        :type basepath: string
        :param xsource: The XML tag that describes this source
        :type source: lxml.etree._Element
        :param setup: A Bcfg2 options dict
        :type setup: dict
        :raises: :class:`Bcfg2.Server.Plugins.Packages.Source.SourceInitError`
        """
        Bcfg2.Server.Plugin.Debuggable.__init__(self)

        #: The base filesystem path under which cache data for this
        #: source should be stored
        self.basepath = basepath

        #: The XML tag that describes this source
        self.xsource = xsource

        #: A Bcfg2 options dict
        self.setup = setup

        #: A set of package names that are deemed "essential" by this
        #: source
        self.essentialpkgs = set()

        #: A list of the text of all 'Component' attributes of this
        #: source from XML
        self.components = [item.text for item in xsource.findall('Component')]

        #: A list of the arches supported by this source
        self.arches = [item.text for item in xsource.findall('Arch')]

        #: A list of the the names of packages that are blacklisted
        #: from this source
        self.blacklist = [item.text for item in xsource.findall('Blacklist')]

        #: A list of the the names of packages that are whitelisted in
        #: this source
        self.whitelist = [item.text for item in xsource.findall('Whitelist')]

        #: Whether or not to include deb-src lines in the generated APT
        #: configuration
        self.debsrc = xsource.get('debsrc', 'false') == 'true'

        #: A dict of repository options that will be included in the
        #: configuration generated on the server side (if such is
        #: applicable; most backends do not generate any sort of
        #: repository configuration on the Bcfg2 server)
        self.server_options = dict()

        #: A dict of repository options that will be included in the
        #: configuration generated for the client (if that is
        #: supported by the backend)
        self.client_options = dict()
        opts = xsource.findall("Options")
        for el in opts:
            repoopts = dict([(k, v)
                             for k, v in el.attrib.items()
                             if k != "clientonly" and k != "serveronly"])
            if el.get("clientonly", "false").lower() == "false":
                self.server_options.update(repoopts)
            if el.get("serveronly", "false").lower() == "false":
                self.client_options.update(repoopts)

        #: A list of URLs to GPG keys that apply to this source
        self.gpgkeys = [el.text for el in xsource.findall("GPGKey")]

        #: Whether or not to include essential packages from this source
        self.essential = xsource.get('essential', 'true').lower() == 'true'

        #: Whether or not to include recommended packages from this source
        self.recommended = xsource.get('recommended',
                                       'false').lower() == 'true'

        #: The "rawurl" attribute from :attr:`xsource`, if applicable.
        #: A trailing slash is automatically appended to this if there
        #: wasn't one already present.
        self.rawurl = xsource.get('rawurl', '')
        if self.rawurl and not self.rawurl.endswith("/"):
            self.rawurl += "/"

        #: The "url" attribute from :attr:`xsource`, if applicable.  A
        #: trailing slash is automatically appended to this if there
        #: wasn't one already present.
        self.url = xsource.get('url', '')
        if self.url and not self.url.endswith("/"):
            self.url += "/"

        #: The "version" attribute from :attr:`xsource`
        self.version = xsource.get('version', '')

        #: A list of predicates that are used to determine if this
        #: source applies to a given
        #: :class:`Bcfg2.Server.Plugins.Metadata.ClientMetadata`
        #: object.
        self.conditions = []
        #: Formerly, :ref:`server-plugins-generators-packages` only
        #: supported applying package sources to groups; that is, they
        #: could not be assigned by more complicated logic like
        #: per-client repositories and group or client negation.  This
        #: attribute attempts to provide for some limited backwards
        #: compat with older code that relies on this.
        self.groups = []
        for el in xsource.iterancestors():
            if el.tag == "Group":
                if el.get("negate", "false").lower() == "true":
                    self.conditions.append(lambda m, el=el:
                                           el.get("name") not in m.groups)
                else:
                    self.groups.append(el.get("name"))
                    self.conditions.append(lambda m, el=el:
                                           el.get("name") in m.groups)
            elif el.tag == "Client":
                if el.get("negate", "false").lower() == "true":
                    self.conditions.append(lambda m, el=el:
                                           el.get("name") != m.hostname)
                else:
                    self.conditions.append(lambda m, el=el:
                                           el.get("name") == m.hostname)

        #: A set of all package names in this source.  This will not
        #: necessarily be populated, particularly by backends that
        #: reimplement large portions of
        #: :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
        self.pkgnames = set()

        #: A dict of ``<package name>`` -> ``<list of dependencies>``.
        #: This will not necessarily be populated, particularly by
        #: backends that reimplement large portions of
        #: :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
        self.deps = dict()

        #: A dict of ``<package name>`` -> ``<list of provided
        #: symbols>``.  This will not necessarily be populated,
        #: particularly by backends that reimplement large portions of
        #: :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
        self.provides = dict()

        #: The file (or directory) used for this source's cache data
        self.cachefile = os.path.join(self.basepath,
                                      "cache-%s" % self.cachekey)
        if not self.rawurl:
            baseurl = self.url + "%(version)s/%(component)s/%(arch)s/"
        else:
            baseurl = self.rawurl

        #: A list of dicts, each of which describes the URL to one
        #: repository contained in this source.  Each dict contains
        #: the following keys:
        #:
        #: * ``version``: The version of the repo (``None`` for
        #:   ``rawurl`` repos)
        #: * ``component``: The component use to form this URL
        #:   (``None`` for ``rawurl`` repos)
        #: * ``arch``: The architecture of this repo
        #: * ``baseurl``: Either the ``rawurl`` attribute, or the
        #:   format string built from the ``url`` attribute
        #: * ``url``: The actual URL to the repository
        self.url_map = []
        for arch in self.arches:
            if self.url:
                usettings = [dict(version=self.version, component=comp,
                                  arch=arch)
                             for comp in self.components]
            else:  # rawurl given
                usettings = [dict(version=self.version, component=None,
                                  arch=arch)]

            for setting in usettings:
                if not self.rawurl:
                    setting['baseurl'] = self.url
                else:
                    setting['baseurl'] = self.rawurl
                setting['url'] = baseurl % setting
            self.url_map.extend(usettings)

    @property
    def cachekey(self):
        """ A unique key for this source that will be used to generate
        :attr:`cachefile` and other cache paths """
        return md5(cPickle.dumps([self.version, self.components, self.url,
                                  self.rawurl, self.arches])).hexdigest()

    def get_relevant_groups(self, metadata):
        """ Get all groups that might be relevant to determining which
        sources apply to this collection's client.

        :return: list of strings - group names
        """
        return sorted(list(set([g for g in metadata.groups
                                if (g in self.basegroups or
                                    g in self.groups or
                                    g in self.arches)])))

    def load_state(self):
        """ Load saved state from :attr:`cachefile`.  If caching and
        state is handled by the package library, then this function
        does not need to be implemented.

        :raises: OSError - If the saved data cannot be read
        :raises: cPickle.UnpicklingError - If the saved data is corrupt """
        data = open(self.cachefile, 'rb')
        (self.pkgnames, self.deps, self.provides,
         self.essentialpkgs) = cPickle.load(data)

    def save_state(self):
        """ Save state to :attr:`cachefile`.  If caching and
        state is handled by the package library, then this function
        does not need to be implemented. """
        cache = open(self.cachefile, 'wb')
        cPickle.dump((self.pkgnames, self.deps, self.provides,
                      self.essentialpkgs), cache, 2)
        cache.close()

    @Bcfg2.Server.Plugin.track_statistics()
    def setup_data(self, force_update=False):
        """ Perform all data fetching and setup tasks.  For most
        backends, this involves downloading all metadata from the
        repository, parsing it, and caching the parsed data locally.
        The order of operations is:

        #. Call :func:`load_state` to try to load data from the local
           cache.
        #. If that fails, call :func:`read_files` to read and parse
           the locally downloaded metadata files.
        #. If that fails, call :func:`update` to fetch the metadata,
           then :func:`read_files` to parse it.

        Obviously with a backend that leverages repo access libraries
        to avoid downloading all metadata, many of the functions
        called by ``setup_data`` can be no-ops (or nearly so).

        :param force_update: Ignore all locally cached and downloaded
                             data and fetch the metadata anew from the
                             upstream repository.
        :type force_update: bool
        """
        # pylint: disable=W0702
        if not force_update:
            if os.path.exists(self.cachefile):
                try:
                    self.load_state()
                except:
                    err = sys.exc_info()[1]
                    self.logger.error("Packages: Cachefile %s load failed: %s"
                                      % (self.cachefile, err))
                    self.logger.error("Falling back to file read")

                    try:
                        self.read_files()
                    except:
                        err = sys.exc_info()[1]
                        self.logger.error("Packages: File read failed: %s" %
                                          err)
                        self.logger.error("Falling back to file download")
                        force_update = True
            else:
                force_update = True

        if force_update:
            try:
                self.update()
                self.read_files()
            except:
                err = sys.exc_info()[1]
                self.logger.error("Packages: Failed to load data for %s: %s" %
                                  (self, err))
                self.logger.error("Some Packages will be missing")
        # pylint: enable=W0702

    def get_repo_name(self, url_map):
        """ Try to find a sensible name for a repository. Since
        ``sources.xml`` doesn't provide for repository names, we have
        to try to guess at the names when generating config files or
        doing other operations that require repository names.  This
        function tries several approaches:

        #. First, if the map contains a ``component`` key, use that as
           the name.
        #. If not, then try to match the repository URL against
           :attr:`Bcfg2.Server.Plugins.Packages.Source.REPO_RE`.  If
           that succeeds, use the first matched group; additionally,
           if the Source tag that describes this repo is contained in
           a ``<Group>`` tag, prepend that to the name.
        #. If :attr:`Bcfg2.Server.Plugins.Packages.Source.REPO_RE`
           does not match the repository, and the Source tag that
           describes this repo is contained in a ``<Group>`` tag, use
           the name of the group.
        #. Failing that, use the full URL to this repository, with the
           protocol and trailing slash stripped off if possible.

        Once that is done, all characters disallowed in yum source
        names are replaced by dashes.  See below for the exact regex.
        The yum rules are used here because they are so restrictive.

        ``get_repo_name`` is **not** guaranteed to return a unique
        name.  If you require a unique name, then you will need to
        generate all repo names and make them unique through the
        approach of your choice, e.g., appending numbers to non-unique
        repository names.  See
        :func:`Bcfg2.Server.Plugins.Packages.Yum.Source.get_repo_name`
        for an example.

        :param url_map: A single :attr:`url_map` dict, i.e., any
                        single element of :attr:`url_map`.
        :type url_map: dict
        :returns: string - the name of the repository.
        """
        if url_map['component']:
            rname = url_map['component']
        else:
            match = REPO_RE.search(url_map['url'])
            if match:
                rname = match.group(1)
                if self.groups:
                    rname = "%s-%s" % (self.groups[0], rname)
            elif self.groups:
                rname = self.groups[0]
            else:
                # a global source with no reasonable name.  Try to
                # strip off the protocol and trailing slash.
                match = re.search(r'^[A-z]://(.*?)/?', url_map['url'])
                if match:
                    rname = match.group(1)
                else:
                    # what kind of crazy url is this?  I give up!
                    # just use the full url and let the regex below
                    # make it even uglier.
                    rname = url_map['url']
        # see yum/__init__.py in the yum source, lines 441-449, for
        # the source of this regex.  yum doesn't like anything but
        # string.ascii_letters, string.digits, and [-_.:].  There
        # doesn't seem to be a reason for this, because yum.
        return re.sub(r'[^A-Za-z0-9-_.:]', '-', rname)

    def __repr__(self):
        if self.rawurl:
            return "%s at %s" % (self.__class__.__name__, self.rawurl)
        elif self.url:
            return "%s at %s" % (self.__class__.__name__, self.url)
        else:
            return self.__class__.__name__

    @property
    def urls(self):
        """ A list of URLs to the base metadata file for each
        repository described by this source. """
        return []

    @property
    def files(self):
        """ A list of files stored in the local cache by this backend.
        """
        return [self.escape_url(url) for url in self.urls]

    def get_vpkgs(self, metadata):
        """ Get a list of all virtual packages provided by all sources.

        :returns: list of strings
        """
        agroups = ['global'] + [a for a in self.arches
                                if a in metadata.groups]
        vdict = dict()
        for agrp in agroups:
            if agrp not in self.provides:
                self.logger.warning("%s provides no packages for %s" %
                                    (self, agrp))
                continue
            for key, value in list(self.provides[agrp].items()):
                if key not in vdict:
                    vdict[key] = set(value)
                else:
                    vdict[key].update(value)
        return vdict

    def is_virtual_package(self, metadata, package):  # pylint: disable=W0613
        """ Return True if a name is a virtual package (i.e., is a
        symbol provided by a real package), False otherwise.

        :param package: The name of the symbol, but see :ref:`pkg-objects`
        :type package: string
        :returns: bool
        """
        return False

    def escape_url(self, url):
        """ Given a URL to a repository metadata file, return the full
        path to a file suitable for storing that file locally.  This
        is acheived by replacing all forward slashes in the URL with
        ``@``.

        :param url: The URL to escape
        :type url: string
        :returns: string
        """
        return os.path.join(self.basepath, url.replace('/', '@'))

    def read_files(self):
        """ Read and parse locally downloaded metadata files and
        populates
        :attr:`Bcfg2.Server.Plugins.Packages.Source.Source.pkgnames`. Should
        call
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.process_files`
        as its final step."""
        pass

    def process_files(self, dependencies, provides):
        """ Given dicts of depends and provides generated by
        :func:`read_files`, this generates :attr:`deps` and
        :attr:`provides` and calls :func:`save_state` to save the
        cached data to disk.

        Both arguments are dicts of dicts of lists.  Keys are the
        arches of packages contained in this source; values are dicts
        whose keys are package names and values are lists of either
        dependencies for each package the symbols provided by each
        package.

        :param dependencies: A dict of dependencies found in the
                             metadata for this source.
        :type dependencies: dict; see above.
        :param provides: A dict of symbols provided by packages in
                        this repository.
        :type provides: dict; see above.
        """
        self.deps['global'] = dict()
        self.provides['global'] = dict()
        for barch in dependencies:
            self.deps[barch] = dict()
            self.provides[barch] = dict()
        for pkgname in self.pkgnames:
            pset = set()
            for barch in dependencies:
                if pkgname not in dependencies[barch]:
                    dependencies[barch][pkgname] = []
                pset.add(tuple(dependencies[barch][pkgname]))
            if len(pset) == 1:
                self.deps['global'][pkgname] = pset.pop()
            else:
                for barch in dependencies:
                    self.deps[barch][pkgname] = dependencies[barch][pkgname]
        provided = set()
        for bprovided in list(provides.values()):
            provided.update(set(bprovided))
        for prov in provided:
            prset = set()
            for barch in provides:
                if prov not in provides[barch]:
                    continue
                prset.add(tuple(provides[barch].get(prov, ())))
            if len(prset) == 1:
                self.provides['global'][prov] = prset.pop()
            else:
                for barch in provides:
                    self.provides[barch][prov] = provides[barch].get(prov, ())
        self.save_state()

    def unknown_filter(self, package):
        """ A predicate that is used by :func:`filter_unknown` to
        filter packages from the results of
        :func:`Bcfg2.Server.Plugins.Packages.Collection.Collection.complete`
        that should not be shown to the end user (i.e., that are not
        truly unknown, but are rather packaging system artifacts).  By
        default, excludes any package whose name starts with "choice"

        :param package: The name of a package that was unknown to the
                        backend
        :type package: string
        :returns: bool
        """
        return package.startswith("choice")

    def filter_unknown(self, unknown):
        """ After
        :func:`Bcfg2.Server.Plugins.Packages.Collection.Collection.complete`,
        filter out packages that appear in the list of unknown
        packages but should not be presented to the user.
        :attr:`unknown_filter` is called to assess whether or not a
        package is expected to be unknown.

        :param unknown: A set of unknown packages.  The set should be
                        modified in place.
        :type unknown: set of strings
        """
        unknown.difference_update(set([u for u in unknown
                                       if self.unknown_filter(u)]))

    def update(self):
        """ Download metadata from the upstream repository and cache
        it locally.

        :raises: ValueError - If any URL in :attr:`urls` is malformed
        :raises: OSError - If there is an error writing the local
                 cache
        :raises: HTTPError - If there is an error fetching the remote
                 data
        """
        for url in self.urls:
            self.logger.info("Packages: Updating %s" % url)
            fname = self.escape_url(url)
            try:
                open(fname, 'wb').write(fetch_url(url))
            except ValueError:
                self.logger.error("Packages: Bad url string %s" % url)
                raise
            except OSError:
                err = sys.exc_info()[1]
                self.logger.error("Packages: Could not write data from %s to "
                                  "local cache at %s: %s" % (url, fname, err))
                raise
            except HTTPError:
                err = sys.exc_info()[1]
                self.logger.error("Packages: Failed to fetch url %s. HTTP "
                                  "response code=%s" % (url, err.code))
                raise

    def applies(self, metadata):
        """ Return true if this source applies to the given client,
        i.e., the client is in all necessary groups and
        :ref:`server-plugins-generators-packages-magic-groups`.

        :param metadata: The client metadata to check to see if this
                         source applies
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: bool
        """
        # check base groups
        if not self.magic_groups_match(metadata):
            return False

        # check Group/Client tags from sources.xml
        for condition in self.conditions:
            if not condition(metadata):
                return False

        return True

    def get_arches(self, metadata):
        """ Get a list of architectures that the given client has and
        for which this source provides packages for.  The return value
        will always include ``global``.

        :param metadata: The client metadata to get matching
                         architectures for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: list of strings
        """
        return ['global'] + [a for a in self.arches if a in metadata.groups]

    def get_deps(self, metadata, package):
        """ Get a list of the dependencies of the given package.

        :param package: The name of the symbol
        :type package: string
        :returns: list of strings
        """
        for arch in self.get_arches(metadata):
            if package in self.deps[arch]:
                return self.deps[arch][package]
        return []

    def get_provides(self, metadata, package):
        """ Get a list of all symbols provided by the given package.

        :param package: The name of the package
        :type package: string
        :returns: list of strings
        """
        for arch in self.get_arches(metadata):
            if package in self.provides[arch]:
                return self.provides[arch][package]
        return []

    def is_package(self, metadata, package):  # pylint: disable=W0613
        """ Return True if a package is a package, False otherwise.

        :param package: The name of the package
        :type package: string
        :returns: bool
        """
        return (package in self.pkgnames and
                package not in self.blacklist and
                (len(self.whitelist) == 0 or package in self.whitelist))

    def get_group(self, metadata, group, ptype=None):  # pylint: disable=W0613
        """ Get the list of packages of the given type in a package
        group.

        :param group: The name of the group to query
        :type group: string
        :param ptype: The type of packages to get, for backends that
                      support multiple package types in package groups
                      (e.g., "recommended," "optional," etc.)
        :type ptype: string
        :returns: list of strings - package names
        """
        return []

    def magic_groups_match(self, metadata):
        """ Returns True if the client's
        :ref:`server-plugins-generators-packages-magic-groups` match
        the magic groups this source.  Also returns True if magic
        groups are off in the configuration and the client's
        architecture matches (i.e., architecture groups are *always*
        checked).

        :returns: bool
        """
        found_arch = False
        for arch in self.arches:
            if arch in metadata.groups:
                found_arch = True
                break
        if not found_arch:
            return False

        if not self.setup.cfp.getboolean("packages", "magic_groups",
                                         default=False):
            return True
        else:
            for group in self.basegroups:
                if group in metadata.groups:
                    return True
            return False
