import os
import re
import sys
import copy
import gzip
import glob
import base64
import logging
import tarfile
import lxml.etree

# Compatibility imports
from Bcfg2.Bcfg2Py3k import cPickle
from Bcfg2.Bcfg2Py3k import HTTPBasicAuthHandler
from Bcfg2.Bcfg2Py3k import HTTPPasswordMgrWithDefaultRealm
from Bcfg2.Bcfg2Py3k import HTTPError
from Bcfg2.Bcfg2Py3k import install_opener
from Bcfg2.Bcfg2Py3k import build_opener
from Bcfg2.Bcfg2Py3k import urlopen
from Bcfg2.Bcfg2Py3k import ConfigParser

# py3k compatibility
if sys.hexversion >= 0x03000000:
    from io import FileIO as BUILTIN_FILE_TYPE
else:
    BUILTIN_FILE_TYPE = file

try:
    import yum.misc
    has_yum = True
except ImportError:
    has_yum = False

try:
    import pulp.client.server
    import pulp.client.config
    import pulp.client.api.repository
    import pulp.client.api.consumer
    has_pulp = True
except ImportError:
    has_pulp = False

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

import Bcfg2.Logger
import Bcfg2.Server.Plugin

# build sources.list?
# caching for yum

class NoData(Exception):
    pass


class SomeData(Exception):
    pass

logger = logging.getLogger('Packages')


def source_from_xml(xsource, cachepath):
    """ create a *Source object from its XML representation in
    sources.xml """
    stype = xsource.get("type")
    if stype is None:
        logger.error("No type specified for source, skipping")
        return None

    try:
        cls = globals()["%sSource" % stype.upper()]
    except KeyError:
        logger.error("Unknown source type %s")
        return None
    
    return cls(cachepath, xsource)


def _fetch_url(url):
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


class Source(object):
    basegroups = []

    def __init__(self, basepath, xsource):
        self.basepath = basepath
        self.xsource = xsource

        try:
            self.version = xsource.find('Version').text
        except AttributeError:
            pass

        for key, tag in [('components', 'Component'), ('arches', 'Arch'),
                         ('blacklist', 'Blacklist'),
                         ('whitelist', 'Whitelist')]:
            self.__dict__[key] = [item.text for item in xsource.findall(tag)]

        self.gpgkeys = [el.text for el in xsource.findall("GPGKey")]

        self.recommended = xsource.get('recommended', 'false').lower() == 'true'
        self.id = xsource.get('id')
    
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

        self.cachefile = \
            os.path.join(self.basepath,
                         "cache-%s" %
                         md5(cPickle.dumps([self.version, self.components,
                                            self.url, self.rawurl,
                                            self.arches])).hexdigest())
        self.url_map = []

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
                logger.error("Cachefile %s load failed; "
                             "falling back to file read" % self.cachefile)
        if should_read:
            try:
                self.read_files()
            except:
                logger.error("Packages: File read failed; "
                             "falling back to file download")
                should_download = True

        if should_download or force_update:
            try:
                self.update()
                self.read_files()
            except:
                logger.error("Failed to update source", exc_info=1)

    def get_urls(self):
        return []
    urls = property(get_urls)

    def get_files(self):
        return [self.escape_url(url) for url in self.urls]
    files = property(get_files)

    def get_vpkgs(self, meta):
        agroups = ['global'] + [a for a in self.arches if a in meta.groups]
        vdict = dict()
        for agrp in agroups:
            for key, value in list(self.provides[agrp].items()):
                if key not in vdict:
                    vdict[key] = set(value)
                else:
                    vdict[key].update(value)
        return vdict

    def escape_url(self, url):
        return os.path.join(self.basepath, url.replace('/', '@'))

    def file_init(self):
        pass

    def read_files(self):
        pass

    def update(self):
        for url in self.urls:
            logger.info("Packages: Updating %s" % url)
            fname = self.escape_url(url)
            try:
                data = _fetch_url(url)
            except ValueError:
                logger.error("Packages: Bad url string %s" % url)
                continue
            except HTTPError:
                err = sys.exc_info()[1]
                logger.error("Packages: Failed to fetch url %s. code=%s" %
                             (url, err.code))
                continue
            BUILTIN_FILE_TYPE(fname, 'w').write(data)

    def applies(self, metadata):
        # check base groups
        if len([g for g in self.basegroups if g in metadata.groups]) == 0:
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
        raise NoData

    def get_provides(self, metadata, required):
        for arch in self.get_arches(metadata):
            if required in self.provides[arch]:
                return self.provides[arch][required]
        raise NoData

    def is_package(self, metadata, _):
        return False


class YUMSource(Source):
    xp = '{http://linux.duke.edu/metadata/common}'
    rp = '{http://linux.duke.edu/metadata/rpm}'
    rpo = '{http://linux.duke.edu/metadata/repo}'
    fl = '{http://linux.duke.edu/metadata/filelists}'
    basegroups = ['yum', 'redhat', 'centos', 'fedora']
    ptype = 'yum'

    def __init__(self, basepath, xsource):
        Source.__init__(self, basepath, xsource)
        if not self.rawurl:
            self.baseurl = self.url + "%(version)s%(component)s%(arch)s"
        else:
            self.baseurl = self.rawurl
        self.packages = dict()
        self.deps = dict([('global', dict())])
        self.provides = dict([('global', dict())])
        self.filemap = dict([(x, dict()) for x in ['global'] + self.arches])
        self.needed_paths = set()
        self.file_to_arch = dict()

    def save_state(self):
        cache = BUILTIN_FILE_TYPE(self.cachefile, 'wb')
        cPickle.dump((self.packages, self.deps, self.provides,
                      self.filemap, self.url_map), cache, 2)
        cache.close()

    def load_state(self):
        data = BUILTIN_FILE_TYPE(self.cachefile)
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
        rmdurl = '%srepodata/repomd.xml' % url
        try:
            repomd = _fetch_url(rmdurl)
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
        for elt in xdata.findall(self.rpo + 'data'):
            if elt.get('type') in ['filelists', 'primary']:
                floc = elt.find(self.rpo + 'location')
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
            logger.error("No packages in repo")
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
        for pkg in data.findall(self.fl + 'package'):
            for fentry in pkg.findall(self.fl + 'file'):
                if fentry.text in self.needed_paths:
                    if fentry.text in self.filemap[arch]:
                        self.filemap[arch][fentry.text].add(pkg.get('name'))
                    else:
                        self.filemap[arch][fentry.text] = set([pkg.get('name')])

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
            pkgname = pkg.find(self.xp + 'name').text
            self.packages[arch].add(pkgname)

            pdata = pkg.find(self.xp + 'format')
            pre = pdata.find(self.rp + 'requires')
            self.deps[arch][pkgname] = set()
            for entry in pre.getchildren():
                self.deps[arch][pkgname].add(entry.get('name'))
                if entry.get('name').startswith('/'):
                    self.needed_paths.add(entry.get('name'))
            pro = pdata.find(self.rp + 'provides')
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
        rv = Source.get_vpkgs(self, metadata)
        for arch, fmdata in list(self.filemap.items()):
            if arch not in metadata.groups and arch != 'global':
                continue
            for filename, pkgs in list(fmdata.items()):
                rv[filename] = pkgs
        return rv

    def filter_unknown(self, unknown):
        filtered = set([u for u in unknown if u.startswith('rpmlib')])
        unknown.difference_update(filtered)


class PulpSource(Source):
    basegroups = ['yum', 'redhat', 'centos', 'fedora']
    ptype = 'yum'
    
    def __init__(self, basepath, xsource):
        Source.__init__(self, basepath, xsource)
        if not has_pulp:
            logger.error("Cannot create pulp source: pulp libraries not found")
            raise Bcfg2.Server.Plugin.PluginInitError

        self._config = pulp.client.config.Config()        

        self._repoapi = pulp.client.api.repository.RepositoryAPI()
        self._repo = self._repoapi.repository(self.id)
        if self._repo is None:
            logger.error("Repo id %s not found")
        else:
            self.baseurl = "%s/%s" % (self._config.cds.baseurl,
                                      self._repo['relative_path'])

        self.gpgkeys = ["%s/%s" % (self._config.cds.keyurl, key)
                        for key in self._repoapi.listkeys(self.id)]

        self.url_map = [{'version': self.version, 'component': None,
                         'arch': self.arches[0], 'url': self.baseurl}]

    def save_state(self):
        cache = BUILTIN_FILE_TYPE(self.cachefile, 'wb')
        cPickle.dump((self.packages, self.deps, self.provides, self._config,
                      self.filemap, self.url_map, self._repoapi, self._repo),
                     cache, 2)
        cache.close()

    def load_state(self):
        cache = BUILTIN_FILE_TYPE(self.cachefile)
        (self.packages, self.deps, self.provides, self._config, self.filemap,
         self.url_map, self._repoapi, self._repo) = cPickle.load(cache)
        cache.close()

    def read_files(self):
        """ ignore the yum files; we can get this information directly
        from pulp """
        for pkg in self._repoapi.packages(self.id):
            try:
                self.packages[pkg['arch']].append(pkg['name'])
            except KeyError:
                self.packages[pkg['arch']] = [pkg['name']]
        self.save_state()


class APTSource(Source):
    basegroups = ['apt', 'debian', 'ubuntu', 'nexenta']
    ptype = 'deb'

    def __init__(self, basepath, xsource):
        Source.__init__(self, basepath, xsource)
        self.pkgnames = set()

        self.url_map = [{'rawurl': self.rawurl, 'url': self.url,
                         'version': self.version,
                         'components': self.components, 'arches': self.arches}]

    def save_state(self):
        cache = BUILTIN_FILE_TYPE(self.cachefile, 'wb')
        cPickle.dump((self.pkgnames, self.deps, self.provides),
                     cache, 2)
        cache.close()

    def load_state(self):
        data = BUILTIN_FILE_TYPE(self.cachefile)
        self.pkgnames, self.deps, self.provides = cPickle.load(data)

    def filter_unknown(self, unknown):
        filtered = set([u for u in unknown if u.startswith('choice')])
        unknown.difference_update(filtered)

    def get_urls(self):
        if not self.rawurl:
            rv = []
            for part in self.components:
                for arch in self.arches:
                    rv.append("%sdists/%s/%s/binary-%s/Packages.gz" %
                              (self.url, self.version, part, arch))
            return rv
        else:
            return ["%sPackages.gz" % self.rawurl]
    urls = property(get_urls)

    def read_files(self):
        bdeps = dict()
        bprov = dict()
        if self.recommended:
            depfnames = ['Depends', 'Pre-Depends', 'Recommends']
        else:
            depfnames = ['Depends', 'Pre-Depends']
        for fname in self.files:
            if not self.rawurl:
                barch = [x
                         for x in fname.split('@')
                         if x.startswith('binary-')][0][7:]
            else:
                # RawURL entries assume that they only have one <Arch></Arch>
                # element and that it is the architecture of the source.
                barch = self.arches[0]
            if barch not in bdeps:
                bdeps[barch] = dict()
                bprov[barch] = dict()
            try:
                reader = gzip.GzipFile(fname)
            except:
                print("Failed to read file %s" % fname)
                raise
            for line in reader.readlines():
                words = str(line.strip()).split(':', 1)
                if words[0] == 'Package':
                    pkgname = words[1].strip().rstrip()
                    self.pkgnames.add(pkgname)
                    bdeps[barch][pkgname] = []
                elif words[0] in depfnames:
                    vindex = 0
                    for dep in words[1].split(','):
                        if '|' in dep:
                            cdeps = [re.sub('\s+', '',
                                            re.sub('\(.*\)', '', cdep))
                                     for cdep in dep.split('|')]
                            dyn_dname = "choice-%s-%s-%s" % (pkgname,
                                                             barch,
                                                             vindex)
                            vindex += 1
                            bdeps[barch][pkgname].append(dyn_dname)
                            bprov[barch][dyn_dname] = set(cdeps)
                        else:
                            raw_dep = re.sub('\(.*\)', '', dep)
                            raw_dep = raw_dep.rstrip().strip()
                            bdeps[barch][pkgname].append(raw_dep)
                elif words[0] == 'Provides':
                    for pkg in words[1].split(','):
                        dname = pkg.rstrip().strip()
                        if dname not in bprov[barch]:
                            bprov[barch][dname] = set()
                        bprov[barch][dname].add(pkgname)

        self.deps['global'] = dict()
        self.provides['global'] = dict()
        for barch in bdeps:
            self.deps[barch] = dict()
            self.provides[barch] = dict()
        for pkgname in self.pkgnames:
            pset = set()
            for barch in bdeps:
                if pkgname not in bdeps[barch]:
                    bdeps[barch][pkgname] = []
                pset.add(tuple(bdeps[barch][pkgname]))
            if len(pset) == 1:
                self.deps['global'][pkgname] = pset.pop()
            else:
                for barch in bdeps:
                    self.deps[barch][pkgname] = bdeps[barch][pkgname]
        provided = set()
        for bprovided in list(bprov.values()):
            provided.update(set(bprovided))
        for prov in provided:
            prset = set()
            for barch in bprov:
                if prov not in bprov[barch]:
                    continue
                prset.add(tuple(bprov[barch].get(prov, ())))
            if len(prset) == 1:
                self.provides['global'][prov] = prset.pop()
            else:
                for barch in bprov:
                    self.provides[barch][prov] = bprov[barch].get(prov, ())
        self.save_state()

    def is_package(self, _, pkg):
        return (pkg in self.pkgnames and
                pkg not in self.blacklist and
                (len(self.whitelist) == 0 or pkg in self.whitelist))


class PACSource(Source):
    basegroups = ['arch', 'parabola']
    ptype = 'pacman'

    def __init__(self, basepath, xsource):
        Source.__init__(self, basepath, xsource)
        self.pkgnames = set()

        self.url_map = [{'rawurl': self.rawurl, 'url': self.url,
                         'version': self.version,
                         'components': self.components, 'arches': self.arches}]

    def save_state(self):
        cache = BUILTIN_FILE_TYPE(self.cachefile, 'wb')
        cPickle.dump((self.pkgnames, self.deps, self.provides),
                     cache, 2)
        cache.close()

    def load_state(self):
        data = BUILTIN_FILE_TYPE(self.cachefile)
        self.pkgnames, self.deps, self.provides = cPickle.load(data)

    def filter_unknown(self, unknown):
        filtered = set([u for u in unknown if u.startswith('choice')])
        unknown.difference_update(filtered)

    def get_urls(self):
        if not self.rawurl:
            rv = []
            for part in self.components:
                for arch in self.arches:
                    rv.append("%s%s/os/%s/%s.db.tar.gz" %
                              (self.url, part, arch, part))
            return rv
        else:
            raise Exception("PACSource : RAWUrl not supported (yet)")
    urls = property(get_urls)

    def read_files(self):
        bdeps = dict()
        bprov = dict()

        if self.recommended:
            depfnames = ['Depends', 'Pre-Depends', 'Recommends']
        else:
            depfnames = ['Depends', 'Pre-Depends']

        for fname in self.files:
            if not self.rawurl:
                barch = [x for x in fname.split('@') if x in self.arches][0]
            else:
                # RawURL entries assume that they only have one <Arch></Arch>
                # element and that it is the architecture of the source.
                barch = self.arches[0]
            
            if barch not in bdeps:
                bdeps[barch] = dict()
                bprov[barch] = dict()
            try:
                print("try to read : " + fname)
                tar = tarfile.open(fname, "r")
                reader = gzip.GzipFile(fname)
            except:
                print("Failed to read file %s" % fname)
                raise

            for tarinfo in tar:
                if tarinfo.isdir():
                    self.pkgnames.add(tarinfo.name.rsplit("-", 2)[0])
                    print("added : " + tarinfo.name.rsplit("-", 2)[0])
            tar.close()

        self.deps['global'] = dict()
        self.provides['global'] = dict()
        for barch in bdeps:
            self.deps[barch] = dict()
            self.provides[barch] = dict()
        for pkgname in self.pkgnames:
            pset = set()
            for barch in bdeps:
                if pkgname not in bdeps[barch]:
                    bdeps[barch][pkgname] = []
                pset.add(tuple(bdeps[barch][pkgname]))
            if len(pset) == 1:
                self.deps['global'][pkgname] = pset.pop()
            else:
                for barch in bdeps:
                    self.deps[barch][pkgname] = bdeps[barch][pkgname]
        provided = set()
        for bprovided in list(bprov.values()):
            provided.update(set(bprovided))
        for prov in provided:
            prset = set()
            for barch in bprov:
                if prov not in bprov[barch]:
                    continue
                prset.add(tuple(bprov[barch].get(prov, ())))
            if len(prset) == 1:
                self.provides['global'][prov] = prset.pop()
            else:
                for barch in bprov:
                    self.provides[barch][prov] = bprov[barch].get(prov, ())
        self.save_state()

    def is_package(self, _, pkg):
        return (pkg in self.pkgnames and
                pkg not in self.blacklist and
                (len(self.whitelist) == 0 or pkg in self.whitelist))


class PackagesSources(Bcfg2.Server.Plugin.SingleXMLFileBacked,
                      Bcfg2.Server.Plugin.StructFile):
    def __init__(self, filename, cachepath, fam, packages):
        Bcfg2.Server.Plugin.SingleXMLFileBacked.__init__(self, filename, fam)
        Bcfg2.Server.Plugin.StructFile.__init__(self, filename)
        self.cachepath = cachepath
        if not os.path.exists(self.cachepath):
            # create cache directory if needed
            os.makedirs(self.cachepath)
        self.extras = []
        self.fam = fam
        self.pkg_obj = packages

    def Index(self):
        try:
            self.xdata = lxml.etree.XML(self.data, base_url=self.name)
        except lxml.etree.XMLSyntaxError:
            err = sys.exc_info()[1]
            logger.error("Packages: Error processing sources: %s" % err)
            raise Bcfg2.Server.Plugin.PluginInitError

        included = [ent.get('href')
                    for ent in self.xdata.findall('./{http://www.w3.org/2001/XInclude}include')]
        if included:
            for name in included:
                if name not in self.extras:
                    self.add_monitor(name)
            try:
                self.xdata.getroottree().xinclude()
            except lxml.etree.XIncludeError:
                err = sys.exc_info()[1]
                logger.error("Packages: Error processing sources: %s" % err)

        if self.__identifier__ is not None:
            self.label = self.xdata.attrib[self.__identifier__]

        self.entries = []
        for xsource in self.xdata.findall('.//Source'):
            source = source_from_xml(xsource, self.cachepath)
            if source is not None:
                self.entries.append(source)
        
        self.pkg_obj.Reload()

    def add_monitor(self, fname):
        """Add a fam monitor for an included file"""
        self.fam.AddMonitor(os.path.join(os.path.dirname(self.name), fname),
                            self)
        self.extras.append(fname)


class PackagesConfig(Bcfg2.Server.Plugin.FileBacked,
                     ConfigParser.SafeConfigParser):
    def __init__(self, filename, fam):
        Bcfg2.Server.Plugin.FileBacked.__init__(self, filename)
        ConfigParser.SafeConfigParser.__init__(self)
        fam.AddMonitor(filename, self)

    def Index(self):
        """ Build local data structures """
        for section in self.sections():
            self.remove_section(section)
        self.read(self.name)


class Packages(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.StructureValidator,
               Bcfg2.Server.Plugin.Generator,
               Bcfg2.Server.Plugin.Connector):
    name = 'Packages'
    conflicts = ['Pkgmgr']
    experimental = True
    __rmi__ = Bcfg2.Server.Plugin.Plugin.__rmi__ + ['Refresh', 'Reload']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.StructureValidator.__init__(self)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.Probing.__init__(self)
        
        self.sentinels = set()
        self.virt_pkgs = dict()
        self.ptypes = dict()
        self.cachepath = os.path.join(self.data, 'cache')
        self.keypath = os.path.join(self.data, 'keys')
        if not os.path.exists(self.keypath):
            # create key directory if needed
            os.makedirs(self.keypath)

        # set up config files
        self.config = PackagesConfig(os.path.join(self.data, "packages.conf"),
                                     core.fam)
        self.sources = PackagesSources(os.path.join(self.data, "sources.xml"),
                                       self.cachepath, core.fam, self)

    @property
    def disableResolver(self):
        try:
            return self.config.get("global", "resolver").lower() == "disabled"
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return False

    @property
    def disableMetaData(self):
        try:
            return self.config.get("global", "metadata").lower() == "disabled"
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return False

    def create_apt_conf(self, entry, metadata):
        """ create apt config for the specified host """
        raise NotImplementedError

    def create_yum_conf(self, entry, metadata):
        """ create yum config for the specified host """
        yum_attrib = {'encoding': 'ascii',
                      'owner': 'root',
                      'group': 'root',
                      'type': 'file',
                      'perms': '0644'}

        stanzas = []
        reponame_re = re.compile(r'.*/(?:RPMS\.)?([^/]+)')
        for source in self.get_matching_sources(metadata):
            for url_map in source.url_map:
                if url_map['arch'] in metadata.groups:
                    # try to find a sensible name for the repo
                    name = None
                    if source.id:
                        reponame = source.id
                    else:
                        match = reponame_re.search(url_map['url'])
                        if url_map['component']:
                            name = url_map['component']
                        elif match:
                            name = match.group(1)
                        else:
                            # couldn't figure out the name from the
                            # source ID, URL or URL map (which
                            # probably means its a screwy URL), so we
                            # just generate a random one
                            name = base64.b64encode(os.urandom(16))[:-2]
                        reponame = "%s-%s" % (source.groups[0], name)

                    stanza = ["[%s]" % reponame,
                              "name=%s" % reponame,
                              "baseurl=%s" % url_map['url'],
                              "enabled=1"]
                    if len(source.gpgkeys):
                        stanza.append("gpgcheck=1")
                        stanza.append("gpgkey=%s" %
                                      " ".join(source.gpgkeys))
                    else:
                        stanza.append("gpgcheck=0")
                    stanzas.append("\n".join(stanza))

        entry.text = "%s\n" % "\n\n".join(stanzas)
        for (key, value) in list(yum_attrib.items()):
            entry.attrib.__setitem__(key, value)

    def get_relevant_groups(self, meta):
        mgrps = []
        for source in self.get_matching_sources(meta):
            mgrps.extend(list(set([g for g in meta.groups
                                   if (g in source.basegroups or
                                       g in source.groups or
                                       g in source.arches)])))
        mgrps.sort()
        return tuple(mgrps)

    def _setup_pulp(self):
        try:
            rouser = self.config.get("pulp", "rouser")
            ropass = self.config.get("pulp", "ropass")
        except ConfigParser.NoSectionError:
            logger.error("No [pulp] section found in Packages/packages.conf")
            raise Bcfg2.Server.Plugin.PluginInitError
        except ConfigParser.NoOptionError:
            err = sys.exc_info()[1]
            logger.error("Required option not found in "
                         "Packages/packages.conf: %s" % err)
            raise Bcfg2.Server.Plugin.PluginInitError            

        pulpconfig = pulp.client.config.Config()
        serveropts = pulpconfig.server
        
        self._server = pulp.client.server.PulpServer(serveropts['host'],
                                                     int(serveropts['port']),
                                                     serveropts['scheme'],
                                                     serveropts['path'])
        self._server.set_basic_auth_credentials(rouser, ropass)
        pulp.client.server.set_active_server(self._server)

    def build_vpkgs_entry(self, meta):
        # build single entry for all matching sources
        vpkgs = dict()
        for source in self.get_matching_sources(meta):
            s_vpkgs = source.get_vpkgs(meta)
            for name, prov_set in list(s_vpkgs.items()):
                if name not in vpkgs:
                    vpkgs[name] = set(prov_set)
                else:
                    vpkgs[name].update(prov_set)
        return vpkgs

    def get_matching_sources(self, meta):
        return [s for s in self.sources if s.applies(meta)]

    def get_ptype(self, metadata):
        """ return the package type relevant to this client """
        if metadata.hostname not in self.ptypes:
            for source in self.sources:
                for grp in metadata.groups:
                    if grp in source.basegroups:
                        self.ptypes[metadata.hostname] = source.ptype
                        break
        try:
            return self.ptypes[metadata.hostname]
        except KeyError:
            return None

    def HandleEntry(self, entry, metadata):
        if entry.tag == 'Package':
            entry.set('version', 'auto')
            entry.set('type', self.get_ptype(metadata))
        elif entry.tag == 'Path':
            if (self.config.has_option("global", "yum_config") and
                entry.get("name") == self.config.get("global", "yum_config")):
                self.create_yum_conf(entry, metadata)
            elif (self.config.has_option("global", "apt_config") and 
                  entry.get("name") == self.config.get("global", "apt_config")):
                self.create_apt_conf(entry, metadata)

    def HandlesEntry(self, entry, metadata):
        if entry.tag == 'Package':
            for grp in metadata.groups:
                if grp in self.sentinels:
                    return True
        elif entry.tag == 'Path':
            # managed entries for yum/apt configs
            if ((self.config.has_option("global", "yum_config") and
                 entry.get("name") == self.config.get("global",
                                                      "yum_config")) or
                (self.config.has_option("global", "apt_config") and 
                 entry.get("name") == self.config.get("global", "apt_config"))):
                return True
        return False

    def complete(self, meta, input_requirements, debug=False):
        '''Build the transitive closure of all package dependencies

        Arguments:
        meta - client metadata instance
        packages - set of package names
        debug - print out debug information for the decision making process
        returns => (set(packages), set(unsatisfied requirements), package type)
        '''
        sources = self.get_matching_sources(meta)
        # reverse list so that priorities correspond to file order
        sources.reverse()
        if len(sources) == 0:
            self.logger.error("Packages: No matching sources for client %s; "
                              "improper group memberships?" % meta.hostname)
            return set(), set(), 'failed'
        ptype = self.get_ptype(meta)
        if ptype is None:
            return set(), set(), 'failed'

        # setup vpkg cache
        pgrps = self.get_relevant_groups(meta)
        if pgrps not in self.virt_pkgs:
            self.virt_pkgs[pgrps] = self.build_vpkgs_entry(meta)
        vpkg_cache = self.virt_pkgs[pgrps]

        # unclassified is set of unsatisfied requirements (may be pkg for vpkg)
        unclassified = set(input_requirements)
        vpkgs = set()
        both = set()
        pkgs = set(input_requirements)

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
                for source in sources:
                    if source.is_package(meta, current):
                        is_pkg = True
                        break
                
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
                if debug:
                    self.logger.debug("Packages: handling package requirement "
                                      "%s" % current)
                deps = ()
                for source in sources:
                    if source.is_package(meta, current):
                        try:
                            deps = source.get_deps(meta, current)
                            break
                        except:
                            continue
                packages.add(current)
                newdeps = set(deps).difference(examined)
                if debug and newdeps:
                    self.logger.debug("Packages: Package %s added "
                                      "requirements %s" % (current, newdeps))
                unclassified.update(newdeps)

            satisfied_vpkgs = set()
            for current in vpkgs:
                # virtual dependencies, satisfied if one of N in the
                # config, or can be forced if only one provider
                if len(vpkg_cache[current]) == 1:
                    if debug:
                        self.logger.debug("Packages: requirement %s satisfied "
                                          "by %s" % (current,
                                                     vpkg_cache[current]))
                    unclassified.update(vpkg_cache[current].difference(examined))
                    satisfied_vpkgs.add(current)
                elif [item for item in vpkg_cache[current] if item in packages]:
                    if debug:
                        self.logger.debug("Packages: requirement %s satisfied "
                                          "by %s" %
                                          (current,
                                           [item for item in vpkg_cache[current]
                                            if item in packages]))
                    satisfied_vpkgs.add(current)
            vpkgs.difference_update(satisfied_vpkgs)

            satisfied_both = set()
            for current in both:
                # packages that are both have virtual providers as
                # well as a package with that name. allow use of virt
                # through explicit specification, then fall back to
                # forcing current on last pass
                if [item for item in vpkg_cache[current] if item in packages]:
                    if debug:
                        self.logger.debug("Packages: requirement %s satisfied "
                                          "by %s" %
                                          (current,
                                           [item for item in vpkg_cache[current]
                                            if item in packages]))
                    satisfied_both.add(current)
                elif current in input_requirements or final_pass:
                    pkgs.add(current)
                    satisfied_both.add(current)
            both.difference_update(satisfied_both)

            if len(unclassified) + len(pkgs) == 0:
                final_pass = True
            else:
                final_pass = False

            for source in sources:
                source.filter_unknown(unknown)

        return packages, unknown, ptype

    def validate_structures(self, metadata, structures):
        '''Ensure client configurations include all needed prerequisites

        Arguments:
        metadata - client metadata instance
        structures - a list of structure-stage entry combinations
        '''
        indep = lxml.etree.Element('Independent')
        self._build_packages(metadata, indep, structures)
        self._build_gpgkeys(metadata, indep)
        self._build_pulp_entries(metadata, indep)
        structures.append(indep)

    def _build_pulp_entries(self, metadata, independent):
        """ build list of Pulp actions that need to be included in the
        specification by validate_structures() """
        if not has_pulp:
            return

        # if there are no Pulp sources for this host, we don't need to
        # worry about registering it
        build_actions = False
        for source in self.get_matching_sources(metadata):
            if isinstance(source, PulpSource):
                build_actions = True
                break
            
        if not build_actions:
            self.logger.debug("No Pulp sources apply to %s, skipping Pulp "
                              "registration" % metadata.hostname)
            return

        consumerapi = pulp.client.api.consumer.ConsumerAPI()
        try:
            consumer = consumerapi.consumer(metadata.hostname)
        except pulp.client.server.ServerRequestError:
            try:
                reguser = self.config.get("pulp", "reguser")
                regpass = self.config.get("pulp", "regpass")           
                reg_cmd = ("pulp-client -u '%s' -p '%s' consumer create "
                           "--id='%s'" % (reguser, regpass, metadata.hostname))
                lxml.etree.SubElement(independent, "BoundAction",
                                      name="pulp-register", timing="pre",
                                      when="always", status="check",
                                      command=reg_cmd)
            except ConfigParser.NoOptionError:
                err = sys.exc_info()[1]
                self.logger.error("Required option not found in "
                                  "Packages/packages.conf: %s.  Pulp consumers "
                                  "will not be registered" % err)
            return

        for source in self.get_matching_sources(metadata):
            # each pulp source can only have one arch, so we don't
            # have to check the arch in url_map
            if source.id not in consumer['repoids']:
                bind_cmd = "pulp-client consumer bind --repoid=%s" % source.id
                lxml.etree.SubElement(independent, "BoundAction",
                                      name="pulp-bind-%s" % source.id,
                                      timing="pre", when="always",
                                      status="check", command=bind_cmd)

    def _build_packages(self, metadata, independent, structures):
        """ build list of packages that need to be included in the
        specification by validate_structures() """
        if self.disableResolver:
            # Config requests no resolver
            return

        initial = set([pkg.get('name')
                       for struct in structures
                         for pkg in struct.findall('Package') + \
                                    struct.findall('BoundPackage')])
        packages, unknown, ptype = self.complete(metadata, initial,
                                                 debug=self.debug_flag)
        if unknown:
            self.logger.info("Got unknown entries")
            self.logger.info(list(unknown))
        newpkgs = list(packages.difference(initial))
        newpkgs.sort()
        for pkg in newpkgs:
            lxml.etree.SubElement(independent, 'BoundPackage', name=pkg,
                                  type=ptype, version='auto', origin='Packages')

    def _build_gpgkeys(self, metadata, independent):
        """ build list of gpg keys to be added to the specification by
        validate_structures() """
        keypkg = lxml.etree.Element('BoundPackage', name="gpg-pubkey",
                                    type=self.get_ptype(metadata),
                                    origin='Packages')

        needkeys = set()
        for source in self.get_matching_sources(metadata):
            for key in source.gpgkeys:
                needkeys.add(key)

        for key in needkeys:
            # figure out the path of the key on the client
            try:
                keydir = self.config.get("global", "gpg_keypath")
            except ConfigParser.NoOptionError:
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
            independent.append(keypath)

            if has_yum:
                # add the key to the specification to ensure it gets
                # installed
                kinfo = yum.misc.getgpgkeyinfo(kdata)
                version = yum.misc.keyIdToRPMVer(kinfo['keyid'])
                release = yum.misc.keyIdToRPMVer(kinfo['timestamp'])

                lxml.etree.SubElement(keypkg, 'Instance', version=version,
                                      release=release, simplefile=remotekey)
            else:
                self.logger.info("Yum libraries not found; GPG keys will not "
                                 "be handled automatically")
        independent.append(keypkg)

    def Refresh(self):
        '''Packages.Refresh() => True|False\nReload configuration
        specification and download sources\n'''
        self._load_config(force_update=True)
        return True

    def Reload(self):
        '''Packages.Refresh() => True|False\nReload configuration
        specification and sources\n'''
        self._load_config()
        return True

    def _load_config(self, force_update=False):
        '''
        Load the configuration data and setup sources

        Keyword args:
            force_update    Force downloading repo data
        '''
        self._load_sources(force_update)
        self._load_gpg_keys(force_update)

    def _load_sources(self, force_update):
        """ Load sources from the config """
        self.virt_pkgs = dict()
        self.sentinels = set()

        cachefiles = []
        for source in self.sources:
            cachefiles.append(source.cachefile)
            if not self.disableMetaData:
                source.setup_data(force_update)
            self.sentinels.update(source.basegroups)
        
        for cfile in glob.glob(os.path.join(self.cachepath, "cache-*")):
            if cfile not in cachefiles:
                os.unlink(cfile)

    def _load_gpg_keys(self, force_update):
        """ Load gpg keys from the config """
        keyfiles = []
        for source in self.sources:
            for key in source.gpgkeys:
                localfile = os.path.join(self.keypath, os.path.basename(key))
                if localfile not in keyfiles:
                    keyfiles.append(localfile)
                if force_update or not os.path.exists(localfile):
                    logger.debug("Downloading and parsing %s" % key)
                    response = urlopen(key)
                    open(localfile, 'w').write(response.read())

        for kfile in glob.glob(os.path.join(self.keypath, "*")):
            if kfile not in keyfiles:
                os.unlink(kfile)

    def get_additional_data(self, meta):
        sdata = []
        [sdata.extend(copy.deepcopy(src.url_map))
         for src in self.get_matching_sources(meta)]
        return dict(sources=sdata)
