import copy, gzip, lxml.etree, re, urllib
import os
import Bcfg2.Server.Plugin

# build sources.list?
# caching
# pinning
# multi apt-source from xml

class NoData(Exception):
    pass

def source_from_xml(xsource):
    ret = dict()
    for key, tag in [('groups', 'Group'), ('components', 'Component'),
                     ('arches', 'Arch')]:
        ret[key] = [item.text for item in xsource.findall(tag)]
    ret['version'] = xsource.find('Version').text
    ret['url'] = xsource.find('URL').text
    return ret

class Source(object):
    basegroups = []
    def __init__(self, basepath, url, version, arches, components, groups):
        self.basepath = basepath
        self.version = version
        self.components = components
        self.url = url
        self.groups = groups
        self.arches = arches
        self.deps = dict()
        self.provides = dict()
        self.files = [self.mk_fname(url) for url in self.urls]

    def mk_fname(self, url):
        return "%s/%s" % (self.basepath, url.replace('/', '@'))

    def file_init(self):
        pass

    def read_files(self):
        pass
    
    def update(self):
        for url in self.urls:
            print "updating", url
            fname = self.mk_fname(url)
            data = urllib.urlopen(url).read()
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

    def complete(self, metadata, packages, unresolved):
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
                    work.update(self.get_deps(metadata, item))
                except NoData:
                    continue
            else:
                # provides dep
                try:
                    work.update(self.get_provides(metadata, item))
                except NoData:
                    unknown.add(item)
            work = work.difference(seen)
        return (newpkg, unknown)

class YUMSource(Source):
    xp = '{http://linux.duke.edu/metadata/common}'
    rp = '{http://linux.duke.edu/metadata/rpm}'
    fl = '{http://linux.duke.edu/metadata/filelists}'
    basegroups = ['redhat', 'centos']
    ptype = 'yum'
    
    def __init__(self, basepath, url, version, arches, components, groups):
        self.urls = ["%s/%s/%s/%s/repodata/%s.xml.gz" % \
                     (url, version, part, arch, basename) for part in components \
                     for arch in arches for basename in ['primary', 'filelists']]
        Source.__init__(self, basepath, url, version, arches, components, groups)
        self.packages = dict()
        self.deps = dict([('global', dict())])
        self.provides = dict([('global', dict())])
        self.filemap = dict([(x, dict()) for x in ['global'] + self.arches])

    def read_files(self):
        for fname in self.files:
            farch = fname.split('@')[-3]
            fdata = lxml.etree.parse(fname).getroot()
            if fname.endswith('primary.xml.gz'):
                self.parse_primary(fdata, farch)
            elif fname.endswith('filelists.xml.gz'):
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
        
    def parse_filelist(self, data, arch):
        for pkg in data.findall(self.fl + 'package'):
            for fentry in pkg.findall(self.fl + 'file'):
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
            if pkgname in self.deps[arch]:
                continue
            pre = pdata.find(self.rp + 'requires')
            self.deps[arch][pkgname] = set()
            for entry in pre.getchildren():
                self.deps[arch][pkgname].add(entry.get('name'))
            pro = pdata.find(self.rp + 'provides')
            for entry in pro.getchildren():
                prov = entry.get('name')
                if prov not in self.provides[arch]:
                    self.provides[arch][prov] = list()
                self.provides[arch][prov].append(pkgname)

    def is_package(self, metadata, item):
        arch = [a for a in self.arches if a in metadata.groups][0]
        return item in self.packages['global'] or item in self.packages[arch]

    def get_provides(self, metadata, required):
        ret = set()
        arch = [a for a in self.arches if a in metadata.groups][0]
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

    def complete(self, metadata, packages, unknown):
        p1, u1 = Source.complete(self, metadata, packages, unknown)
        return (p1, set([u for u in u1 if not u.startswith('rpmlib')]))

class APTSource(Source):
    basegroups = ['debian', 'ubuntu', 'nexenta']
    ptype = 'deb'
    
    def __init__(self, basepath, url, version, arches, components, groups):
        self.urls = ["%s/dists/%s/%s/binary-%s/Packages.gz" % \
                     (url, version, part, arch) for part in components \
                     for arch in arches]
        Source.__init__(self, basepath, url, version, arches, components, groups)
        self.pkgnames = set()

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

    def is_package(self, _, pkg):
        return pkg in self.pkgnames

    def get_provides(self, metadata, pkgname):
        arches = [ar for ar in self.provides if ar in metadata.groups]
        for arch in ['global'] + arches:
            if pkgname in self.provides[arch]:
                # FIXME next round of provides HACK alert
                return set([self.provides[arch][pkgname][0]])
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
        if not os.path.exists(cachepath):
            # create cache directory if needed
            os.mkdir(cachepath)
        xdata = lxml.etree.parse(self.data + '/config.xml').getroot()
        self.sources = []
        for s in xdata.findall('APTSource'):
            self.sources.append(APTSource(cachepath, **source_from_xml(s)))
        for s in xdata.findall('YUMSource'):
            self.sources.append(YUMSource(cachepath, **source_from_xml(s)))
        for source in self.sources:
            try:
                source.read_files()
            except:
                self.logger.info("File read failed; updating sources", exc_info=1)
                source.update()
                source.read_files()

    def get_matching_sources(self, meta):
        return [s for s in self.sources if s.applies(meta)]

    def HandlesEntry(self, entry, metadata):
        if [x for x in metadata.groups if x in ['debian', 'ubuntu', 'redhat']] \
               and entry.tag == 'Package':
            return True
        return False

    def HandleEntry(self, entry, metadata):
        entry.set('version', 'auto')
        for source in self.sources:
            if [x for x in metadata.groups if x in source.basegroups]:
                entry.set('type', source.ptype)                

    def complete(self, meta, packages):
        sources = self.get_matching_sources(meta)
        ptype = set([s.ptype for s in sources])
        if len(ptype) > 1:
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
                pkgs, unknown = source.complete(meta, pkgs, unknown)
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
    aa = Packages(None, '/home/desai/tmp/bcfg2')
