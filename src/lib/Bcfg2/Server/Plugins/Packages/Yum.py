import os
import re
import sys
import copy
import socket
import logging
import lxml.etree
from subprocess import Popen, PIPE
import Bcfg2.Server.Plugin
from Bcfg2.Compat import StringIO, cPickle, HTTPError, URLError, \
    ConfigParser, json
from Bcfg2.Server.Plugins.Packages.Collection import _Collection
from Bcfg2.Server.Plugins.Packages.Source import SourceInitError, Source, \
     fetch_url

logger = logging.getLogger(__name__)

try:
    from pulp.client.consumer.config import ConsumerConfig
    from pulp.client.api.repository import RepositoryAPI
    from pulp.client.api.consumer import ConsumerAPI
    from pulp.client.api import server
    has_pulp = True
except ImportError:
    has_pulp = False

try:
    import yum
    has_yum = True
except ImportError:
    has_yum = False
    logger.info("Packages: No yum libraries found; forcing use of internal "
                "dependency resolver")

XP = '{http://linux.duke.edu/metadata/common}'
RP = '{http://linux.duke.edu/metadata/rpm}'
RPO = '{http://linux.duke.edu/metadata/repo}'
FL = '{http://linux.duke.edu/metadata/filelists}'

PULPSERVER = None
PULPCONFIG = None


def _setup_pulp(setup):
    global PULPSERVER, PULPCONFIG
    if not has_pulp:
        msg = "Packages: Cannot create Pulp collection: Pulp libraries not found"
        logger.error(msg)
        raise Bcfg2.Server.Plugin.PluginInitError(msg)

    if PULPSERVER is None:
        try:
            username = setup.cfp.get("packages:pulp", "username")
            password = setup.cfp.get("packages:pulp", "password")
        except ConfigParser.NoSectionError:
            msg = "Packages: No [pulp] section found in Packages/packages.conf"
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginInitError(msg)
        except ConfigParser.NoOptionError:
            msg = "Packages: Required option not found in Packages/packages.conf: %s" % sys.exc_info()[1]
            logger.error(msg)
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


class YumCollection(_Collection):
    #: YumCollections support package groups
    __package_groups__ = True

    #: Options that are included in the [packages:yum] section of the
    #: config but that should not be included in the temporary
    #: yum.conf we write out
    option_blacklist = ["use_yum_libraries", "helper"]

    def __init__(self, metadata, sources, basepath, debug=False):
        _Collection.__init__(self, metadata, sources, basepath, debug=debug)
        self.keypath = os.path.join(self.basepath, "keys")

        if self.use_yum:
            self.cachefile = os.path.join(self.cachepath,
                                         "cache-%s" % self.cachekey)
            if not os.path.exists(self.cachefile):
                os.mkdir(self.cachefile)

            self.cfgfile = os.path.join(self.cachefile, "yum.conf")
            self.write_config()
        if has_pulp and self.has_pulp_sources:
            _setup_pulp(self.setup)

        self._helper = None

    @property
    def helper(self):
        try:
            return self.setup.cfp.get("packages:yum", "helper")
        except:
            pass

        if not self._helper:
            # first see if bcfg2-yum-helper is in PATH
            try:
                Popen(['bcfg2-yum-helper'],
                      stdin=PIPE, stdout=PIPE, stderr=PIPE).wait()
                self._helper = 'bcfg2-yum-helper'
            except OSError:
                self._helper = "/usr/sbin/bcfg2-yum-helper"
        return self._helper

    @property
    def use_yum(self):
        return has_yum and self.setup.cfp.getboolean("packages:yum",
                                                     "use_yum_libraries",
                                                     default=False)

    @property
    def has_pulp_sources(self):
        """ see if there are any pulp sources to handle """
        for source in self:
            if source.pulp_id:
                return True
        return False

    def write_config(self):
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

    def get_config(self, raw=False):
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
                        match = re.search("-(\d+)", reponame)
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

    def build_extra_structures(self, independent):
        """ build list of gpg keys to be added to the specification by
        validate_structures() """
        needkeys = set()
        for source in self:
            for key in source.gpgkeys:
                needkeys.add(key)

        if len(needkeys):
            if has_yum:
                # this must be be has_yum, not use_yum, because
                # regardless of whether the user wants to use the yum
                # resolver we want to include gpg key data
                keypkg = lxml.etree.Element('BoundPackage', name="gpg-pubkey",
                                            type=self.ptype, origin='Packages')
            else:
                self.logger.warning("GPGKeys were specified for yum sources in "
                                    "sources.xml, but no yum libraries were "
                                    "found")
                self.logger.warning("GPG key version/release data cannot be "
                                    "determined automatically")
                self.logger.warning("Install yum libraries, or manage GPG keys "
                                    "manually")
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
                                             type='file', perms='0644',
                                             important='true')
                keypath.text = kdata

                # hook to add version/release info if possible
                self._add_gpg_instances(keypkg, kdata, localkey, remotekey)
                independent.append(keypath)
            if keypkg is not None:
                independent.append(keypkg)

        if self.has_pulp_sources:
            consumerapi = ConsumerAPI()
            consumer = self._get_pulp_consumer(consumerapi=consumerapi)
            if consumer is None:
                consumer = consumerapi.create(self.metadata.hostname,
                                              self.metadata.hostname)
                lxml.etree.SubElement(independent, "BoundAction",
                                      name="pulp-update", timing="pre",
                                      when="always", status="check",
                                      command="pulp-consumer consumer update")

            for source in self:
                # each pulp source can only have one arch, so we don't
                # have to check the arch in url_map
                if (source.pulp_id and
                    source.pulp_id not in consumer['repoids']):
                    consumerapi.bind(self.metadata.hostname, source.pulp_id)

            crt = lxml.etree.SubElement(independent, "BoundPath",
                                        name="/etc/pki/consumer/cert.pem",
                                        type="file", owner="root",
                                        group="root", perms="0644")
            crt.text = consumerapi.certificate(self.metadata.hostname)

    def _get_pulp_consumer(self, consumerapi=None):
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
            self.logger.error("Packages: Unknown error querying Pulp server: %s"
                              % err)
        return consumer

    def _add_gpg_instances(self, keyentry, keydata, localkey, remotekey):
        """ add gpg keys to the specification to ensure they get
        installed """
        # this must be be has_yum, not use_yum, because regardless of
        # whether the user wants to use the yum resolver we want to
        # include gpg key data
        if not has_yum:
            return

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

    def is_package(self, package):
        if not self.use_yum:
            return _Collection.is_package(self, package)
        elif isinstance(package, tuple):
            if package[1] is None and package[2] == (None, None, None):
                package = package[0]
            else:
                return None
        else:
            # this should really never get called; it's just provided
            # for API completeness
            return self.call_helper("is_package", package)

    def is_virtual_package(self, package):
        if not self.use_yum:
            return _Collection.is_virtual_package(self, package)
        else:
            # this should really never get called; it's just provided
            # for API completeness
            return self.call_helper("is_virtual_package", package)

    def get_deps(self, package):
        if not self.use_yum:
            return _Collection.get_deps(self, package)
        else:
            # this should really never get called; it's just provided
            # for API completeness
            return self.call_helper("get_deps", package)

    def get_provides(self, required, all=False, silent=False):
        if not self.use_yum:
            return _Collection.get_provides(self, required)
        else:
            # this should really never get called; it's just provided
            # for API completeness
            return self.call_helper("get_provides", required)

    def get_groups(self, grouplist):
        if not self.use_yum:
            self.logger.warning("Packages: Package groups are not supported by "
                                "Bcfg2's internal Yum dependency generator")
            return dict()

        if not grouplist:
            return dict()

        gdicts = []
        for group, ptype in grouplist:
            if group.startswith("@"):
                group = group[1:]
            if not ptype:
                ptype = "default"
            gdicts.append(dict(group=group, type=ptype))

        return self.call_helper("get_groups", gdicts)

    def get_group(self, group, ptype="default"):
        if not self.use_yum:
            self.logger.warning("Packages: Package groups are not supported by "
                                "Bcfg2's internal Yum dependency generator")
            return []

        if group.startswith("@"):
            group = group[1:]

        return self.call_helper("get_group", dict(group=group, type=ptype))

    def packages_from_entry(self, entry):
        rv = set()
        name = entry.get("name")

        def _tag_to_pkg(tag):
            rv = [name, tag.get("arch"), tag.get("epoch"),
                  tag.get("version"), tag.get("release")]
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

        for inst in entry.getchildren():
            if inst.tag != "Instance":
                continue
            rv.add(_tag_to_pkg(inst))
        if not rv:
            rv.add(_tag_to_pkg(entry))
        return list(rv)

    def packages_to_entry(self, pkglist, entry):
        def _get_entry_attrs(pkgtup):
            attrs = dict(version=self.setup.cfp.get("packages",
                                                    "version",
                                                    default="auto"))
            if attrs['version'] == 'any':
                return attrs

            if pkgtup[1]:
                attrs['arch'] = pkgtup[1]
            if pkgtup[2]:
                attrs['epoch'] = pkgtup[2]
            if pkgtup[3]:
                attrs['version'] = pkgtup[3]
            if pkgtup[4]:
                attrs['release'] = pkgtup[4]
            return attrs

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
                                          _get_entry_attrs(inst))
            else:
                attrs = _get_entry_attrs(instances[0])
                attrs.update(pkgattrs)
                lxml.etree.SubElement(entry, 'BoundPackage', **attrs)

    def get_new_packages(self, initial, complete):
        initial_names = []
        for pkg in initial:
            if isinstance(pkg, tuple):
                initial_names.append(pkg[0])
            else:
                initial_names.append(pkg)
        new = []
        for pkg in complete:
            if pkg[0] not in initial_names:
                new.append(pkg)
        return new

    def complete(self, packagelist):
        if not self.use_yum:
            return _Collection.complete(self, packagelist)

        if packagelist:
            result = \
                self.call_helper("complete",
                                 dict(packages=list(packagelist),
                                      groups=list(self.get_relevant_groups())))
            if not result:
                # some sort of error, reported by call_helper()
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

    def call_helper(self, command, input=None):
        """ Make a call to bcfg2-yum-helper.  The yum libs have
        horrific memory leaks, so apparently the right way to get
        around that in long-running processes it to have a short-lived
        helper.  No, seriously -- check out the yum-updatesd code.
        It's pure madness. """
        cmd = [self.helper, "-c", self.cfgfile]
        verbose = self.debug_flag or self.setup['verbose']
        if verbose:
            cmd.append("-v")
        cmd.append(command)
        self.debug_log("Packages: running %s" % " ".join(cmd), flag=verbose)
        try:
            helper = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Failed to execute %s: %s" %
                              (" ".join(cmd), err))
            return None

        if input:
            idata = json.dumps(input)
            (stdout, stderr) = helper.communicate(idata)
        else:
            (stdout, stderr) = helper.communicate()
        rv = helper.wait()
        if rv:
            self.logger.error("Packages: error running bcfg2-yum-helper "
                              "(returned %d): %s" % (rv, stderr))
        else:
            self.debug_log("Packages: debug info from bcfg2-yum-helper: %s" %
                           stderr, flag=verbose)
        try:
            return json.loads(stdout)
        except ValueError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: error reading bcfg2-yum-helper "
                              "output: %s" % err)
            return None

    def setup_data(self, force_update=False):
        if not self.use_yum:
            return _Collection.setup_data(self, force_update)

        if force_update:
            # we call this twice: one to clean up data from the old
            # config, and once to clean up data from the new config
            self.call_helper("clean")

        os.unlink(self.cfgfile)
        self.write_config()

        if force_update:
            self.call_helper("clean")


class YumSource(Source):
    basegroups = ['yum', 'redhat', 'centos', 'fedora']
    ptype = 'yum'

    def __init__(self, basepath, xsource, setup):
        Source.__init__(self, basepath, xsource, setup)
        self.pulp_id = None
        if has_pulp and xsource.get("pulp_id"):
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
                raise SourceInitError("Could not contact Pulp server: %s" % err)
            except:
                err = sys.exc_info()[1]
                raise SourceInitError("Unknown error querying Pulp server: %s" %
                                      err)
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

    @property
    def use_yum(self):
        return has_yum and self.setup.cfp.getboolean("packages:yum",
                                                     "use_yum_libraries",
                                                     default=False)

    def save_state(self):
        if not self.use_yum:
            cache = open(self.cachefile, 'wb')
            cPickle.dump((self.packages, self.deps, self.provides,
                          self.filemap, self.url_map), cache, 2)
            cache.close()

    def load_state(self):
        if not self.use_yum:
            data = open(self.cachefile)
            (self.packages, self.deps, self.provides,
             self.filemap, self.url_map) = cPickle.load(data)

    def get_urls(self):
        return [self._get_urls_from_repodata(m['url'], m['arch'])
                for m in self.url_map]
    urls = property(get_urls)

    def _get_urls_from_repodata(self, url, arch):
        if self.use_yum:
            return [url]

        rmdurl = '%srepodata/repomd.xml' % url
        try:
            repomd = fetch_url(rmdurl)
            xdata = lxml.etree.XML(repomd)
        except ValueError:
            self.logger.error("Packages: Bad url string %s" % rmdurl)
            return []
        except URLError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Failed to fetch url %s. %s" %
                              (rmdurl, err))
            return []
        except HTTPError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Failed to fetch url %s. code=%s" %
                              (rmdurl, err.code))
            return []
        except lxml.etree.XMLSyntaxError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Failed to process metadata at %s: %s" %
                              (rmdurl, err))
            return []

        urls = []
        for elt in xdata.findall(RPO + 'data'):
            if elt.get('type') in ['filelists', 'primary']:
                floc = elt.find(RPO + 'location')
                fullurl = url + floc.get('href')
                urls.append(fullurl)
                self.file_to_arch[self.escape_url(fullurl)] = arch
        return urls

    def read_files(self):
        # we have to read primary.xml first, and filelists.xml afterwards;
        primaries = list()
        filelists = list()
        for fname in self.files:
            if fname.endswith('primary.xml.gz'):
                primaries.append(fname)
            elif fname.endswith('filelists.xml.gz'):
                filelists.append(fname)

        for fname in primaries:
            farch = self.file_to_arch[fname]
            fdata = lxml.etree.parse(fname).getroot()
            self.parse_primary(fdata, farch)
        for fname in filelists:
            farch = self.file_to_arch[fname]
            fdata = lxml.etree.parse(fname).getroot()
            self.parse_filelist(fdata, farch)

        # merge data
        sdata = list(self.packages.values())
        try:
            self.packages['global'] = copy.deepcopy(sdata.pop())
        except IndexError:
            logger.error("Packages: No packages in repo")
        while sdata:
            self.packages['global'] = \
                self.packages['global'].intersection(sdata.pop())

        for key in self.packages:
            if key == 'global':
                continue
            self.packages[key] = \
                self.packages[key].difference(self.packages['global'])
        self.save_state()

    def parse_filelist(self, data, arch):
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

    def parse_primary(self, data, arch):
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
            if pro != None:
                for entry in pro.getchildren():
                    prov = entry.get('name')
                    if prov not in self.provides[arch]:
                        self.provides[arch][prov] = list()
                    self.provides[arch][prov].append(pkgname)

    def is_package(self, metadata, item):
        arch = [a for a in self.arches if a in metadata.groups]
        if not arch:
            return False
        return ((item in self.packages['global'] or
                 item in self.packages[arch[0]]) and
                item not in self.blacklist and
                (len(self.whitelist) == 0 or item in self.whitelist))

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

    def filter_unknown(self, unknown):
        if self.use_yum:
            filtered = set()
            for unk in unknown:
                try:
                    if unk.startswith('rpmlib'):
                        filtered.update(unk)
                except AttributeError:
                    try:
                        if unk[0].startswith('rpmlib'):
                            filtered.update(unk)
                    except (IndexError, AttributeError):
                        pass
        else:
            filtered = set([u for u in unknown if u.startswith('rpmlib')])
        unknown.difference_update(filtered)

    def setup_data(self, force_update=False):
        if not self.use_yum:
            Source.setup_data(self, force_update=force_update)

    def get_repo_name(self, url_map):
        if self.pulp_id:
            return self.pulp_id
        else:
            return Source.get_repo_name(self, url_map)
