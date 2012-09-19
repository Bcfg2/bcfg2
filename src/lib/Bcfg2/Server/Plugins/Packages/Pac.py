import tarfile
from Bcfg2.Server.Plugins.Packages.Collection import _Collection
from Bcfg2.Server.Plugins.Packages.Source import Source


class PacCollection(_Collection):
    pass


class PacSource(Source):
    basegroups = ['arch', 'parabola']
    ptype = 'pacman'

    @property
    def urls(self):
        if not self.rawurl:
            rv = []
            for part in self.components:
                for arch in self.arches:
                    rv.append("%s%s/os/%s/%s.db.tar.gz" %
                              (self.url, part, arch, part))
            return rv
        else:
            raise Exception("PacSource : RAWUrl not supported (yet)")

    def read_files(self):
        bdeps = dict()
        bprov = dict()

        depfnames = ['Depends', 'Pre-Depends']
        if self.recommended:
            depfnames.append('Recommends')

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
                self.debug_log("Packages: try to read %s" % fname)
                tar = tarfile.open(fname, "r")
            except:
                self.logger.error("Packages: Failed to read file %s" % fname)
                raise

            for tarinfo in tar:
                if tarinfo.isdir():
                    self.pkgnames.add(tarinfo.name.rsplit("-", 2)[0])
                    self.debug_log("Packages: added %s" %
                                   tarinfo.name.rsplit("-", 2)[0])
            tar.close()
        self.process_files(bdeps, bprov)
