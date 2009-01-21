import copy, gzip, lxml.etree, re, urllib
import Bcfg2.Server.Plugin

# build sources.list?
# caching
# pinning

def apt_source_from_xml(xsource):
    ret = dict()
    for key, tag in [('groups', 'Group'), ('components', 'Component'),
                     ('arches', 'Arch')]:
        ret[key] = [item.text for item in xsource.findall(tag)]
    ret['version'] = xsource.find('Version').text
    ret['url'] = xsource.find('URL').text
    return ret

class APTSource(object):
    def __init__(self, basepath, url, version, arches, components, groups):
        self.basepath = basepath
        self.version = version
        self.components = components
        self.url = url
        self.urls = ["%s/dists/%s/%s/binary-%s/Packages.gz" % \
                     (url, version, part, arch) for part in components \
                     for arch in arches]
        self.files = [self.mk_fname(url) for url in self.urls]
        self.groups = groups
        self.deps = dict()

    def get_aptsrc(self):
        return ["deb %s %s %s" % (self.url, self.version,
                                  " ".join(self.components)),
                "deb-src %s %s %s" % (self.url, self.version,
                                      " ".join(self.components))]

    def mk_fname(self, url):
        return "%s/%s" % (self.basepath, url.replace('/', '_'))

    def read_files(self):
        bdeps = dict()
        for fname in self.files:
            bin = [x for x in fname.split('_') if x.startswith('binary-')][0][7:]
            if bin not in bdeps:
                bdeps[bin] = dict()
            reader = gzip.GzipFile(fname)
            for line in reader.readlines():
                words = line.strip().split(':', 1)
                if words[0] == 'Package':
                    pkgname = words[1].strip().rstrip()
                elif words[0] == 'Depends':
                    bdeps[bin][pkgname] = []
                    for dep in words[1].split(','):
                        raw_dep = re.sub('\(.*\)', '', dep)
                        if '|' in raw_dep:
                            # FIXME hack alert
                            raw_dep = raw_dep.split('|')[0]
                        raw_dep = raw_dep.rstrip().strip()
                        bdeps[bin][pkgname].append(raw_dep)
        pkgnames = set()
        self.deps['global'] = dict()
        for bin in bdeps:
            [pkgnames.add(pname) for pname in bdeps[bin]]
            self.deps[bin] = dict()
        for pkgname in pkgnames:
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
        

    def update(self):
        for url in self.urls:
            print "updating", url
            fname = self.mk_fname(url)
            data = urllib.urlopen(url).read()
            output = file(fname, 'w').write(data)

    def applies(self, metadata):
        return len([g for g in metadata.groups if g in self.groups]) \
               == len(self.groups)

    def get_deps(self, metadata, pkgname):
        if pkgname in self.deps['global']:
            return self.deps['global'][pkgname]
        for arch in [ar for ar in self.deps if ar in metadata.groups]:
            if pkgname in self.deps[arch]:
                return self.deps[arch][pkgname]
        return False

class Packages(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.StructureValidator,
               Bcfg2.Server.Plugin.Generator):
    name = 'Packages'
    
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.StructureValidator.__init__(self)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        cachepath = self.data + '/cache'
        xdata = lxml.etree.parse(self.data + '/config.xml').getroot()
        self.sources = []
        for s in xdata.findall('APTSource'):
            self.sources.append(APTSource(cachepath, **apt_source_from_xml(s)))
        for source in self.sources:
            try:
                source.read_files()
            except:
                source.update()
                source.read_files()
        self.pkgmap = dict()

    def find_deps(self, metadata, pkgname):
        for source in self.sources:
            if source.applies(metadata):
                deps = source.get_deps(metadata, pkgname)
                if deps:
                    return deps
        return ()

    def HandlesEntry(self, entry, metadata):
        if [x for x in metadata.groups if x in ['debian', 'ubuntu']]:
            return True
        return False

    def HandleEntry(self, entry, metadata):
        entry.set('version', 'auto')
        entry.set('type', 'deb')

    def validate_structures(self, meta, structures):
        if [g for g in meta.groups if g in ['debian', 'ubuntu']]:
            ptype = 'deb'
        else:
            return
        pkgnames = set()
        for struct in structures:
            for pkg in struct.findall('Package'):
                pkgnames.add(pkg.get('name'))
        all = copy.copy(pkgnames)
        work = copy.copy(pkgnames)
        new = set()
        while work:
            next = work.pop()
            for dep in self.find_deps(meta, next):
                if dep in all:
                    continue
                else:
                    new.add(dep)
                    all.add(dep)
                    work.add(dep)
        news = lxml.etree.Element('Independent')
        for pkg in new:
            lxml.etree.SubElement(news, 'BoundPackage', name=pkg,
                                  type=ptype, version='auto')
        structures.append(news)

if __name__ == '__main__':
    aa = Packages(None, '/home/desai/tmp/bcfg2')
