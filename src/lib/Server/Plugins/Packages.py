import cPickle
import copy
import gzip
import glob
import logging
import lxml.etree
import os
import re
import sys
import urllib2

# FIXME: Remove when server python dep is 2.5 or greater
if sys.version_info >= (2, 5):
    from hashlib import md5
else:
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

def source_from_xml(xsource):
    ret = dict([('rawurl', False), ('url', False)])
    for key, tag in [('groups', 'Group'), ('components', 'Component'),
                     ('arches', 'Arch'), ('blacklist', 'Blacklist'),
                     ('whitelist', 'Whitelist')]:
        ret[key] = [item.text for item in xsource.findall(tag)]
    # version and component need to both contain data for sources to work
    try:
        ret['version'] = xsource.find('Version').text
    except:
        ret['version'] = 'placeholder'
    if ret['components'] == []:
        ret['components'] = ['placeholder']
    try:
        if xsource.find('Recommended').text in ['True', 'true']:
            ret['recommended'] = True
        else:
            ret['recommended'] = False
    except:
        ret['recommended'] = False
    if xsource.find('RawURL') is not None:
        ret['rawurl'] = xsource.find('RawURL').text
        if not ret['rawurl'].endswith('/'):
            ret['rawurl'] += '/'
    else:
        ret['url'] = xsource.find('URL').text
        if not ret['url'].endswith('/'):
            ret['url'] += '/'
    return ret

def _fetch_url(url):
    if '@' in url:
        mobj = re.match('(\w+://)([^:]+):([^@]+)@(.*)$', url)
        if not mobj:
            raise ValueError
        user = mobj.group(2)
        passwd = mobj.group(3)
        url = mobj.group(1) + mobj.group(4)
        auth = urllib2.HTTPBasicAuthHandler(urllib2.HTTPPasswordMgrWithDefaultRealm())
        auth.add_password(None, url, user, passwd)
        urllib2.install_opener(urllib2.build_opener(auth))
    return urllib2.urlopen(url).read()

class Source(object):
    basegroups = []

    def __init__(self, basepath, url, version, arches, components, groups, rawurl,
                 blacklist, whitelist, recommended):
        self.basepath = basepath
        self.version = version
        self.components = components
        self.url = url
        self.rawurl = rawurl
        self.groups = groups
        self.arches = arches
        self.deps = dict()
        self.provides = dict()
        self.blacklist = set(blacklist)
        self.whitelist = set(whitelist)
        self.cachefile = '%s/cache-%s' % (self.basepath, md5(cPickle.dumps( \
                [self.version, self.components, self.url, \
                self.rawurl, self.groups, self.arches])).hexdigest())
        self.recommended = recommended
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
                logger.error("Cachefile %s load failed; falling back to file read"\
                             % (self.cachefile))
        if should_read:
            try:
                self.read_files()
            except:
                logger.error("Packages: File read failed; falling back to file download")
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
            for key, value in self.provides[agrp].iteritems():
                if key not in vdict:
                    vdict[key] = set(value)
                else:
                    vdict[key].update(value)
        return vdict

    def escape_url(self, url):
        return "%s/%s" % (self.basepath, url.replace('/', '@'))

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
            except urllib2.HTTPError, h:
                logger.error("Packages: Failed to fetch url %s. code=%s" \
                             % (url, h.code))
                continue
            file(fname, 'w').write(data)

    def applies(self, metadata):
        return len([g for g in self.basegroups if g in metadata.groups]) != 0 and \
               len([g for g in metadata.groups if g in self.groups]) \
               == len(self.groups)

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

    def get_url_info(self):
        return {'groups': copy.copy(self.groups), \
            'urls': [copy.deepcopy(url) for url in self.url_map]}

class YUMSource(Source):
    xp = '{http://linux.duke.edu/metadata/common}'
    rp = '{http://linux.duke.edu/metadata/rpm}'
    rpo = '{http://linux.duke.edu/metadata/repo}'
    fl = '{http://linux.duke.edu/metadata/filelists}'
    basegroups = ['yum', 'redhat', 'centos', 'fedora']
    ptype = 'yum'

    def __init__(self, basepath, url, version, arches, components, groups,
                 rawurl, blacklist, whitelist, recommended):
        Source.__init__(self, basepath, url, version, arches, components,
                        groups, rawurl, blacklist, whitelist, recommended)
        if not self.rawurl:
            self.baseurl = self.url + '%(version)s/%(component)s/%(arch)s/'
        else:
            self.baseurl = self.rawurl
        self.packages = dict()
        self.deps = dict([('global', dict())])
        self.provides = dict([('global', dict())])
        self.filemap = dict([(x, dict()) for x in ['global'] + self.arches])
        self.needed_paths = set()
        self.file_to_arch = dict()

    def save_state(self):
        cache = file(self.cachefile, 'wb')
        cPickle.dump((self.packages, self.deps, self.provides,
                      self.filemap, self.url_map), cache, 2)
        cache.close()

    def load_state(self):
        data = file(self.cachefile)
        (self.packages, self.deps, self.provides, \
         self.filemap, self.url_map) = cPickle.load(data)

    def get_urls(self):
        surls = list()
        self.url_map = []
        for arch in self.arches:
            usettings = [{'version': self.version, 'component':comp,
                          'arch':arch} for comp in self.components]
            for setting in usettings:
                setting['groups'] = self.groups
                setting['url'] = self.baseurl % setting
                self.url_map.append(copy.deepcopy(setting))
            surls.append((arch, [setting['url'] for setting in usettings]))
        urls = []
        for (sarch, surl_list) in surls:
            for surl in surl_list:
                if not surl.endswith('/'):
                    surl += '/'
                rmdurl = surl + 'repodata/repomd.xml'
                try:
                    repomd = _fetch_url(rmdurl)
                    xdata = lxml.etree.XML(repomd)
                except ValueError:
                    logger.error("Packages: Bad url string %s" % rmdurl)
                    continue
                except urllib2.HTTPError, h:
                    logger.error("Packages: Failed to fetch url %s. code=%s" \
                             % (rmdurl, h.code))
                    continue
                except:
                    logger.error("Failed to process url %s" % rmdurl)
                    continue
                for elt in xdata.findall(self.rpo + 'data'):
                    if elt.get('type') not in ['filelists', 'primary']:
                        continue
                    floc = elt.find(self.rpo + 'location')
                    fullurl = surl + floc.get('href')
                    urls.append(fullurl)
                    self.file_to_arch[self.escape_url(fullurl)] = sarch
        return urls
    urls = property(get_urls)

    def read_files(self):
        for fname in [f for f in self.files if f.endswith('primary.xml.gz')]:
            farch = self.file_to_arch[fname]
            fdata = lxml.etree.parse(fname).getroot()
            self.parse_primary(fdata, farch)
        for fname in [f for f in self.files if f.endswith('filelists.xml.gz')]:
            farch = self.file_to_arch[fname]
            fdata = lxml.etree.parse(fname).getroot()
            self.parse_filelist(fdata, farch)
        # merge data
        sdata = self.packages.values()
        self.packages['global'] = copy.deepcopy(sdata.pop())
        while sdata:
            self.packages['global'].intersection(sdata.pop())

        for key in self.packages:
            if key == 'global':
                continue
            self.packages[key] = self.packages['global'].difference(self.packages[key])
        self.save_state()

    def parse_filelist(self, data, arch):
        if arch not in self.filemap:
            self.filemap[arch] = dict()
        for pkg in data.findall(self.fl + 'package'):
            for fentry in [fe for fe in pkg.findall(self.fl + 'file') \
                           if fe.text in self.needed_paths]:
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
        return (item in self.packages['global'] or item in self.packages[arch[0]]) and \
               item not in self.blacklist and \
               ((len(self.whitelist) == 0) or item in self.whitelist)

    def get_vpkgs(self, metadata):
        rv = Source.get_vpkgs(self, metadata)
        for arch, fmdata in self.filemap.iteritems():
            if arch not in metadata.groups and arch != 'global':
                continue
            for filename, pkgs in fmdata.iteritems():
                rv[filename] = pkgs
        return rv

    def filter_unknown(self, unknown):
        filtered = set([u for u in unknown if u.startswith('rpmlib')])
        unknown.difference_update(filtered)

class APTSource(Source):
    basegroups = ['apt', 'debian', 'ubuntu', 'nexenta']
    ptype = 'deb'

    def __init__(self, basepath, url, version, arches, components, groups,
                 rawurl, blacklist, whitelist, recommended):
        Source.__init__(self, basepath, url, version, arches, components, groups,
                        rawurl, blacklist, whitelist, recommended)
        self.pkgnames = set()

        self.url_map = [{'rawurl': self.rawurl, 'url': self.url, 'version': self.version, \
            'components': self.components, 'arches': self.arches, 'groups': self.groups}]

    def save_state(self):
        cache = file(self.cachefile, 'wb')
        cPickle.dump((self.pkgnames, self.deps, self.provides),
                     cache, 2)
        cache.close()

    def load_state(self):
        data = file(self.cachefile)
        self.pkgnames, self.deps, self.provides = cPickle.load(data)

    def filter_unknown(self, unknown):
        filtered = set([u for u in unknown if u.startswith('choice')])
        unknown.difference_update(filtered)

    def get_urls(self):
        if not self.rawurl:
            return ["%sdists/%s/%s/binary-%s/Packages.gz" % \
                    (self.url, self.version, part, arch) for part in self.components \
                    for arch in self.arches]
        else:
            return ["%sPackages.gz" % (self.rawurl)]
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
                barch = [x for x in fname.split('@') if x.startswith('binary-')][0][7:]
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
                words = line.strip().split(':', 1)
                if words[0] == 'Package':
                    pkgname = words[1].strip().rstrip()
                    self.pkgnames.add(pkgname)
                    bdeps[barch][pkgname] = []
                elif words[0] in depfnames:
                    vindex = 0
                    for dep in words[1].split(','):
                        if '|' in dep:
                            cdeps = [re.sub('\s+', '', re.sub('\(.*\)', '', cdep)) for cdep in dep.split('|')]
                            dyn_dname = "choice-%s-%s-%s" % (pkgname, barch, vindex)
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
        for bprovided in bprov.values():
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
        return pkg in self.pkgnames and \
               pkg not in self.blacklist and \
               (len(self.whitelist) == 0 or pkg in self.whitelist)

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
        self.cachepath = self.data + '/cache'
        self.sentinels = set()
        self.sources = []
        self.disableResolver = False
        self.disableMetaData = False
        self.virt_pkgs = dict()

        if not os.path.exists(self.cachepath):
            # create cache directory if needed
            os.makedirs(self.cachepath)
        self._load_config()

    def get_relevant_groups(self, meta):
        mgrps = list(set([g for g in meta.groups for s in self.get_matching_sources(meta) \
                          if g in s.basegroups or g in s.groups or g in s.arches]))
        mgrps.sort()
        return tuple(mgrps)

    def build_vpkgs_entry(self, meta):
        # build single entry for all matching sources
        mgrps = self.get_relevant_groups(meta)
        vpkgs = dict()
        for source in self.get_matching_sources(meta):
            s_vpkgs = source.get_vpkgs(meta)
            for name, prov_set in s_vpkgs.iteritems():
                if name not in vpkgs:
                    vpkgs[name] = set(prov_set)
                else:
                    vpkgs[name].update(prov_set)
        return vpkgs

    def get_matching_sources(self, meta):
        return [s for s in self.sources if s.applies(meta)]

    def HandlesEntry(self, entry, metadata):
        if [x for x in metadata.groups if x in self.sentinels] \
               and entry.tag == 'Package':
            return True
        return False

    def HandleEntry(self, entry, metadata):
        entry.set('version', 'auto')
        for source in self.sources:
            if [x for x in metadata.groups if x in source.basegroups]:
                entry.set('type', source.ptype)

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
            self.logger.error("Packages: No matching sources for client %s; improper group memberships?" % (meta.hostname))
            return set(), set(), 'failed'
        ptype = set([s.ptype for s in sources])
        if len(ptype) < 1:
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
            #print len(unclassified), len(pkgs), len(both), len(vpkgs), final_pass
            if really_done: 
                break
            if len(unclassified) + len(pkgs) + len(both) == 0:
                # one more pass then exit
                really_done = True

            while unclassified:
                current = unclassified.pop()
                examined.add(current)
                is_pkg = True in [source.is_package(meta, current) for source in sources]
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
                # direct packages; current can be added, and all deps should be resolved
                current = pkgs.pop()
                if debug:
                    self.logger.debug("Packages: handling package requirement %s" % (current))
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
                    self.logger.debug("Packages: Package %s added requirements %s" % (current, newdeps))
                unclassified.update(newdeps)

            satisfied_vpkgs = set()
            for current in vpkgs:
                # virtual dependencies, satisfied if one of N in the config, or can be forced if only one provider
                if len(vpkg_cache[current]) == 1:
                    if debug:
                        self.logger.debug("Packages: requirement %s satisfied by %s" % (current, vpkg_cache[current]))
                    unclassified.update(vpkg_cache[current].difference(examined))
                    satisfied_vpkgs.add(current)
                elif [item for item in vpkg_cache[current] if item in packages]:
                    if debug:
                        self.logger.debug("Packages: requirement %s satisfied by %s" % (current, [item for item in vpkg_cache[current] if item in packages]))
                    satisfied_vpkgs.add(current)
            vpkgs.difference_update(satisfied_vpkgs)

            satisfied_both = set()
            for current in both:
                # packages that are both have virtual providers as well as a package with that name
                # allow use of virt through explicit specification, then fall back to forcing current on last pass
                if [item for item in vpkg_cache[current] if item in packages]:
                    if debug:
                        self.logger.debug("Packages: requirement %s satisfied by %s" % (current, [item for item in vpkg_cache[current] if item in packages]))
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

        return packages, unknown, ptype.pop()

    def validate_structures(self, meta, structures):
        '''Ensure client configurations include all needed prerequisites

        Arguments:
        meta - client metadata instance
        structures - a list of structure-stage entry combinations
        '''
        if self.disableResolver: return # Config requests no resolver

        initial = set([pkg.get('name') for struct in structures \
                       for pkg in struct.findall('Package') +
                       struct.findall('BoundPackage')])
        news = lxml.etree.Element('Independent')
        packages, unknown, ptype = self.complete(meta, initial,
                                                 debug=self.debug_flag)
        if unknown:
            self.logger.info("Got unknown entries")
            self.logger.info(list(unknown))
        newpkgs = list(packages.difference(initial))
        newpkgs.sort()
        for pkg in newpkgs:
            lxml.etree.SubElement(news, 'BoundPackage', name=pkg,
                                  type=ptype, version='auto', origin='Packages')
        structures.append(news)

    def make_non_redundant(self, meta, plname=None, plist=None):
        '''build a non-redundant version of a list of packages

        Arguments:
        meta - client metadata instance
        plname - name of file containing a list of packages
        '''
        if plname is not None:
            pkgnames = set([x.strip() for x in open(plname).readlines()])
        elif plist is not None:
            pkgnames = set(plist)
        redundant = set()
        sources = self.get_matching_sources(meta)
        for source in sources:
            for pkgname in pkgnames:
                if source.is_pkg(meta, current):
                    try:
                        deps = source.get_deps(meta, pkgname)
                    except:
                        continue
                    for rpkg in deps:
                        if rpkg in pkgnames:
                            redundant.add(rpkg)
        return pkgnames.difference(redundant), redundant

    def Refresh(self):
        '''Packages.Refresh() => True|False\nReload configuration specification and download sources\n'''
        self._load_config(force_update=True)
        return True

    def Reload(self):
        '''Packages.Refresh() => True|False\nReload configuration specification and sources\n'''
        self._load_config()
        return True

    def _load_config(self, force_update=False):
        '''
        Load the configuration data and setup sources

        Keyword args:
            force_update    Force downloading repo data
        '''
        self.virt_pkgs = dict()
        try:
            xdata = lxml.etree.parse(self.data + '/config.xml')
            xdata.xinclude()
            xdata = xdata.getroot()
        except (lxml.etree.XIncludeError, \
                lxml.etree.XMLSyntaxError), xmlerr:
            self.logger.error("Package: Error processing xml: %s" % xmlerr)
            raise Bcfg2.Server.Plugin.PluginInitError
        except IOError:
            self.logger.error("Failed to read Packages configuration. Have" +
                              " you created your config.xml file?")
            raise Bcfg2.Server.Plugin.PluginInitError

        # Load Packages config
        config = xdata.xpath('//Sources/Config')
        if config:
            if config[0].get("resolver", "enabled").lower() == "disabled":
                self.logger.info("Packages: Resolver disabled")
                self.disableResolver = True
            if config[0].get("metadata", "enabled").lower() == "disabled":
                self.logger.info("Packages: Metadata disabled")
                self.disableResolver = True
                self.disableMetaData = True

        self.sentinels = set()
        self.sources = []
        for s in xdata.findall('.//APTSource'):
            self.sources.append(APTSource(self.cachepath, **source_from_xml(s)))
        for s in xdata.findall('.//YUMSource'):
            self.sources.append(YUMSource(self.cachepath, **source_from_xml(s)))
        cachefiles = []
        for source in self.sources:
            cachefiles.append(source.cachefile)
            if not self.disableMetaData: source.setup_data(force_update)
            self.sentinels.update(source.basegroups)
        for cfile in glob.glob("%s/cache-*" % self.cachepath):
            if cfile not in cachefiles:
                os.unlink(cfile)

    def get_additional_data(self, meta):
        sdata = []
        [sdata.extend(copy.deepcopy(src.url_map)) for src in self.get_matching_sources(meta)]
        return dict(sources=sdata)
