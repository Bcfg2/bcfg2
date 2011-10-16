import os
import sys
import time
import copy
import glob
import socket
import random
import logging
import threading
import lxml.etree
from UserDict import DictMixin
import Bcfg2.Server.Plugin
from Bcfg2.Bcfg2Py3k import StringIO, cPickle, HTTPError, ConfigParser, file
from Bcfg2.Server.Plugins.Packages.Collection import Collection
from Bcfg2.Server.Plugins.Packages.Source import Source, fetch_url

logger = logging.getLogger("Packages")

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
    logger.info("Packages: No yum libraries found; forcing use of internal dependency "
                "resolver")

XP = '{http://linux.duke.edu/metadata/common}'
RP = '{http://linux.duke.edu/metadata/rpm}'
RPO = '{http://linux.duke.edu/metadata/repo}'
FL = '{http://linux.duke.edu/metadata/filelists}'

PULPSERVER = None
PULPCONFIG = None

def _setup_pulp(config):
    global PULPSERVER, PULPCONFIG
    if not has_pulp:
        logger.error("Packages: Cannot create Pulp collection: Pulp libraries not "
                     "found")
        raise Bcfg2.Server.Plugin.PluginInitError

    if PULPSERVER is None:
        try:
            username = config.get("pulp", "username")
            password = config.get("pulp", "password")
        except ConfigParser.NoSectionError:
            logger.error("Packages: No [pulp] section found in Packages/packages.conf")
            raise Bcfg2.Server.Plugin.PluginInitError
        except ConfigParser.NoOptionError:
            err = sys.exc_info()[1]
            logger.error("Packages: Required option not found in "
                         "Packages/packages.conf: %s" % err)
            raise Bcfg2.Server.Plugin.PluginInitError
        
        PULPCONFIG = ConsumerConfig()
        serveropts = PULPCONFIG.server
        
        PULPSERVER = server.PulpServer(serveropts['host'],
                                       int(serveropts['port']),
                                       serveropts['scheme'],
                                       serveropts['path'])
        PULPSERVER.set_basic_auth_credentials(username, password)
        server.set_active_server(PULPSERVER)
    return PULPSERVER


class CacheItem(object):
    def __init__(self, value, expiration=None):
        self.value = value
        if expiration:
            self.expiration = time.time() + expiration
    
    def expired(self):
        if self.expiration:
            return time.time() > self.expiration
        else:
            return False


class Cache(DictMixin):
    def __init__(self, expiration=None, tidy=None):
        """ params:
        - expiration: How many seconds a cache entry stays alive for.
          Specify None for no expiration.
        - tidy: How frequently to tidy the cache (remove all expired
          entries).  Without this, entries are only expired as they
          are accessed.  Cache will be tidied once per every <tidy>
          accesses to cache data; a sensible value might be, e.g.,
          10000.  Specify 0 to fully tidy the cache every access; this
          makes the cache much slower, but also smaller in memory.
          Specify None to never tidy the cache; this makes the cache
          faster, but potentially much larger in memory, especially if
          cache items are accessed infrequently."""
        self.cache = dict()
        self.expiration = expiration
        self.tidy = tidy
        self.access_count = 0
    
    def __getitem__(self, key):
        self._expire(key)
        if key in self.cache:
            return self.cache[key].value
        else:
            raise KeyError(key)
    
    def __setitem__(self, key, value):
        self.cache[key] = CacheItem(value, self.expiration)
    
    def __delitem__(self, key):
        del self.cache[key]
    
    def __contains__(self, key):
        self.expire(key)
        return key in self.cache
    
    def keys(self):
        return self.cache.keys()
    
    def __iter__(self):
        for k in self.cache.keys():
            try:
                yield k
            except KeyError:
                pass

    def iteritems(self):
        for k in self:
            try:
                yield (k, self[k])
            except KeyError:
                pass

    def _expire(self, *args):
        if args:
            self.access_count += 1
            if self.access_count >= self.tidy:
                self.access_count = 0
                candidates = self.cache.items()
            else:
                candidates = [(k, self.cache[k]) for k in args]
        else:
            candidates = self.cache.items()

        expire = []
        for key, item in candidates:
            if item.expired():
                expire.append(key)
        for key in expire:
            del self.cache[key]
    
    def clear(self):
        self.cache = dict()


class YumCollection(Collection):
    def __init__(self, metadata, sources, basepath):
        Collection.__init__(self, metadata, sources, basepath)
        self.keypath = os.path.join(self.basepath, "keys")

        if len(sources):
            config = sources[0].config
            self.use_yum = has_yum
            try:
                self.use_yum &= config.getboolean("yum", "use_yum_libraries")
            except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
                self.use_yum = False
        else:
            self.use_yum = False

        if self.use_yum:
            self._yb = None
            self.cachefile = os.path.join(self.cachepath,
                                         "cache-%s" % self.cachekey)
            if not os.path.exists(self.cachefile):
                os.mkdir(self.cachefile)
                
            self.configdir = os.path.join(self.basepath, "yum")
            if not os.path.exists(self.configdir):
                os.mkdir(self.configdir)
            self.cfgfile = os.path.join(self.configdir,
                                        "%s-yum.conf" % self.cachekey)
            if self.config.has_option("yum", "metadata_expire"):
                cache_expire = self.config.getint("yum", "metadata_expire")
            else:
                cache_expire = 21600
            
            self.pkgs_cache = Cache(expiration=cache_expire)
            self.deps_cache = Cache(expiration=cache_expire)
            self.vpkgs_cache = Cache(expiration=cache_expire)
            self.group_cache = Cache(expiration=cache_expire)
            self.pkgset_cache = Cache(expiration=cache_expire)

        if has_pulp:
            _setup_pulp(self.config)

    @property
    def yumbase(self):
        """ if we try to access a Yum SQLitePackageSack object in a
        different thread from the one it was created in, we get a
        nasty error.  but I can't find a way to detect when a new
        thread is started (which happens for every new client
        connection, I think), so this property creates a new YumBase
        object if the old YumBase object was created in a different
        thread than the current one.  (I definitely don't want to
        create a new YumBase object every time it's used, because that
        involves writing a temp file, at least for now.) """
        if not self.use_yum:
            self._yb = None
            self._yb_thread = None
        elif (self._yb is None or
              self._yb_thread != threading.current_thread().ident):
            self._yb = yum.YumBase()
            self._yb_thread = threading.current_thread().ident

            if not os.path.exists(self.cfgfile):
                # todo: detect yum version.  Supposedly very new
                # versions of yum have better support for
                # reconfiguring on the fly using the RepoStorage API
                yumconf = self.get_config(raw=True)
                yumconf.add_section("main")
            
                mainopts = dict(cachedir=self.cachefile,
                                keepcache="0",
                                sslverify="0",
                                reposdir="/dev/null")
                try:
                    for opt in self.config.options("yum"):
                        if opt != "use_yum_libraries":
                            mainopts[opt] = self.config.get("yum", opt)
                except ConfigParser.NoSectionError:
                    pass

                for opt, val in list(mainopts.items()):
                    yumconf.set("main", opt, val)

                yumconf.write(open(self.cfgfile, 'w'))

            # it'd be nice if we could change this to be more verbose
            # if -v was given, but Collection objects don't get setup.
            # It'd also be nice if we could tell yum to log to syslog,
            # but so would a unicorn.
            self._yb.preconf.debuglevel = 1
            self._yb.preconf.fn = self.cfgfile
        return self._yb

    def get_config(self, raw=False):
        config = ConfigParser.SafeConfigParser()
        for source in self.sources:
            # get_urls() loads url_map as a side-effect
            source.get_urls()
            for url_map in source.url_map:
                if url_map['arch'] in self.metadata.groups:
                    reponame = source.get_repo_name(url_map)
                    config.add_section(reponame)
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
        for source in self.sources:
            for key in source.gpgkeys:
                needkeys.add(key)

        if len(needkeys):
            keypkg = lxml.etree.Element('BoundPackage', name="gpg-pubkey",
                                        type=self.ptype, origin='Packages')

            for key in needkeys:
                # figure out the path of the key on the client
                try:
                    keydir = self.config.get("global", "gpg_keypath")
                except (ConfigParser.NoOptionError,
                        ConfigParser.NoSectionError):
                    keydir = "/etc/pki/rpm-gpg"
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
            independent.append(keypkg)

        # see if there are any pulp sources to handle
        has_pulp_sources = False
        for source in self.sources:
            if source.pulp_id:
                has_pulp_sources = True
                break

        if has_pulp_sources:
            consumerapi = ConsumerAPI()
            consumer = self._get_pulp_consumer(consumerapi=consumerapi)
            if consumer is None:
                consumer = consumerapi.create(self.metadata.hostname,
                                              self.metadata.hostname)
                lxml.etree.SubElement(independent, "BoundAction",
                                      name="pulp-update", timing="pre",
                                      when="always", status="check",
                                      command="pulp-consumer consumer update")

            for source in self.sources:
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
            logger.error("Packages: Could not contact Pulp server: %s" % err)
        except:
            err = sys.exc_info()[1]
            logger.error("Packages: Unknown error querying Pulp server: %s" % err)
        return consumer

    def _add_gpg_instances(self, keyentry, keydata, localkey, remotekey):
        """ add gpg keys to the specification to ensure they get
        installed """
        if self.use_yum:
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
            return Collection.is_package(self, package)

        if isinstance(package, tuple):
            if package[1] is None and package[2] == (None, None, None):
                package = package[0]
            else:
                return None

        try:
            return self.pkgs_cache[package]
        except KeyError:
            pass

        self.pkgs_cache[package] = bool(self.get_package_object(package,
                                                                silent=True))
        return self.pkgs_cache[package]

    def is_virtual_package(self, package):
        if self.use_yum:
            try:
                return bool(self.vpkgs_cache[package])
            except KeyError:
                return bool(self.get_provides(package, silent=True))
        else:
            return Collection.is_virtual_package(self, package)

    def get_package_object(self, package, silent=False):
        """ package objects cannot be cached since they are sqlite
        objects, so they can't be reused between threads. """
        try:
            matches = self.yumbase.pkgSack.returnNewestByName(name=package)
        except yum.Errors.PackageSackError:
            if not silent:
                self.logger.warning("Packages: Package '%s' not found" %
                                    self.get_package_name(package))
            matches = []
        except yum.Errors.RepoError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Temporary failure loading metadata "
                              "for '%s': %s" %
                              (self.get_package_name(package), err))
            matches = []

        pkgs = self._filter_arch(matches)
        if pkgs:
            return pkgs[0]
        else:
            return None

    def get_deps(self, package):
        if not self.use_yum:
            return Collection.get_deps(self, package)

        try:
            return self.deps_cache[package]
        except KeyError:
            pass

        pkg = self.get_package_object(package)
        deps = []
        if pkg:
            deps = set(pkg.requires)
            # filter out things the package itself provides
            deps.difference_update([dep for dep in deps
                                        if pkg.checkPrco('provides', dep)])
        else:
            self.logger.error("Packages: No package available: %s" %
                              self.get_package_name(package))
        self.deps_cache[package] = deps
        return self.deps_cache[package]

    def get_provides(self, required, all=False, silent=False):
        if not self.use_yum:
            return Collection.get_provides(self, package)

        if not isinstance(required, tuple):
            required = (required, None, (None, None, None))

        try:
            return self.vpkgs_cache[required]
        except KeyError:
            pass
        
        try:
            prov = \
                self.yumbase.whatProvides(*required).returnNewestByNameArch()
        except yum.Errors.NoMoreMirrorsRepoError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: Temporary failure loading metadata "
                              "for '%s': %s" %
                              (self.get_package_name(required),
                               err))
            self.vpkgs_cache[required] = None
            return []

        if prov and not all:
            prov = self._filter_provides(required, prov)
        elif not prov and not silent:
            self.logger.error("Packages: No package provides %s" %
                              self.get_package_name(required))
        self.vpkgs_cache[required] = prov
        return self.vpkgs_cache[required]

    def get_group(self, group):
        if not self.use_yum:
            self.logger.warning("Packages: Package groups are not supported by Bcfg2's "
                                "internal Yum dependency generator")
            return []

        if group.startswith("@"):
            group = group[1:]

        try:
            return self.group_cache[group]
        except KeyError:
            pass
        
        try:
            if self.yumbase.comps.has_group(group):
                pkgs = self.yumbase.comps.return_group(group).packages
            else:
                self.logger.warning("Packages: '%s' is not a valid group" %
                                    group)
                pkgs = []
        except yum.Errors.GroupsError:
            err = sys.exc_info()[1]
            self.logger.warning("Packages: %s" % err)
            pkgs = []

        self.group_cache[group] = pkgs
        return self.group_cache[group]

    def _filter_provides(self, package, providers):
        providers = [pkg for pkg in self._filter_arch(providers)]
        if len(providers) > 1:
            # go through each provider and make sure it's the newest
            # package of its name available.  If we have multiple
            # providers, avoid installing old packages.
            #
            # For instance: on Fedora 14,
            # perl-Sub-WrapPackages-2.0-2.fc14 erroneously provided
            # perl(lib), which should not have been provided;
            # perl(lib) is provided by the "perl" package.  The bogus
            # provide was removed in perl-Sub-WrapPackages-2.0-4.fc14,
            # but if we just queried to resolve the "perl(lib)"
            # dependency, we'd get both packages.  By performing this
            # check, we learn that there's a newer
            # perl-Sub-WrapPackages available, so it can't be the best
            # provider of perl(lib).
            rv = []
            for pkg in providers:
                if self.get_package_object(pkg.name) == pkg:
                    rv.append(pkg)
        else:
            rv = providers
        return [p.name for p in rv]

    def _filter_arch(self, packages):
        groups = set(list(self.get_relevant_groups()) + ["noarch"])
        matching = [pkg for pkg in packages if pkg.arch in groups]
        if matching:
            return matching
        else:
            # no packages match architecture; we'll assume that the
            # user knows what s/he is doing and this is a multiarch
            # box.
            return packages

    def get_package_name(self, package):
        """ get the name of a package or virtual package from the
        internal representation used by this Collection class """
        if self.use_yum and isinstance(package, tuple):
            return yum.misc.prco_tuple_to_string(package)
        else:
            return str(package)

    def complete(self, packagelist):
        if not self.use_yum:
            return Collection.complete(self, packagelist)

        cachekey = cPickle.dumps(sorted(packagelist))
        try:
            packages = self.pkgset_cache[cachekey]
        except KeyError:
            packages = set()

        pkgs = set(packagelist).difference(packages)    
        requires = set()
        satisfied = set()
        unknown = set()
        final_pass = False

        while requires or pkgs:
            # infinite loop protection
            start_reqs = len(requires)
            
            while pkgs:
                package = pkgs.pop()
                if package in packages:
                    continue
                
                if not self.is_package(package):
                    # try this package out as a requirement
                    requires.add((package, None, (None, None, None)))
                    continue

                packages.add(package)
                reqs = set(self.get_deps(package)).difference(satisfied)
                if reqs:
                    requires.update(reqs)

            reqs_satisfied = set()
            for req in requires:
                if req in satisfied:
                    reqs_satisfied.add(req)
                    continue

                if req[1] is None and self.is_package(req[0]):
                    if req[0] not in packages:
                        pkgs.add(req[0])
                    reqs_satisfied.add(req)
                    continue
                    
                self.logger.debug("Packages: Handling requirement '%s'" %
                                  self.get_package_name(req))
                providers = list(set(self.get_provides(req)))
                if len(providers) > 1:
                    # hopefully one of the providing packages is already
                    # included
                    best = [p for p in providers if p in packages]
                    if best:
                        providers = best
                    else:
                        # pick a provider whose name matches the requirement
                        best = [p for p in providers if p == req[0]]
                        if len(best) == 1:
                            providers = best
                        elif not final_pass:
                            # found no "best" package, so defer
                            providers = None
                        # else: found no "best" package, but it's the
                        # final pass, so include them all
                
                if providers:
                    self.logger.debug("Packages: Requirement '%s' satisfied "
                                      "by %s" %
                                     (self.get_package_name(req),
                                      ",".join([self.get_package_name(p)
                                                for p in providers])))
                    newpkgs = set(providers).difference(packages)
                    if newpkgs:
                        for package in newpkgs:
                            if self.is_package(package):
                                pkgs.add(package)
                            else:
                                unknown.add(package)
                    reqs_satisfied.add(req)
                elif providers is not None:
                    # nothing provided this requirement at all
                    unknown.add(req)
                    reqs_satisfied.add(req)
                # else, defer
            requires.difference_update(reqs_satisfied)

            # infinite loop protection
            if len(requires) == start_reqs and len(pkgs) == 0:
                final_pass = True

            if final_pass and requires:
                unknown.update(requires)
                requires = set()

        self.filter_unknown(unknown)
        unknown = [self.get_package_name(p) for p in unknown]

        # we do not cache unknown packages, since those are likely to
        # be fixed
        self.pkgset_cache[cachekey] = packages

        return packages, unknown

    def setup_data(self, force_update=False):
        if not self.use_yum:
            return Collection.setup_data(self, force_update)

        for cfile in glob.glob(os.path.join(self.configdir, "*-yum.conf")):
            os.unlink(cfile)
            self._yb = None
        
        self.pkgs_cache.clear()
        self.deps_cache.clear()
        self.vpkgs_cache.clear()
        self.group_cache.clear()
        self.pkgset_cache.clear()
        
        if force_update:
            for mdtype in ["Headers", "Packages", "Sqlite", "Metadata",
                           "ExpireCache"]:
                # for reasons that are entirely obvious, all of the
                # yum API clean* methods return a tuple of 0 (zero,
                # always zero) and a list containing a single message
                # about how many files were deleted.  so useful.
                # thanks, yum.
                self.logger.info("Packages: %s" %
                                 getattr(self.yumbase,
                                         "clean%s" % mdtype)()[1][0])


class YumSource(Source):
    basegroups = ['yum', 'redhat', 'centos', 'fedora']
    ptype = 'yum'

    def __init__(self, basepath, xsource, config):
        Source.__init__(self, basepath, xsource, config)
        self.pulp_id = None
        if has_pulp and xsource.get("pulp_id"):
            self.pulp_id = xsource.get("pulp_id")
            
            _setup_pulp(self.config)
            repoapi = RepositoryAPI()
            try:
                self.repo = repoapi.repository(self.pulp_id)
                self.gpgkeys = ["%s/%s" % (PULPCONFIG.cds['keyurl'], key)
                                for key in repoapi.listkeys(self.pulp_id)]
            except server.ServerRequestError:
                err = sys.exc_info()[1]
                if err[0] == 401:
                    msg = "Packages: Error authenticating to Pulp: %s" % err[1]
                elif err[0] == 404:
                    msg = "Packages: Pulp repo id %s not found: %s" % (self.pulp_id,
                                                             err[1])
                else:
                    msg = "Packages: Error %d fetching pulp repo %s: %s" % (err[0],
                                                                  self.pulp_id,
                                                                  err[1])
                logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginInitError
            except socket.error:
                err = sys.exc_info()[1]
                logger.error("Packages: Could not contact Pulp server: %s" % err)
                raise Bcfg2.Server.Plugin.PluginInitError
            except:
                err = sys.exc_info()[1]
                logger.error("Packages: Unknown error querying Pulp server: %s" % err)
                raise Bcfg2.Server.Plugin.PluginInitError
            self.rawurl = "%s/%s" % (PULPCONFIG.cds['baseurl'],
                                     self.repo['relative_path'])
            self.arches = [self.repo['arch']]
        
        if not self.rawurl:
            self.baseurl = self.url + "%(version)s/%(component)s/%(arch)s/"
        else:
            self.baseurl = self.rawurl
        self.packages = dict()
        self.deps = dict([('global', dict())])
        self.provides = dict([('global', dict())])
        self.filemap = dict([(x, dict())
                             for x in ['global'] + self.arches])
        self.needed_paths = set()
        self.file_to_arch = dict()

        self.use_yum = has_yum
        try:
            self.use_yum &= config.getboolean("yum", "use_yum_libraries")
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            self.use_yum = False

    def save_state(self):
        if not self.use_yum:
            cache = file(self.cachefile, 'wb')
            cPickle.dump((self.packages, self.deps, self.provides,
                          self.filemap, self.url_map), cache, 2)
            cache.close()
            

    def load_state(self):
        if not self.use_yum:
            data = file(self.cachefile)
            (self.packages, self.deps, self.provides,
             self.filemap, self.url_map) = cPickle.load(data)

    def get_urls(self):
        surls = list()
        self.url_map = []
        for arch in self.arches:
            if self.url:
                usettings = [{'version':self.version, 'component':comp,
                              'arch':arch}
                             for comp in self.components]
            else: # rawurl given 
                usettings = [{'version':self.version, 'component':None,
                              'arch':arch}]

            for setting in usettings:
                setting['url'] = self.baseurl % setting
                self.url_map.append(copy.deepcopy(setting))
            surls.append((arch, [setting['url'] for setting in usettings]))
        urls = []
        for (sarch, surl_list) in surls:
            for surl in surl_list:
                urls.extend(self._get_urls_from_repodata(surl, sarch))
        return urls
    urls = property(get_urls)

    def _get_urls_from_repodata(self, url, arch):
        if self.use_yum:
            return [url]
        
        rmdurl = '%srepodata/repomd.xml' % url
        try:
            repomd = fetch_url(rmdurl)
            xdata = lxml.etree.XML(repomd)
        except ValueError:
            logger.error("Packages: Bad url string %s" % rmdurl)
            return []
        except HTTPError:
            err = sys.exc_info()[1]
            logger.error("Packages: Failed to fetch url %s. code=%s" %
                         (rmdurl, err.code))
            return []
        except lxml.etree.XMLSyntaxError:
            err = sys.exc_info()[1]
            logger.error("Packages: Failed to process metadata at %s: %s" %
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
            pre = pdata.find(RP + 'requires')
            self.deps[arch][pkgname] = set()
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
