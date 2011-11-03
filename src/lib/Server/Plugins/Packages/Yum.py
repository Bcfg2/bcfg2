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
from subprocess import Popen, PIPE, STDOUT
import Bcfg2.Server.Plugin
from Bcfg2.Bcfg2Py3k import StringIO, cPickle, HTTPError, ConfigParser, file
from Bcfg2.Server.Plugins.Packages.Collection import Collection
from Bcfg2.Server.Plugins.Packages.Source import SourceInitError, Source, \
     fetch_url

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
    logger.info("Packages: No yum libraries found; forcing use of internal "
                "dependency resolver")

try:
    import json
except ImportError:
    import simplejson as json

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


class YumCollection(Collection):
    # options that are included in the [yum] section but that should
    # not be included in the temporary yum.conf we write out
    option_blacklist = ["use_yum_libraries", "helper"]
    
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
            self.cachefile = os.path.join(self.cachepath,
                                         "cache-%s" % self.cachekey)
            if not os.path.exists(self.cachefile):
                os.mkdir(self.cachefile)
                
            self.configdir = os.path.join(self.basepath, "yum")
            if not os.path.exists(self.configdir):
                os.mkdir(self.configdir)
            self.cfgfile = os.path.join(self.configdir,
                                        "%s-yum.conf" % self.cachekey)
            self.write_config()

            try:
                self.helper = self.config.get("yum", "helper")
            except ConfigParser.NoOptionError:
                self.helper = "/usr/sbin/bcfg2-yum-helper"
            
        if has_pulp:
            _setup_pulp(self.config)

    def write_config(self):
        if not os.path.exists(self.cfgfile):
            yumconf = self.get_config(raw=True)
            yumconf.add_section("main")
            
            mainopts = dict(cachedir=self.cachefile,
                            keepcache="0",
                            sslverify="0",
                            reposdir="/dev/null")
            try:
                for opt in self.config.options("yum"):
                    if opt not in self.option_blacklist:
                        mainopts[opt] = self.config.get("yum", opt)
            except ConfigParser.NoSectionError:
                pass

            for opt, val in list(mainopts.items()):
                yumconf.set("main", opt, val)

            yumconf.write(open(self.cfgfile, 'w'))

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
            return Collection.is_virtual_package(self, package)
        else:
            # this should really never get called; it's just provided
            # for API completeness
            return self.call_helper("is_virtual_package", package)

    def get_deps(self, package):
        if not self.use_yum:
            return Collection.get_deps(self, package)
        else:
            # this should really never get called; it's just provided
            # for API completeness
            return self.call_helper("get_deps", package)

    def get_provides(self, required, all=False, silent=False):
        if not self.use_yum:
            return Collection.get_provides(self, package)
        else:
            # this should really never get called; it's just provided
            # for API completeness
            return self.call_helper("get_provides", package)

    def get_group(self, group, ptype="default"):
        if not self.use_yum:
            self.logger.warning("Packages: Package groups are not supported by "
                                "Bcfg2's internal Yum dependency generator")
            return []

        if group.startswith("@"):
            group = group[1:]

        pkgs = self.call_helper("get_group", dict(group=group, type=ptype))
        return pkgs

    def complete(self, packagelist):
        if not self.use_yum:
            return Collection.complete(self, packagelist)

        packages = set()
        unknown = set(packagelist)

        if unknown:
            result = \
                self.call_helper("complete",
                                 dict(packages=list(unknown),
                                      groups=list(self.get_relevant_groups())))
            if result and "packages" in result and "unknown" in result:
                # we stringify every package because it gets returned
                # in unicode; set.update() doesn't work if some
                # elements are unicode and other are strings.  (I.e.,
                # u'foo' and 'foo' get treated as unique elements.)
                packages.update([str(p) for p in result['packages']])
                unknown = set([str(p) for p in result['unknown']])

            self.filter_unknown(unknown)
        
        return packages, unknown

    def call_helper(self, command, input=None):
        """ Make a call to bcfg2-yum-helper.  The yum libs have
        horrific memory leaks, so apparently the right way to get
        around that in long-running processes it to have a short-lived
        helper.  No, seriously -- check out the yum-updatesd code.
        It's pure madness. """
        # it'd be nice if we could change this to be more verbose if
        # -v was given to bcfg2-server, but Collection objects don't
        # get the 'setup' variable, so we don't know how verbose
        # bcfg2-server is.  It'd also be nice if we could tell yum to
        # log to syslog.  So would a unicorn.
        cmd = [self.helper, "-c", self.cfgfile, command]
        self.logger.debug("Packages: running %s" % " ".join(cmd))
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
        try:
            return json.loads(stdout)
        except ValueError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: error reading bcfg2-yum-helper "
                              "output: %s" % err)
            return None

    def setup_data(self, force_update=False):
        if not self.use_yum:
            return Collection.setup_data(self, force_update)

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
