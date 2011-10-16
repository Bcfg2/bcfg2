import gzip
import tarfile
import logging
from Bcfg2.Bcfg2Py3k import cPickle, file
from Bcfg2.Server.Plugins.Packages.Collection import Collection
from Bcfg2.Server.Plugins.Packages.Source import Source

logger = logging.getLogger("Packages")

class PacCollection(Collection):
    def get_group(self, group):
        self.logger.warning("Packages: Package groups are not supported by APT")
        return []

class PacSource(Source):
    basegroups = ['arch', 'parabola']
    ptype = 'pacman'

    def __init__(self, basepath, xsource, config):
        Source.__init__(self, basepath, xsource, config)
        self.pkgnames = set()

        self.url_map = [{'rawurl': self.rawurl, 'url': self.url,
                         'version': self.version,
                         'components': self.components, 'arches': self.arches}]

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
            rv = []
            for part in self.components:
                for arch in self.arches:
                    rv.append("%s%s/os/%s/%s.db.tar.gz" %
                              (self.url, part, arch, part))
            return rv
        else:
            raise Exception("PacSource : RAWUrl not supported (yet)")
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
                logger.debug("Packages: try to read : " + fname)
                tar = tarfile.open(fname, "r")
                reader = gzip.GzipFile(fname)
            except:
                logger.error("Packages: Failed to read file %s" % fname)
                raise

            for tarinfo in tar:
                if tarinfo.isdir():
                    self.pkgnames.add(tarinfo.name.rsplit("-", 2)[0])
                    logger.debug("Packages: added : " + tarinfo.name.rsplit("-", 2)[0])
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
