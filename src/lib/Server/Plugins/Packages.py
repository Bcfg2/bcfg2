import copy, gzip, lxml.etree, re, urllib2, logging
import os, cPickle
import Bcfg2.Server.Plugin, Bcfg2.Logger

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
    ret['version'] = xsource.find('Version').text
    if xsource.find('RawURL') is not None:
        ret['rawurl'] = xsource.find('RawURL').text
    else:
        ret['url'] = xsource.find('URL').text
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
            print "updating", url
            fname = self.escape_url(url)
            data = urllib2.urlopen(url).read()
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
            if self.is_package(metadata, item):
                newpkg.add(item)
                try:
                    newdeps = [x for x in self.get_deps(metadata, item) \
                               if x not in newpkg and x not in work]
                    if debug and newdeps:
                        logger.debug("Package %s: adding new deps %s" \
                                     %(item, str(newdeps)))
                    work.update(newdeps)
                except NoData:
                    continue
            else:
                # provides dep
                try:
                    pset = self.get_provides(metadata, item)
                    if debug:
                        logger.debug("VPackage %s: got provides %s" \
                                     % (item, list(pset)))
                    if len(pset) == 1:
                        work.update(pset)
                    else:
                        if True not in [p in newpkg for p in pset]:
                            # FIXME: still hacky; unchosen multiple provides still not handled
                            unknown.add(item)
                except NoData:
                    unknown.add(item)
            work = work.difference(seen)
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
        data = cPickle.dump((self.packages, self.deps, self.provides,
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
                rmdurl = surl + '/repodata/repomd.xml'
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
                    self.file_to_arch[self.escape_url(fullurl)] = arch
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
            for fentry in pkg.findall(self.fl + 'file'):
                if fentry in self.needed_paths:
                    self.filemap[arch][fentry.text] = pkg.get('name')

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
        arch = arches[0]
        if required in self.provides['global']: 
            ret.update(Source.get_provides(self, metadata, required))
        elif required in self.provides[arch]:
            ret.update(Source.get_provides(self, metadata, required))
        elif required in self.filemap['global']:
            ret.update([self.filemap['global'][required]])
        elif required in self.filemap[arch]:
            ret.update([self.filemap[arch][required]])
        else:
            raise NoData
        return ret

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
        data = cPickle.dump((self.pkgnames, self.deps, self.provides),
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
            bin = [x for x in fname.split('@') if x.startswith('binary-')][0][7:]
            if bin not in bdeps:
                bdeps[bin] = dict()
                bprov[bin] = dict()
            try:
                reader = gzip.GzipFile(fname)
            except:
                print "failed to read file %s" % fname
                raise Exception()
                continue
            for line in reader.readlines():
                words = line.strip().split(':', 1)
                if words[0] == 'Package':
                    pkgname = words[1].strip().rstrip()
                    self.pkgnames.add(pkgname)
                elif words[0] == 'Depends':
                    bdeps[bin][pkgname] = []
                    for dep in words[1].split(','):
                        raw_dep = re.sub('\(.*\)', '', dep)
                        if '|' in raw_dep:
                            # FIXME hack alert
                            raw_dep = raw_dep.split('|')[0]
                        raw_dep = raw_dep.rstrip().strip()
                        bdeps[bin][pkgname].append(raw_dep)
                elif words[0] == 'Provides':
                    for pkg in words[1].split(','):
                        dname = pkg.rstrip().strip()
                        if dname not in bprov[bin]:
                            bprov[bin][dname] = set()
                        bprov[bin][dname].add(pkgname)

        self.deps['global'] = dict()
        self.provides['global'] = dict()
        for bin in bdeps:
            self.deps[bin] = dict()
            self.provides[bin] = dict()
        for pkgname in self.pkgnames:
            pset = set()
            for bin in bdeps:
                if pkgname not in bdeps[bin]:
                    bdeps[bin][pkgname] = []
                pset.add(tuple(bdeps[bin][pkgname]))
            if len(pset) == 1:
                self.deps['global'][pkgname] = pset.pop()
            else:
                for bin in bdeps:
                    self.deps[bin][pkgname] = bdeps[bin][pkgname]
        provided = set()
        for bin in bprov:
            for prov in bprov[bin]:
                provided.add(prov)
        for prov in provided:
            prset = set()
            for bin in bprov:
                if prov not in bprov[bin]:
                    continue
                prset.add(tuple(bprov[bin].get(prov, ())))
            if len(prset) == 1:
                self.provides['global'][prov] = prset.pop()
            else:
                for bin in bprov:
                    self.provides[bin][prov] = bprov[bin].get(prov, ())
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
    
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.StructureValidator.__init__(self)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        cachepath = self.data + '/cache'
        self.sentinels = set()
        if not os.path.exists(cachepath):
            # create cache directory if needed
            os.makedirs(cachepath)
        try:
            xdata = lxml.etree.parse(self.data + '/config.xml').getroot()
        except IOError, e:
            self.logger.error("Failed to read Packages configuration. Have"
                              " you created your config.xml file?")
            raise Bcfg2.Server.Plugin.PluginInitError
        self.sources = []
        for s in xdata.findall('APTSource'):
            self.sources.append(APTSource(cachepath, **source_from_xml(s)))
        for s in xdata.findall('YUMSource'):
            self.sources.append(YUMSource(cachepath, **source_from_xml(s)))
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
        sources = self.get_matching_sources(meta)
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
        initial = set([pkg.get('name') for struct in structures \
                       for pkg in struct.findall('Package')])
        news = lxml.etree.Element('Independent')
        packages, unknown, ptype = self.complete(meta, initial)
        if unknown:
            self.logger.info("Got unknown entries")
            self.logger.info(list(unknown))
        for pkg in packages.difference(initial):
            lxml.etree.SubElement(news, 'BoundPackage', name=pkg,
                                  type=ptype, version='auto')
        structures.append(news)

if __name__ == '__main__':
    Bcfg2.Logger.setup_logging('Packages',to_console=True)
    aa = Packages(None, '/home/desai/tmp/bcfg2')
