import cPickle
import copy
import gzip
import logging
import lxml.etree
import os
import re
import urllib2

import Bcfg2.Logger
import Bcfg2.Server.Plugin

# build sources.list?
# caching for yum

class NoData(Exception):
    pass

logger = logging.getLogger('Packages')

def source_from_xml(xsource):
    ret = dict([('rawurl', False), ('url', False)])
    for key, tag in [('groups', 'Group'), ('components', 'Component'),
                     ('arches', 'Arch')]:
        ret[key] = [item.text for item in xsource.findall(tag)]
    # version and component need to both contain data for sources to work
    try:
        ret['version'] = xsource.find('Version').text
    except:
        ret['version'] = 'placeholder'
    if ret['components'] == []:
        ret['components'] = ['placeholder']
    if xsource.find('RawURL') is not None:
        ret['rawurl'] = xsource.find('RawURL').text
        if not ret['rawurl'].endswith('/'):
            ret['rawurl'] += '/'
    else:
        ret['url'] = xsource.find('URL').text
        if not ret['url'].endswith('/'):
            ret['url'] += '/'
    return ret

class Source(object):
    basegroups = []
    def __init__(self, basepath, url, version, arches, components, groups, rawurl):
        self.basepath = basepath
        self.version = version
        self.components = components
        self.url = url
        self.rawurl = rawurl
        self.groups = groups
        self.arches = arches
        self.deps = dict()
        self.provides = dict()
        self.cachefile = None

    def load_state(self):
        pass

    def setup_data(self):
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

        if should_download:
            self.update()
            self.read_files()

    def get_urls(self):
        return []
    urls = property(get_urls)

    def get_files(self):
        return [self.escape_url(url) for url in self.urls]
    files = property(get_files)

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
                data = urllib2.urlopen(url).read()
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

    def complete(self, metadata, packages, unresolved, debug=False):
        '''Construct the transitive closure of package dependencies for client

        Arguments:
        metadata - client metadata instance
        packages - set of package names
        unresolved - set of unresolved dependency package names
        debug - boolean debug mode
        '''
        # perhaps cache arch?
        #arch = [a for a in self.arches if a in metadata.groups][0]
        # return newpkg, unknown
        newpkg = set(packages)
        unknown = set()
        work = set(unresolved)
        seen = set()
        while work:
            item = work.pop()
            seen.add(item)
            if debug:
                logger.debug("Handling item %s" % item)
            item_is_pkg = self.is_package(metadata, item)
            try:
                pset = self.get_provides(metadata, item)
                item_is_virt = True
            except NoData:
                item_is_virt = False

            #print "%s:%s:%s" % (item, item_is_pkg, item_is_virt)
            if (not item_is_pkg) and (not item_is_virt):
                unknown.add(item)
                continue
            if item_is_pkg and not item_is_virt:
                newpkg.add(item)
                try:
                    newdeps = set(self.get_deps(metadata, item))
                    if debug and newdeps:
                        logger.debug("Package %s: adding new deps %s" \
                                     %(item, str(newdeps)))
                    work.update(newdeps.difference(newpkg))
                except NoData:
                    continue
            elif item_is_virt:
                if item_is_pkg:
                    pset.add(item)
                if debug:
                    logger.debug("Package(s) %s provide(s) %s" \
                                 % (list(pset), item))

                if len(pset) == 1:
                    provider = list(pset)[0]
                    if debug:
                        logger.debug("Using package %s for requirement %s" \
                                     % (provider, item))
                    newpkg.add(provider)
                    # add deps for provider
                    try:
                        newdeps = set(self.get_deps(metadata, provider))
                        work.update(newdeps.difference(newpkg))
                    except NoData:
                        pass
                else:
                    if True in [p in newpkg for p in pset]:
                        # dep satisfied
                        try:
                            newdeps = set(self.get_deps(metadata, item))
                            if debug and newdeps:
                                logger.debug("Package %s: adding new deps %s" \
                                             %(item, str(newdeps)))
                            work.update(newdeps.difference(newpkg))
                        except NoData:
                            pass
                    elif item_is_pkg:
                        # add this pkg as a default action
                        if debug:
                            logger.debug("Adding Package %s" % item)
                        newpkg.add(item)
                        try:
                            newdeps = set(self.get_deps(metadata, item))
                            if debug and newdeps:
                                logger.debug("Package %s: adding new deps %s" \
                                             %(item, str(newdeps)))
                            work.update(newdeps.difference(newpkg))
                        except NoData:
                            pass
                    else:
                        # dep unsatisfied
                        # FIXME: hacky; multiple provides still not forced
                        unknown.add(item)
            else:
                unknown.add(item)
            work.difference_update(seen)
        return (newpkg, unknown)

class YUMSource(Source):
    xp = '{http://linux.duke.edu/metadata/common}'
    rp = '{http://linux.duke.edu/metadata/rpm}'
    rpo = '{http://linux.duke.edu/metadata/repo}'
    fl = '{http://linux.duke.edu/metadata/filelists}'
    basegroups = ['redhat', 'centos']
    ptype = 'yum'

    def __init__(self, basepath, url, version, arches, components, groups, rawurl):
        Source.__init__(self, basepath, url, version, arches, components,
                        groups, rawurl)
        if not self.rawurl:
            self.baseurl = self.url + '%(version)s/%(component)s/%(arch)s/'
        else:
            self.baseurl = self.rawurl
        self.cachefile = self.escape_url(self.baseurl) + '.data'
        self.packages = dict()
        self.deps = dict([('global', dict())])
        self.provides = dict([('global', dict())])
        self.filemap = dict([(x, dict()) for x in ['global'] + self.arches])
        self.needed_paths = set()
        self.file_to_arch = dict()

    def save_state(self):
        cache = file(self.cachefile, 'wb')
        cPickle.dump((self.packages, self.deps, self.provides,
                      self.filemap), cache, 2)
        cache.close()

    def load_state(self):
        data = file(self.cachefile)
        (self.packages, self.deps, self.provides, \
         self.filemap) = cPickle.load(data)

    def get_urls(self):
        surls = list()
        for arch in self.arches:
            usettings = [{'version': self.version, 'component':comp,
                          'arch':arch} for comp in self.components]
            surls.append((arch, [self.baseurl % setting for setting in usettings]))
        urls = []
        for (sarch, surl_list) in surls:
            for surl in surl_list:
                if not surl.endswith('/'):
                    surl += '/'
                rmdurl = surl + 'repodata/repomd.xml'
                try:
                    repomd = urllib2.urlopen(rmdurl).read()
                    xdata = lxml.etree.XML(repomd)
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
        return item in self.packages['global'] or item in self.packages[arch[0]]

    def get_provides(self, metadata, required):
        ret = set()
        arches = [a for a in self.arches if a in metadata.groups]
        if not arches:
            raise NoData
        if required in self.provides['global']:
            ret.update(Source.get_provides(self, metadata, required))
        elif required in self.provides[arches[0]]:
            ret.update(Source.get_provides(self, metadata, required))
        else:
            for arch in ['global'] + arches:
                if required in self.filemap[arch]:
                    ret.update(self.filemap[arch][required])
        if ret:
            return ret
        else:
            raise NoData

    def complete(self, metadata, packages, unknown, debug):
        p1, u1 = Source.complete(self, metadata, packages, unknown, debug)
        return (p1, set([u for u in u1 if not u.startswith('rpmlib')]))

class APTSource(Source):
    basegroups = ['debian', 'ubuntu', 'nexenta']
    ptype = 'deb'

    def __init__(self, basepath, url, version, arches, components, groups, rawurl):
        Source.__init__(self, basepath, url, version, arches, components, groups, rawurl)
        self.cachefile = self.escape_url(self.url) + '.data'
        self.pkgnames = set()

    def save_state(self):
        cache = file(self.cachefile, 'wb')
        cPickle.dump((self.pkgnames, self.deps, self.provides),
                     cache, 2)
        cache.close()

    def load_state(self):
        data = file(self.cachefile)
        self.pkgnames, self.deps, self.provides = cPickle.load(data)

    def get_urls(self):
        return ["%s/dists/%s/%s/binary-%s/Packages.gz" % \
                (self.url, self.version, part, arch) for part in self.components \
                for arch in self.arches]
    urls = property(get_urls)

    def get_aptsrc(self):
        return ["deb %s %s %s" % (self.url, self.version,
                                  " ".join(self.components)),
                "deb-src %s %s %s" % (self.url, self.version,
                                      " ".join(self.components))]

    def read_files(self):
        bdeps = dict()
        bprov = dict()
        for fname in self.files:
            barch = [x for x in fname.split('@') if x.startswith('binary-')][0][7:]
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
                elif words[0] == 'Depends':
                    bdeps[barch][pkgname] = []
                    vindex = 0
                    for dep in words[1].split(','):
                        raw_dep = re.sub('\(.*\)', '', dep)
                        if '|' in raw_dep:
                            dyn_dname = "choice-%s-%s-%s" % (pkgname, barch, vindex)
                            vindex += 1
                            bdeps[barch][pkgname].append(dyn_dname)
                            dyn_list = [x.strip() for x in raw_dep.split('|')]
                            bprov[barch][dyn_dname] = set(dyn_list)
                        else:
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
        return pkg in self.pkgnames

    def get_provides(self, metadata, pkgname):
        arches = [ar for ar in self.provides if ar in metadata.groups]
        for arch in ['global'] + arches:
            if pkgname in self.provides[arch]:
                return set(self.provides[arch][pkgname])
        raise NoData

class Packages(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.StructureValidator,
               Bcfg2.Server.Plugin.Generator):
    name = 'Packages'
    experimental = True
    __rmi__ = ['Refresh']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.StructureValidator.__init__(self)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        self.cachepath = self.data + '/cache'

        if not os.path.exists(self.cachepath):
            # create cache directory if needed
            os.makedirs(self.cachepath)
        try:
            xdata = lxml.etree.parse(self.data + '/config.xml').getroot()
        except IOError:
            self.logger.error("Failed to read Packages configuration. Have"
                              " you created your config.xml file?")
            raise Bcfg2.Server.Plugin.PluginInitError
        self.sentinels = set()
        self.sources = []
        for s in xdata.findall('APTSource'):
            self.sources.append(APTSource(self.cachepath, **source_from_xml(s)))
        for s in xdata.findall('YUMSource'):
            self.sources.append(YUMSource(self.cachepath, **source_from_xml(s)))
        for source in self.sources:
            source.setup_data()
            self.sentinels.update(source.basegroups)

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

    def complete(self, meta, packages, debug=False):
        '''Build the transitive closure of all package dependencies

        Arguments:
        meta - client metadata instance
        packages - set of package names
        debug - print out debug information for the decision making process
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
        pkgs = set(packages)
        unknown = set(packages)
        oldp = set()
        oldu = set()
        while unknown and (pkgs != oldp or unknown != oldu):
            # loop through sources until no progress is made
            oldp = pkgs
            oldu = unknown
            for source in sources:
                try:
                    pkgs, unknown = source.complete(meta, pkgs, unknown, debug)
                except:
                    self.logger.error("Packages: complete call failed unexpectedly:", exc_info=1)
        return pkgs, unknown, ptype.pop()

    def validate_structures(self, meta, structures):
        '''Ensure client configurations include all needed prerequisites

        Arguments:
        meta - client metadata instance
        structures - a list of structure-stage entry combinations
        '''
        initial = set([pkg.get('name') for struct in structures \
                       for pkg in struct.findall('Package')])
        news = lxml.etree.Element('Independent')
        packages, unknown, ptype = self.complete(meta, initial)
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
                try:
                    deps = source.get_deps(meta, pkgname)
                except:
                    continue
                for rpkg in deps:
                    if rpkg in pkgnames:
                        redundant.add(rpkg)
        return pkgnames.difference(redundant), redundant

    def Refresh(self):
        '''Packages.Refresh() => True|False\nReload configuration specification and sources\n'''
        try:
            xdata = lxml.etree.parse(self.data + '/config.xml').getroot()
        except IOError:
            self.logger.error("Failed to read Packages configuration. Have" +
                              " you created your config.xml file?")
            raise Bcfg2.Server.Plugin.PluginInitError
        self.sentinels = set()
        self.sources = []
        for s in xdata.findall('APTSource'):
            self.sources.append(APTSource(self.cachepath, **source_from_xml(s)))
        for s in xdata.findall('YUMSource'):
            self.sources.append(YUMSource(self.cachepath, **source_from_xml(s)))
        for source in self.sources:
            source.setup_data()
            self.sentinels.update(source.basegroups)
        for source in self.sources:
            try:
                source.update()
            except:
                self.logger.error("Failed to update source", exc_info=1)
                continue
            source.read_files()
        return True

if __name__ == '__main__':
    Bcfg2.Logger.setup_logging('Packages', to_console=True)
    aa = Packages(None, '/home/desai/tmp/bcfg2')
