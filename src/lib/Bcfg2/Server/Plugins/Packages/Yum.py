""" Yum backend for :mod:`Bcfg2.Server.Plugins.Packages`.  This module
is the most complex backend because it has to handle Yum sources
without yum Python libraries, with yum Python libraries, and Pulp
sources.  (See :ref:`native-yum-libraries` for details on using the
yum Python libraries and :ref:`pulp-source-support` for details on
Pulp sources.)

.. _bcfg2-yum-helper:

bcfg2-yum-helper
~~~~~~~~~~~~~~~~

If using the yum Python libraries, :class:`YumCollection` makes shell
calls to an external command, ``bcfg2-yum-helper``, which performs the
actual yum API calls.  This is done because the yum libs have horrific
memory leaks, and apparently the right way to get around that in
long-running processes it to have a short-lived helper.  This is how
it's done by yum itself in ``yum-updatesd``, which is a long-running
daemon that checks for and applies updates.

.. _yum-pkg-objects:

Package Objects
~~~~~~~~~~~~~~~

:class:`Bcfg2.Server.Plugins.Packages.Collection.Collection` objects
have the option to translate from some backend-specific representation
of packages to XML entries; see :ref:`pkg-objects` for more
information on this.  If you are using the Python yum libraries,
:class:`Bcfg2.Server.Plugins.Packages.Yum.YumCollection` opts to do
this, using the yum tuple representation of packages, which is::

    (<name>, <arch>, <epoch>, <version>, <release>)

For shorthand this is occasionally abbrevated "naevr".  Any datum that
is not defined is ``None``.  So a normal package entry that can be any
version would be passed to :ref:`bcfg2-yum-helper` as::

    ("somepackage", None, None, None, None)

A package returned from the helper might look more like this::

    ("somepackage", "x86_64", None, "1.2.3", "1.el6")

We translate between this representation and the XML representation of
packages with :func:`YumCollection.packages_from_entry` and
:func:`YumCollection.packages_to_entry`.

The Yum Backend
~~~~~~~~~~~~~~~
"""

import os
import re
import sys
import copy
import errno
import socket
import logging
import lxml.etree
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin
# pylint: disable=W0622
from Bcfg2.Compat import StringIO, cPickle, HTTPError, URLError, \
    ConfigParser, any
# pylint: enable=W0622
from Bcfg2.Server.Plugins.Packages.Collection import Collection
from Bcfg2.Server.Plugins.Packages.Source import SourceInitError, Source, \
    fetch_url

LOGGER = logging.getLogger(__name__)

# pylint: disable=E0611
try:
    from pulp.client.consumer.config import ConsumerConfig
    from pulp.client.api.repository import RepositoryAPI
    from pulp.client.api.consumer import ConsumerAPI
    from pulp.client.api import server
    HAS_PULP = True
except ImportError:
    HAS_PULP = False
# pylint: enable=E0611

try:
    import yum
    try:
        import json
    except ImportError:
        import simplejson as json
    HAS_YUM = True
except ImportError:
    HAS_YUM = False
    LOGGER.info("Packages: No yum libraries found; forcing use of internal "
                "dependency resolver")


XP = '{http://linux.duke.edu/metadata/common}'
RP = '{http://linux.duke.edu/metadata/rpm}'
RPO = '{http://linux.duke.edu/metadata/repo}'
FL = '{http://linux.duke.edu/metadata/filelists}'

PULPSERVER = None
PULPCONFIG = None

#: The path to bcfg2-yum-helper
HELPER = None


def _setup_pulp(setup):
    """ Connect to a Pulp server and pass authentication credentials.
    This only needs to be called once, but multiple calls won't hurt
    anything.

    :param setup: A Bcfg2 options dict
    :type setup: dict
    :returns: :class:`pulp.client.api.server.PulpServer`
    """
    global PULPSERVER, PULPCONFIG
    if not HAS_PULP:
        msg = "Packages: Cannot create Pulp collection: Pulp libraries " + \
            "not found"
        LOGGER.error(msg)
        raise Bcfg2.Server.Plugin.PluginInitError(msg)

    if PULPSERVER is None:
        try:
            username = setup.cfp.get("packages:pulp", "username")
            password = setup.cfp.get("packages:pulp", "password")
        except ConfigParser.NoSectionError:
            msg = "Packages: No [pulp] section found in bcfg2.conf"
            LOGGER.error(msg)
            raise Bcfg2.Server.Plugin.PluginInitError(msg)
        except ConfigParser.NoOptionError:
            msg = "Packages: Required option not found in bcfg2.conf: %s" % \
                sys.exc_info()[1]
            LOGGER.error(msg)
            raise Bcfg2.Server.Plugin.PluginInitError(msg)

        PULPCONFIG = ConsumerConfig()
        serveropts = PULPCONFIG.server

        PULPSERVER = server.PulpServer(serveropts['host'],
                                       int(serveropts['port']),
                                       serveropts['scheme'],
                                       serveropts['path'])
        PULPSERVER.set_basic_auth_credentials(username, password)
        server.set_active_server(PULPSERVER)
    return PULPSERVER


class PulpCertificateData(Bcfg2.Server.Plugin.SpecificData):
    """ Handle pulp consumer certificate data for
    :class:`PulpCertificateSet` """

    def bind_entry(self, entry, _):
        """ Given an abstract entry, add data to it and return it.
        :class:`PulpCertificateSet` handles binding entry metadata.

        :param entry: The abstract entry to bind data to
        :type entry: lxml.etree._Element
        :returns: lxml.etree._Element - the bound entry
        """
        entry.set("type", "file")
        if self.data:
            entry.text = self.data
        else:
            entry.set("empty", "true")
        return entry


class PulpCertificateSet(Bcfg2.Server.Plugin.EntrySet):
    """ Handle Pulp consumer certificates. """

    #: The path to certificates on consumer machines
    certpath = "/etc/pki/consumer/cert.pem"

    def __init__(self, path, fam):
        """
        :param path: The path to the directory where Pulp consumer
                     certificates will be stored
        :type path: string
        """
        Bcfg2.Server.Plugin.EntrySet.__init__(self,
                                              os.path.basename(self.certpath),
                                              path,
                                              PulpCertificateData,
                                              "UTF-8")
        self.metadata = dict(owner='root',
                             group='root',
                             mode='0644',
                             secontext='__default__',
                             important='true',
                             sensitive='true',
                             paranoid=self.metadata['paranoid'])
        self.fam = fam
        self.fam.AddMonitor(path, self)

    def HandleEvent(self, event):
        """ Handle FAM events on certificate files.

        :param event: The event to handle
        :type event: Bcfg2.Server.FileMonitor.Event """
        if event.filename != self.path:
            return self.handle_event(event)

    def write_data(self, data, metadata):
        """ Write a new certificate to the filesystem.

        :param data: The new certificate data
        :type data: string
        :param metadata: Metadata for the client to write the
                         certificate for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        specific = "%s.H_%s" % (os.path.basename(self.certpath),
                                metadata.hostname)
        fileloc = os.path.join(self.path, specific)

        self.logger.info("Packages: Writing certificate data for %s to %s" %
                         (metadata.hostname, fileloc))
        try:
            open(fileloc, 'wb').write(data)
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Could not write %s: %s" % (fileloc, err))
            return
        self.verify_file(specific)

    def verify_file(self, filename):
        """ Service the FAM events queued up by the key generation so
        the data structure entries will be available for binding.

        NOTE: We wait for up to ten seconds. There is some potential
        for race condition, because if the file monitor doesn't get
        notified about the new key files in time, those entries won't
        be available for binding. In practice, this seems "good
        enough."

        :param filename: The filename to check for events on
        :type filename: string
        """
        tries = 0
        updated = False
        while not updated:
            if tries >= 10:
                self.logger.error("%s still not registered" % filename)
                return
            self.fam.handle_events_in_interval(1)
            if filename in self.entries:
                break
            else:
                tries += 1
                continue


class YumCollection(Collection):
    """ Handle collections of Yum sources.  If we're using the yum
    Python libraries, then this becomes a very full-featured
    :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`
    object; if not, then it defers to the :class:`YumSource`
    object.

    .. private-include: _add_gpg_instances, _get_pulp_consumer
    """

    #: Options that are included in the [packages:yum] section of the
    #: config but that should not be included in the temporary
    #: yum.conf we write out
    option_blacklist = ["use_yum_libraries", "helper"]

    #: :class:`PulpCertificateSet` object used to handle Pulp certs
    pulp_cert_set = None

    def __init__(self, metadata, sources, cachepath, basepath, fam,
                 debug=False):
        Collection.__init__(self, metadata, sources, cachepath, basepath, fam,
                            debug=debug)
        self.keypath = os.path.join(self.cachepath, "keys")

        if self.use_yum:
            #: Define a unique cache file for this collection to use
            #: for cached yum metadata
            self.cachefile = os.path.join(self.cachepath,
                                          "cache-%s" % self.cachekey)
            if not os.path.exists(self.cachefile):
                os.mkdir(self.cachefile)

            #: The path to the server-side config file used when
            #: resolving packages with the Python yum libraries
            self.cfgfile = os.path.join(self.cachefile, "yum.conf")
            self.write_config()
        else:
            self.cachefile = None

        if HAS_PULP and self.has_pulp_sources:
            _setup_pulp(self.setup)
            if self.pulp_cert_set is None:
                certdir = os.path.join(
                    self.basepath,
                    "pulp",
                    os.path.basename(PulpCertificateSet.certpath))
                try:
                    os.makedirs(certdir)
                except OSError:
                    err = sys.exc_info()[1]
                    if err.errno == errno.EEXIST:
                        pass
                    else:
                        self.logger.error("Could not create Pulp consumer "
                                          "cert directory at %s: %s" %
                                          (certdir, err))
                self.pulp_cert_set = PulpCertificateSet(certdir, self.fam)

    @property
    def __package_groups__(self):
        return True

    @property
    def helper(self):
        """ The full path to :file:`bcfg2-yum-helper`.  First, we
        check in the config file to see if it has been explicitly
        specified; next we see if it's in $PATH (which we do by making
        a call to it; I wish there was a way to do this without
        forking, but apparently not); finally we check in /usr/sbin,
        the default location. """
        global HELPER
        if not HELPER:
            try:
                HELPER = self.setup.cfp.get("packages:yum", "helper")
            except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
                # first see if bcfg2-yum-helper is in PATH
                try:
                    self.debug_log("Checking for bcfg2-yum-helper in $PATH")
                    Popen(['bcfg2-yum-helper'],
                          stdin=PIPE, stdout=PIPE, stderr=PIPE).wait()
                    HELPER = 'bcfg2-yum-helper'
                except OSError:
                    HELPER = "/usr/sbin/bcfg2-yum-helper"
        return HELPER

    @property
    def use_yum(self):
        """ True if we should use the yum Python libraries, False
        otherwise """
        return HAS_YUM and self.setup.cfp.getboolean("packages:yum",
                                                     "use_yum_libraries",
                                                     default=False)

    @property
    def has_pulp_sources(self):
        """ True if there are any Pulp sources to handle, False
        otherwise """
        return any(s.pulp_id for s in self)

    @property
    def cachefiles(self):
        """ A list of the full path to all cachefiles used by this
        collection."""
        cachefiles = set(Collection.cachefiles.fget(self))
        if self.cachefile:
            cachefiles.add(self.cachefile)
        return list(cachefiles)

    @Bcfg2.Server.Plugin.track_statistics()
    def write_config(self):
        """ Write the server-side config file to :attr:`cfgfile` based
        on the data from :func:`get_config`"""
        if not os.path.exists(self.cfgfile):
            yumconf = self.get_config(raw=True)
            yumconf.add_section("main")

            # we set installroot to the cache directory so
            # bcfg2-yum-helper works with an empty rpmdb.  otherwise
            # the rpmdb is so hopelessly intertwined with yum that we
            # have to totally reinvent the dependency resolver.
            mainopts = dict(cachedir='/',
                            installroot=self.cachefile,
                            keepcache="0",
                            debuglevel="0",
                            sslverify="0",
                            reposdir="/dev/null")
            if self.setup['debug']:
                mainopts['debuglevel'] = "5"
            elif self.setup['verbose']:
                mainopts['debuglevel'] = "2"

            try:
                for opt in self.setup.cfp.options("packages:yum"):
                    if opt not in self.option_blacklist:
                        mainopts[opt] = self.setup.cfp.get("packages:yum", opt)
            except ConfigParser.NoSectionError:
                pass

            for opt, val in list(mainopts.items()):
                yumconf.set("main", opt, val)

            yumconf.write(open(self.cfgfile, 'w'))

    def get_config(self, raw=False):  # pylint: disable=W0221
        """ Get the yum configuration for this collection.

        :param raw: Return a :class:`ConfigParser.SafeConfigParser`
                    object representing the configuration instead of a
                    string.  This is useful if you need to modify the
                    config before writing it (as :func:`write_config`
                    does in order to produce a server-specific
                    configuration).
        :type raw: bool
        :returns: string or ConfigParser.SafeConfigParser """

        config = ConfigParser.SafeConfigParser()
        for source in self:
            for url_map in source.url_map:
                if url_map['arch'] not in self.metadata.groups:
                    continue
                basereponame = source.get_repo_name(url_map)
                reponame = basereponame

                added = False
                while not added:
                    try:
                        config.add_section(reponame)
                        added = True
                    except ConfigParser.DuplicateSectionError:
                        match = re.search(r'-(\d+)', reponame)
                        if match:
                            rid = int(match.group(1)) + 1
                        else:
                            rid = 1
                        reponame = "%s-%d" % (basereponame, rid)

                config.set(reponame, "name", reponame)
                config.set(reponame, "baseurl", url_map['url'])
                config.set(reponame, "enabled", "1")
                if len(source.gpgkeys):
                    config.set(reponame, "gpgcheck", "1")
                    config.set(reponame, "gpgkey",
                               " ".join(source.gpgkeys))
                else:
                    config.set(reponame, "gpgcheck", "0")

                if len(source.blacklist):
                    config.set(reponame, "exclude",
                               " ".join(source.blacklist))
                if len(source.whitelist):
                    config.set(reponame, "includepkgs",
                               " ".join(source.whitelist))

                if raw:
                    opts = source.server_options
                else:
                    opts = source.client_options
                for opt, val in opts.items():
                    config.set(reponame, opt, val)

        if raw:
            return config
        else:
            # configparser only writes to file, so we have to use a
            # StringIO object to get the data out as a string
            buf = StringIO()
            config.write(buf)
            return "# This config was generated automatically by the Bcfg2 " \
                   "Packages plugin\n\n" + buf.getvalue()

    @Bcfg2.Server.Plugin.track_statistics()
    def build_extra_structures(self, independent):
        """ Add additional entries to the ``<Independent/>`` section
        of the final configuration.  This adds several kinds of
        entries:

        * For GPG keys, adds a ``Package`` entry that describes the
          version and release of all expected ``gpg-pubkey`` packages;
          and ``Path`` entries to copy all of the GPG keys to the
          appropriate place on the client filesystem.  Calls
          :func:`_add_gpg_instances`.

        * For Pulp Sources, adds a ``Path`` entry for the consumer
          certificate; and ``Action`` entries to update the
          consumer-side Pulp config if the consumer is newly
          registered.  Creates a new Pulp consumer from the Bcfg2
          server as necessary.

        :param independent: The XML tag to add extra entries to.  This
                            is modified in place.
        :type independent: lxml.etree._Element
        """
        needkeys = set()
        for source in self:
            for key in source.gpgkeys:
                needkeys.add(key)

        if len(needkeys):
            if HAS_YUM:
                # this must be be HAS_YUM, not use_yum, because
                # regardless of whether the user wants to use the yum
                # resolver we want to include gpg key data
                keypkg = lxml.etree.Element('BoundPackage', name="gpg-pubkey",
                                            type=self.ptype, origin='Packages')
            else:
                self.logger.warning("GPGKeys were specified for yum sources "
                                    "in sources.xml, but no yum libraries "
                                    "were found")
                self.logger.warning("GPG key version/release data cannot be "
                                    "determined automatically")
                self.logger.warning("Install yum libraries, or manage GPG "
                                    "keys manually")
                keypkg = None

            for key in needkeys:
                # figure out the path of the key on the client
                keydir = self.setup.cfp.get("global", "gpg_keypath",
                                            default="/etc/pki/rpm-gpg")
                remotekey = os.path.join(keydir, os.path.basename(key))
                localkey = os.path.join(self.keypath, os.path.basename(key))
                kdata = open(localkey).read()

                # copy the key to the client
                keypath = lxml.etree.Element("BoundPath", name=remotekey,
                                             encoding='ascii',
                                             owner='root', group='root',
                                             type='file', mode='0644',
                                             important='true')
                keypath.text = kdata

                # hook to add version/release info if possible
                self._add_gpg_instances(keypkg, localkey, remotekey,
                                        keydata=kdata)
                independent.append(keypath)
            if keypkg is not None:
                independent.append(keypkg)

        if self.has_pulp_sources:
            consumerapi = ConsumerAPI()
            consumer = self._get_pulp_consumer(consumerapi=consumerapi)
            if consumer is None:
                try:
                    consumer = \
                        consumerapi.create(self.metadata.hostname,
                                           self.metadata.hostname,
                                           capabilities=dict(bind=False))
                    lxml.etree.SubElement(
                        independent, "BoundAction", name="pulp-update",
                        timing="pre", when="always", status="check",
                        command="pulp-consumer consumer update")
                    self.pulp_cert_set.write_data(consumer['certificate'],
                                                  self.metadata)
                except server.ServerRequestError:
                    err = sys.exc_info()[1]
                    self.logger.error("Packages: Could not create Pulp "
                                      "consumer %s: %s" %
                                      (self.metadata.hostname, err))

            for source in self:
                # each pulp source can only have one arch, so we don't
                # have to check the arch in url_map
                if (source.pulp_id and
                    source.pulp_id not in consumer['repoids']):
                    try:
                        consumerapi.bind(self.metadata.hostname,
                                         source.pulp_id)
                    except server.ServerRequestError:
                        err = sys.exc_info()[1]
                        self.logger.error("Packages: Could not bind %s to "
                                          "Pulp repo %s: %s" %
                                          (self.metadata.hostname,
                                           source.pulp_id, err))

            crt = lxml.etree.SubElement(independent, "BoundPath",
                                        name=self.pulp_cert_set.certpath)
            self.pulp_cert_set.bind_entry(crt, self.metadata)

    @Bcfg2.Server.Plugin.track_statistics()
    def _get_pulp_consumer(self, consumerapi=None):
        """ Get a Pulp consumer object for the client.

        :param consumerapi: A Pulp ConsumerAPI object.  If none is
                            passed, one will be instantiated.
        :type consumerapi: pulp.client.api.consumer.ConsumerAPI
        :returns: dict - the consumer.  Returns None on failure
                  (including if there is no existing Pulp consumer for
                  this client.
        """
        if consumerapi is None:
            consumerapi = ConsumerAPI()
        consumer = None
        try:
            consumer = consumerapi.consumer(self.metadata.hostname)
        except server.ServerRequestError:
            # consumer does not exist
            pass
        except socket.error:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Could not contact Pulp server: %s" %
                              err)
        except:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Unknown error querying Pulp server: "
                              "%s" % err)
        return consumer

    @Bcfg2.Server.Plugin.track_statistics()
    def _add_gpg_instances(self, keyentry, localkey, remotekey, keydata=None):
        """ Add GPG keys instances to a ``Package`` entry.  This is
        called from :func:`build_extra_structures` to add GPG keys to
        the specification.

        :param keyentry: The ``Package`` entry to add key instances
                         to.  This will be modified in place.
        :type keyentry: lxml.etree._Element
        :param localkey: The full path to the key file on the Bcfg2 server
        :type localkey: string
        :param remotekey: The full path to the key file on the client.
                          (If they key is not yet on the client, this
                          will be the full path to where the key file
                          will go eventually.)
        :type remotekey: string
        :param keydata: The contents of the key file.  If this is not
                        provided, read the data from ``localkey``.
        :type keydata: string
        """
        # this must be be HAS_YUM, not use_yum, because regardless of
        # whether the user wants to use the yum resolver we want to
        # include gpg key data
        if not HAS_YUM:
            return

        if keydata is None:
            keydata = open(localkey).read()

        try:
            kinfo = yum.misc.getgpgkeyinfo(keydata)
            version = yum.misc.keyIdToRPMVer(kinfo['keyid'])
            release = yum.misc.keyIdToRPMVer(kinfo['timestamp'])

            lxml.etree.SubElement(keyentry, 'Instance',
                                  version=version,
                                  release=release,
                                  simplefile=remotekey)
        except ValueError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Could not read GPG key %s: %s" %
                              (localkey, err))

    @Bcfg2.Server.Plugin.track_statistics()
    def get_groups(self, grouplist):
        """ If using the yum libraries, given a list of package group
        names, return a dict of ``<group name>: <list of packages>``.
        This is much faster than implementing
        :func:`Bcfg2.Server.Plugins.Packages.Collection.Collection.get_group`,
        since we have to make a call to the bcfg2 Yum helper, and each
        time we do that we make another call to yum, which means we
        set up yum metadata from the cache (hopefully) each time.  So
        resolving ten groups once is much faster than resolving one
        group ten times.

        If you are using the builtin yum parser, this raises a warning
        and returns an empty dict.

        :param grouplist: The list of groups to query
        :type grouplist: list of strings - group names
        :returns: dict of ``<group name>: <list of packages>``

        In this implementation the packages may be strings or tuples.
        See :ref:`yum-pkg-objects` for more information. """
        if not grouplist:
            return dict()

        gdicts = []
        for group, ptype in grouplist:
            if group.startswith("@"):
                group = group[1:]
            if not ptype:
                ptype = "default"
            gdicts.append(dict(group=group, type=ptype))

        if self.use_yum:
            try:
                return self.call_helper("get_groups", inputdata=gdicts)
            except ValueError:
                return dict()
        else:
            pkgs = dict()
            for gdict in gdicts:
                pkgs[gdict['group']] = Collection.get_group(self,
                                                            gdict['group'],
                                                            gdict['type'])
            return pkgs

    def _element_to_pkg(self, el, name):
        """ Convert a Package or Instance element to a package tuple """
        rv = (name, el.get("arch"), el.get("epoch"),
              el.get("version"), el.get("release"))
        if rv[3] in ['any', 'auto']:
            rv = (rv[0], rv[1], rv[2], None, None)
        # if a package requires no specific version, we just use
        # the name, not the tuple.  this limits the amount of JSON
        # encoding/decoding that has to be done to pass the
        # package list to bcfg2-yum-helper.
        if rv[1:] == (None, None, None, None):
            return name
        else:
            return rv

    def packages_from_entry(self, entry):
        """ When using the Python yum libraries, convert a Package
        entry to a list of package tuples.  See :ref:`yum-pkg-objects`
        and :ref:`pkg-objects` for more information on this process.

        :param entry: The Package entry to convert
        :type entry: lxml.etree._Element
        :returns: list of tuples
        """
        if not self.use_yum:
            return Collection.packages_from_entry(self, entry)

        rv = set()
        name = entry.get("name")

        for inst in entry.getchildren():
            if inst.tag != "Instance":
                continue
            rv.add(self._element_to_pkg(inst, name))
        if not rv:
            rv.add(self._element_to_pkg(entry, name))
        return list(rv)

    def _get_entry_attrs(self, pkgtup):
        """ Given a package tuple, return a dict of attributes
        suitable for applying to either a Package or an Instance
        tag """
        attrs = dict(version=self.setup.cfp.get("packages", "version",
                                                default="auto"))
        if attrs['version'] == 'any' or not isinstance(pkgtup, tuple):
            return attrs

        try:
            if pkgtup[1]:
                attrs['arch'] = pkgtup[1]
            if pkgtup[2]:
                attrs['epoch'] = pkgtup[2]
            if pkgtup[3]:
                attrs['version'] = pkgtup[3]
            if pkgtup[4]:
                attrs['release'] = pkgtup[4]
        except IndexError:
            self.logger.warning("Malformed package tuple: %s" % pkgtup)
        return attrs

    def packages_to_entry(self, pkglist, entry):
        """ When using the Python yum libraries, convert a list of
        package tuples to a Package entry.  See :ref:`yum-pkg-objects`
        and :ref:`pkg-objects` for more information on this process.

        If pkglist contains only one package, then its data is
        converted to a single ``BoundPackage`` entry that is added as
        a subelement of ``entry``.  If pkglist contains more than one
        package, then a parent ``BoundPackage`` entry is created and
        child ``Instance`` entries are added to it.

        :param pkglist: A list of package tuples to convert to an XML
                         Package entry
        :type pkglist: list of tuples
        :param entry: The base XML entry to add Package entries to.
                      This is modified in place.
        :type entry: lxml.etree._Element
        :returns: None
        """
        if not self.use_yum:
            return Collection.packages_to_entry(self, pkglist, entry)

        packages = dict()
        for pkg in pkglist:
            try:
                packages[pkg[0]].append(pkg)
            except KeyError:
                packages[pkg[0]] = [pkg]
        for name, instances in packages.items():
            pkgattrs = dict(type=self.ptype,
                            origin='Packages',
                            name=name)
            if len(instances) > 1:
                pkg_el = lxml.etree.SubElement(entry, 'BoundPackage',
                                               **pkgattrs)
                for inst in instances:
                    lxml.etree.SubElement(pkg_el, "Instance",
                                          self._get_entry_attrs(inst))
            else:
                attrs = self._get_entry_attrs(instances[0])
                attrs.update(pkgattrs)
                lxml.etree.SubElement(entry, 'BoundPackage', **attrs)

    def get_new_packages(self, initial, complete):
        """ Compute the difference between the complete package list
        (as returned by :func:`complete`) and the initial package list
        computed from the specification, allowing for package tuples.
        See :ref:`yum-pkg-objects` and :ref:`pkg-objects` for more
        information on this process.

        :param initial: The initial package list
        :type initial: set of strings, but see :ref:`pkg-objects`
        :param complete: The final package list
        :type complete: set of strings, but see :ref:`pkg-objects`
        :return: set of tuples
        """
        initial_names = []
        for pkg in initial:
            if isinstance(pkg, tuple):
                initial_names.append(pkg[0])
            else:
                initial_names.append(pkg)
        new = []
        for pkg in complete:
            if isinstance(pkg, tuple):
                name = pkg[0]
            else:
                name = pkg
            if name not in initial_names:
                new.append(pkg)
        return new

    @Bcfg2.Server.Plugin.track_statistics()
    def complete(self, packagelist):
        """ Build a complete list of all packages and their dependencies.

        When using the Python yum libraries, this defers to the
        :ref:`bcfg2-yum-helper`; when using the builtin yum parser,
        this defers to
        :func:`Bcfg2.Server.Plugins.Packages.Collection.Collection.complete`.

        :param packagelist: Set of initial packages computed from the
                            specification.
        :type packagelist: set of strings, but see :ref:`pkg-objects`
        :returns: tuple of sets - The first element contains a set of
                  strings (but see :ref:`pkg-objects`) describing the
                  complete package list, and the second element is a
                  set of symbols whose dependencies could not be
                  resolved.
        """
        if not self.use_yum:
            return Collection.complete(self, packagelist)

        if packagelist:
            try:
                result = self.call_helper(
                    "complete",
                    dict(packages=list(packagelist),
                         groups=list(self.get_relevant_groups())))
            except ValueError:
                # error reported by call_helper()
                return set(), packagelist
            # json doesn't understand sets or tuples, so we get back a
            # lists of lists (packages) and a list of unicode strings
            # (unknown).  turn those into a set of tuples and a set of
            # strings, respectively.
            unknown = set([str(u) for u in result['unknown']])
            packages = set([tuple(p) for p in result['packages']])
            self.filter_unknown(unknown)
            return packages, unknown
        else:
            return set(), set()

    @Bcfg2.Server.Plugin.track_statistics()
    def call_helper(self, command, inputdata=None):
        """ Make a call to :ref:`bcfg2-yum-helper`.  The yum libs have
        horrific memory leaks, so apparently the right way to get
        around that in long-running processes it to have a short-lived
        helper.  No, seriously -- check out the yum-updatesd code.
        It's pure madness.

        :param command: The :ref:`bcfg2-yum-helper` command to call.
        :type command: string
        :param inputdata: The input to pass to ``bcfg2-yum-helper`` on
                          stdin.  If this is None, no input will be
                          given at all.
        :type inputdata: Any JSON-encodable data structure.
        :returns: Varies depending on the return value of the
                  ``bcfg2-yum-helper`` command.
        """
        cmd = [self.helper, "-c", self.cfgfile]
        if self.setup['verbose']:
            cmd.append("-v")
        if self.debug_flag:
            if not self.setup['verbose']:
                # ensure that running in debug gets -vv, even if
                # verbose is not enabled
                cmd.append("-v")
            cmd.append("-v")
        cmd.append(command)
        self.debug_log("Packages: running %s" % " ".join(cmd))
        try:
            helper = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Failed to execute %s: %s" %
                              (" ".join(cmd), err))
            return None

        if inputdata:
            idata = json.dumps(inputdata)
            (stdout, stderr) = helper.communicate(idata)
        else:
            (stdout, stderr) = helper.communicate()
        rv = helper.wait()
        errlines = stderr.splitlines()
        if rv:
            if not errlines:
                errlines.append("No error output")
            self.logger.error("Packages: error running bcfg2-yum-helper "
                              "(returned %d): %s" % (rv, errlines[0]))
            for line in errlines[1:]:
                self.logger.error("Packages: %s" % line)
        elif errlines:
            self.debug_log("Packages: debug info from bcfg2-yum-helper: %s" %
                           errlines[0])
            for line in errlines[1:]:
                self.debug_log("Packages: %s" % line)

        try:
            return json.loads(stdout)
        except ValueError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: error reading bcfg2-yum-helper "
                              "output: %s" % err)
            raise

    def setup_data(self, force_update=False):
        """ Do any collection-level data setup tasks. This is called
        when sources are loaded or reloaded by
        :class:`Bcfg2.Server.Plugins.Packages.Packages`.

        If the builtin yum parsers are in use, this defers to
        :func:`Bcfg2.Server.Plugins.Packages.Collection.Collection.setup_data`.
        If using the yum Python libraries, this cleans up cached yum
        metadata, regenerates the server-side yum config (in order to
        catch any new sources that have been added to this server),
        and then cleans up cached yum metadata again, in case the new
        config has any preexisting cache.

        :param force_update: Ignore all local cache and setup data
                             from its original upstream sources (i.e.,
                             the package repositories)
        :type force_update: bool
        """
        if not self.use_yum:
            return Collection.setup_data(self, force_update)

        if force_update:
            # we call this twice: one to clean up data from the old
            # config, and once to clean up data from the new config
            try:
                self.call_helper("clean")
            except ValueError:
                # error reported by call_helper
                pass

        os.unlink(self.cfgfile)
        self.write_config()

        if force_update:
            try:
                self.call_helper("clean")
            except ValueError:
                # error reported by call_helper
                pass


class YumSource(Source):
    """ Handle yum sources """

    #: :ref:`server-plugins-generators-packages-magic-groups` for
    #: ``YumSource`` are "yum", "redhat", "centos", and "fedora"
    basegroups = ['yum', 'redhat', 'centos', 'fedora']

    #: YumSource sets the ``type`` on Package entries to "yum"
    ptype = 'yum'

    def __init__(self, basepath, xsource, setup):
        Source.__init__(self, basepath, xsource, setup)
        self.pulp_id = None
        if HAS_PULP and xsource.get("pulp_id"):
            self.pulp_id = xsource.get("pulp_id")

            _setup_pulp(self.setup)
            repoapi = RepositoryAPI()
            try:
                self.repo = repoapi.repository(self.pulp_id)
                self.gpgkeys = [os.path.join(PULPCONFIG.cds['keyurl'], key)
                                for key in repoapi.listkeys(self.pulp_id)]
            except server.ServerRequestError:
                err = sys.exc_info()[1]
                if err[0] == 401:
                    msg = "Packages: Error authenticating to Pulp: %s" % err[1]
                elif err[0] == 404:
                    msg = "Packages: Pulp repo id %s not found: %s" % \
                          (self.pulp_id, err[1])
                else:
                    msg = "Packages: Error %d fetching pulp repo %s: %s" % \
                          (err[0], self.pulp_id, err[1])
                raise SourceInitError(msg)
            except socket.error:
                err = sys.exc_info()[1]
                raise SourceInitError("Could not contact Pulp server: %s" %
                                      err)
            except:
                err = sys.exc_info()[1]
                raise SourceInitError("Unknown error querying Pulp server: %s"
                                      % err)
            self.rawurl = "%s/%s" % (PULPCONFIG.cds['baseurl'],
                                     self.repo['relative_path'])
            self.arches = [self.repo['arch']]

        self.packages = dict()
        self.deps = dict([('global', dict())])
        self.provides = dict([('global', dict())])
        self.filemap = dict([(x, dict())
                             for x in ['global'] + self.arches])
        self.needed_paths = set()
        self.file_to_arch = dict()
        self.yumgroups = dict()
    __init__.__doc__ = Source.__init__.__doc__

    @property
    def use_yum(self):
        """ True if we should use the yum Python libraries, False
        otherwise """
        return HAS_YUM and self.setup.cfp.getboolean("packages:yum",
                                                     "use_yum_libraries",
                                                     default=False)

    def save_state(self):
        """ If using the builtin yum parser, save state to
        :attr:`cachefile`.  If using the Python yum libraries, yum
        handles caching and state and this method is a no-op."""
        if not self.use_yum:
            cache = open(self.cachefile, 'wb')
            cPickle.dump((self.packages, self.deps, self.provides,
                          self.filemap, self.url_map,
                          self.yumgroups), cache, 2)
            cache.close()

    def load_state(self):
        """ If using the builtin yum parser, load saved state from
        :attr:`cachefile`.  If using the Python yum libraries, yum
        handles caching and state and this method is a no-op."""
        if not self.use_yum:
            data = open(self.cachefile)
            (self.packages, self.deps, self.provides,
             self.filemap, self.url_map, self.yumgroups) = cPickle.load(data)

    @property
    def urls(self):
        """ A list of URLs to the base metadata file for each
        repository described by this source. """
        rv = []
        for umap in self.url_map:
            rv.extend(self._get_urls_from_repodata(umap['url'], umap['arch']))
        return rv

    def _get_urls_from_repodata(self, url, arch):
        """ When using the builtin yum parser, given the base URL of a
        repository, return the URLs of the various repo metadata files
        needed to get package data from the repo.

        If using the yum Python libraries, this just returns ``url``
        as it was passed in, but should realistically not be called.

        :param url: The base URL to the repository (i.e., the
                    directory that contains the ``repodata/`` directory)
        :type url: string
        :param arch: The architecture of the directory.
        :type arch: string
        :return: list of strings - URLs to metadata files
        """
        if self.use_yum:
            return [url]

        rmdurl = '%srepodata/repomd.xml' % url
        try:
            repomd = fetch_url(rmdurl)
        except ValueError:
            self.logger.error("Packages: Bad url string %s" % rmdurl)
            return []
        except HTTPError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Failed to fetch url %s. code=%s" %
                              (rmdurl, err.code))
            return []
        except URLError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Failed to fetch url %s. %s" %
                              (rmdurl, err))
            return []
        try:
            xdata = lxml.etree.XML(repomd)
        except lxml.etree.XMLSyntaxError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Failed to process metadata at %s: %s"
                              % (rmdurl, err))
            return []

        urls = []
        for elt in xdata.findall(RPO + 'data'):
            if elt.get('type') in ['filelists', 'primary', 'group']:
                floc = elt.find(RPO + 'location')
                fullurl = url + floc.get('href')
                urls.append(fullurl)
                self.file_to_arch[self.escape_url(fullurl)] = arch
        return urls

    @Bcfg2.Server.Plugin.track_statistics()
    def read_files(self):
        """ When using the builtin yum parser, read and parse locally
        downloaded metadata files.  This diverges from the stock
        :func:`Bcfg2.Server.Plugins.Packages.Source.Source.read_files`
        quite a bit. """

        # we have to read primary.xml first, and filelists.xml afterwards;
        primaries = list()
        filelists = list()
        groups = list()
        for fname in self.files:
            if fname.endswith('primary.xml.gz'):
                primaries.append(fname)
            elif fname.endswith('filelists.xml.gz'):
                filelists.append(fname)
            elif fname.find('comps'):
                groups.append(fname)

        for fname in primaries:
            farch = self.file_to_arch[fname]
            fdata = lxml.etree.parse(fname).getroot()
            self.parse_primary(fdata, farch)
        for fname in filelists:
            farch = self.file_to_arch[fname]
            fdata = lxml.etree.parse(fname).getroot()
            self.parse_filelist(fdata, farch)
        for fname in groups:
            fdata = lxml.etree.parse(fname).getroot()
            self.parse_group(fdata)

        # merge data
        sdata = list(self.packages.values())
        try:
            self.packages['global'] = copy.deepcopy(sdata.pop())
        except IndexError:
            self.logger.error("Packages: No packages in repo")
            self.packages['global'] = set()
        while sdata:
            self.packages['global'].update(sdata.pop())

        for key in self.packages:
            if key == 'global':
                continue
            self.packages[key] = \
                self.packages[key].difference(self.packages['global'])
        self.save_state()

    @Bcfg2.Server.Plugin.track_statistics()
    def parse_filelist(self, data, arch):
        """ parse filelists.xml.gz data """
        if arch not in self.filemap:
            self.filemap[arch] = dict()
        for pkg in data.findall(FL + 'package'):
            for fentry in pkg.findall(FL + 'file'):
                if fentry.text in self.needed_paths:
                    if fentry.text in self.filemap[arch]:
                        self.filemap[arch][fentry.text].add(pkg.get('name'))
                    else:
                        self.filemap[arch][fentry.text] = \
                            set([pkg.get('name')])

    @Bcfg2.Server.Plugin.track_statistics()
    def parse_primary(self, data, arch):
        """ parse primary.xml.gz data """
        if arch not in self.packages:
            self.packages[arch] = set()
        if arch not in self.deps:
            self.deps[arch] = dict()
        if arch not in self.provides:
            self.provides[arch] = dict()
        for pkg in data.getchildren():
            if not pkg.tag.endswith('package'):
                continue
            pkgname = pkg.find(XP + 'name').text
            self.packages[arch].add(pkgname)

            pdata = pkg.find(XP + 'format')
            self.deps[arch][pkgname] = set()
            pre = pdata.find(RP + 'requires')
            if pre is not None:
                for entry in pre.getchildren():
                    self.deps[arch][pkgname].add(entry.get('name'))
                    if entry.get('name').startswith('/'):
                        self.needed_paths.add(entry.get('name'))
            pro = pdata.find(RP + 'provides')
            if pro is not None:
                for entry in pro.getchildren():
                    prov = entry.get('name')
                    if prov not in self.provides[arch]:
                        self.provides[arch][prov] = list()
                    self.provides[arch][prov].append(pkgname)

    @Bcfg2.Server.Plugin.track_statistics()
    def parse_group(self, data):
        """ parse comps.xml.gz data """
        for group in data.getchildren():
            if not group.tag.endswith('group'):
                continue
            try:
                groupid = group.xpath('id')[0].text
                self.yumgroups[groupid] = {'mandatory': list(),
                                           'default': list(),
                                           'optional': list(),
                                           'conditional': list()}
            except IndexError:
                continue
            try:
                packagelist = group.xpath('packagelist')[0]
            except IndexError:
                continue
            for pkgreq in packagelist.getchildren():
                pkgtype = pkgreq.get('type', None)
                if pkgtype == 'mandatory':
                    self.yumgroups[groupid]['mandatory'].append(pkgreq.text)
                elif pkgtype == 'default':
                    self.yumgroups[groupid]['default'].append(pkgreq.text)
                elif pkgtype == 'optional':
                    self.yumgroups[groupid]['optional'].append(pkgreq.text)
                elif pkgtype == 'conditional':
                    self.yumgroups[groupid]['conditional'].append(pkgreq.text)

    def is_package(self, metadata, package):
        arch = [a for a in self.arches if a in metadata.groups]
        if not arch:
            return False
        return ((package in self.packages['global'] or
                 package in self.packages[arch[0]]) and
                package not in self.blacklist and
                (len(self.whitelist) == 0 or package in self.whitelist))
    is_package.__doc__ = Source.is_package.__doc__

    def get_vpkgs(self, metadata):
        if self.use_yum:
            return dict()

        rv = Source.get_vpkgs(self, metadata)
        for arch, fmdata in list(self.filemap.items()):
            if arch not in metadata.groups and arch != 'global':
                continue
            for filename, pkgs in list(fmdata.items()):
                rv[filename] = pkgs
        return rv
    get_vpkgs.__doc__ = Source.get_vpkgs.__doc__

    def unknown_filter(self, package):
        """ By default,
        :class:`Bcfg2.Server.Plugins.Packages.Source.Source` filters
        out unknown packages that start with "choice", but that
        doesn't mean anything to Yum or RPM.  Instead, we filter out
        unknown packages that start with "rpmlib", although this is
        likely legacy behavior; that would seem to indicate that a
        package required some RPM feature that isn't provided, which
        is a bad thing.  This should probably go away at some point.

        :param package: The name of a package that was unknown to the
                        backend
        :type package: string
        :returns: bool
        """
        return package.startswith("rpmlib")

    def filter_unknown(self, unknown):
        if self.use_yum:
            filtered = set()
            for unk in unknown:
                try:
                    if self.unknown_filter(unk):
                        filtered.update(unk)
                except AttributeError:
                    try:
                        if self.unknown_filter(unk[0]):
                            filtered.update(unk)
                    except (IndexError, AttributeError):
                        pass
            unknown.difference_update(filtered)
        else:
            Source.filter_unknown(self, unknown)
    filter_unknown.__doc__ = Source.filter_unknown.__doc__

    def setup_data(self, force_update=False):
        if not self.use_yum:
            Source.setup_data(self, force_update=force_update)
    setup_data.__doc__ = \
        "``setup_data`` is only used by the builtin yum parser.  " + \
        Source.setup_data.__doc__

    def get_repo_name(self, url_map):
        """ Try to find a sensible name for a repository.  First use a
        repository's Pulp ID, if it has one; if not, then defer to
        :class:`Bcfg2.Server.Plugins.Packages.Source.Source.get_repo_name`

        :param url_map: A single :attr:`url_map` dict, i.e., any
                        single element of :attr:`url_map`.
        :type url_map: dict
        :returns: string - the name of the repository.
        """
        if self.pulp_id:
            return self.pulp_id
        else:
            return Source.get_repo_name(self, url_map)

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
        try:
            yumgroup = self.yumgroups[group]
        except KeyError:
            return []
        packages = yumgroup['conditional'] + yumgroup['mandatory']
        if ptype in ['default', 'optional', 'all']:
            packages += yumgroup['default']
        if ptype in ['optional', 'all']:
            packages += yumgroup['optional']
        return packages
