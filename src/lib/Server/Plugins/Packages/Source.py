import os
import re
import sys
import Bcfg2.Server.Plugin
from Bcfg2.Bcfg2Py3k import HTTPError, HTTPBasicAuthHandler, \
     HTTPPasswordMgrWithDefaultRealm, install_opener, build_opener, \
     urlopen, file, cPickle

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

def fetch_url(url):
    if '@' in url:
        mobj = re.match('(\w+://)([^:]+):([^@]+)@(.*)$', url)
        if not mobj:
            raise ValueError
        user = mobj.group(2)
        passwd = mobj.group(3)
        url = mobj.group(1) + mobj.group(4)
        auth = HTTPBasicAuthHandler(HTTPPasswordMgrWithDefaultRealm())
        auth.add_password(None, url, user, passwd)
        install_opener(build_opener(auth))
    return urlopen(url).read()


class SourceInitError(Exception):
    pass


class Source(Bcfg2.Server.Plugin.Debuggable):
    mrepo_re = re.compile(r'/RPMS\.([^/]+)')
    pulprepo_re = re.compile(r'pulp/repos/([^/]+)')
    genericrepo_re = re.compile('https?://.*?/([^/]+)/?$')
    basegroups = []

    def __init__(self, basepath, xsource, config):
        Bcfg2.Server.Plugin.Debuggable.__init__(self)
        self.basepath = basepath
        self.xsource = xsource
        self.config = config

        try:
            self.version = xsource.find('Version').text
        except AttributeError:
            self.version = None

        for key, tag in [('components', 'Component'), ('arches', 'Arch'),
                         ('blacklist', 'Blacklist'),
                         ('whitelist', 'Whitelist')]:
            setattr(self, key, [item.text for item in xsource.findall(tag)])
        self.server_options = dict()
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

        self.gpgkeys = [el.text for el in xsource.findall("GPGKey")]

        self.recommended = xsource.get('recommended', 'false').lower() == 'true'
    
        self.rawurl = xsource.get('rawurl', '')
        if self.rawurl and not self.rawurl.endswith("/"):
            self.rawurl += "/"
        self.url = xsource.get('url', '')
        if self.url and not self.url.endswith("/"):
            self.url += "/"
        self.version = xsource.get('version', '')

        # build the set of conditions to see if this source applies to
        # a given set of metadata
        self.conditions = []
        self.groups = [] # provided for some limited backwards compat
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

        self.deps = dict()
        self.provides = dict()

        self.cachefile = os.path.join(self.basepath,
                                      "cache-%s" % self.cachekey)
        if not self.rawurl:
            self.baseurl = self.url + "%(version)s/%(component)s/%(arch)s/"
        else:
            self.baseurl = self.rawurl
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
                setting['url'] = self.baseurl % setting
            self.url_map.extend(usettings)

    @property
    def cachekey(self):
        return md5(cPickle.dumps([self.version, self.components, self.url,
                                  self.rawurl, self.arches])).hexdigest()

    def get_relevant_groups(self, metadata):
        return sorted(list(set([g for g in metadata.groups
                                if (g in self.basegroups or
                                    g in self.groups or
                                    g in self.arches)])))

    def load_state(self):
        pass

    def setup_data(self, force_update=False):
        should_read = True
        should_download = False
        if os.path.exists(self.cachefile):
            try:
                self.load_state()
                should_read = False 
            except:
                self.logger.error("Packages: Cachefile %s load failed; "
                                  "falling back to file read" % self.cachefile)
        if should_read:
            try:
                self.read_files()
            except:
                self.logger.error("Packages: File read failed; "
                                  "falling back to file download")
                should_download = True

        if should_download or force_update:
            try:
                self.update()
                self.read_files()
            except:
                self.logger.error("Packages: Failed to load data for Source "
                                  "of %s. Some Packages will be missing." %
                                  self.urls)

    def get_repo_name(self, url_map):
        # try to find a sensible name for a repo
        if url_map['component']:
            rname = url_map['component']
        else:
            name = None
            for repo_re in (self.mrepo_re,
                            self.pulprepo_re,
                            self.genericrepo_re):
                match = repo_re.search(url_map['url'])
                if match:
                    name = match.group(1)
                    break
            if name is not None:
                rname = "%s-%s" % (self.groups[0], name)
            else:
                rname = self.groups[0]
        # see yum/__init__.py in the yum source, lines 441-449, for
        # the source of this regex.  yum doesn't like anything but
        # string.ascii_letters, string.digits, and [-_.:].  There
        # doesn't seem to be a reason for this, because yum.
        return re.sub(r'[^A-Za-z0-9-_.:]', '-', rname)

    def __str__(self):
        if self.rawurl:
            return "%s at %s" % (self.__class__.__name__, self.rawurl)
        elif self.url:
            return "%s at %s" % (self.__class__.__name__, self.url)
        else:
            return self.__class__.__name__

    def get_urls(self):
        return []
    urls = property(get_urls)

    def get_files(self):
        return [self.escape_url(url) for url in self.urls]
    files = property(get_files)

    def get_vpkgs(self, metadata):
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

    def is_virtual_package(self, metadata, package):
        """ called to determine if a package is a virtual package.
        this is only invoked if the package is not listed in the dict
        returned by get_vpkgs """
        return False

    def escape_url(self, url):
        return os.path.join(self.basepath, url.replace('/', '@'))

    def file_init(self):
        pass

    def read_files(self):
        pass

    def filter_unknown(self, unknown):
        pass

    def update(self):
        for url in self.urls:
            self.logger.info("Packages: Updating %s" % url)
            fname = self.escape_url(url)
            try:
                data = fetch_url(url)
                file(fname, 'w').write(data)
            except ValueError:
                self.logger.error("Packages: Bad url string %s" % url)
                raise
            except HTTPError:
                err = sys.exc_info()[1]
                self.logger.error("Packages: Failed to fetch url %s. HTTP "
                                  "response code=%s" % (url, err.code))
                raise

    def applies(self, metadata):
        # check base groups
        if not self.magic_groups_match(metadata):
            return False

        # check Group/Client tags from sources.xml
        for condition in self.conditions:
            if not condition(metadata):
                return False

        return True

    def get_arches(self, metadata):
        return ['global'] + [a for a in self.arches if a in metadata.groups]

    def get_deps(self, metadata, pkgname):
        for arch in self.get_arches(metadata):
            if pkgname in self.deps[arch]:
                return self.deps[arch][pkgname]
        return []

    def get_provides(self, metadata, required):
        for arch in self.get_arches(metadata):
            if required in self.provides[arch]:
                return self.provides[arch][required]
        return []

    def is_package(self, metadata, _):
        return False

    def get_package(self, metadata, package):
        return package

    def get_group(self, metadata, group, ptype=None):
        return []

    def magic_groups_match(self, metadata):
        """ check to see if this source applies to the given host
        metadata by checking 'magic' (base) groups only, or if magic
        groups are off """
        # we always check that arch matches
        found_arch = False
        for arch in self.arches:
            if arch in metadata.groups:
                found_arch = True
                break
        if not found_arch:
            return False

        if self.config.getboolean("global", "magic_groups",
                                  default=True) == False:
            return True
        else:
            for group in self.basegroups:
                if group in metadata.groups:
                    return True
            return False
