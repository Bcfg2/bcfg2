import re
import gzip
from Bcfg2.Server.Plugins.Packages.Collection import _Collection
from Bcfg2.Server.Plugins.Packages.Source import Source


class AptCollection(_Collection):
    def get_config(self):
        lines = ["# This config was generated automatically by the Bcfg2 " \
                     "Packages plugin", '']

        for source in self:
            if source.rawurl:
                self.logger.info("Packages: Skipping rawurl %s" % source.rawurl)
            else:
                lines.append("deb %s %s %s" % (source.url, source.version,
                                               " ".join(source.components)))
                lines.append("")

        return "\n".join(lines)


class AptSource(Source):
    basegroups = ['apt', 'debian', 'ubuntu', 'nexenta']
    ptype = 'deb'

    @property
    def urls(self):
        if not self.rawurl:
            rv = []
            for part in self.components:
                for arch in self.arches:
                    rv.append("%sdists/%s/%s/binary-%s/Packages.gz" %
                              (self.url, self.version, part, arch))
            return rv
        else:
            return ["%sPackages.gz" % self.rawurl]

    def read_files(self):
        bdeps = dict()
        bprov = dict()
        depfnames = ['Depends', 'Pre-Depends']
        if self.recommended:
            depfnames.append('Recommends')
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
                self.logger.error("Packages: Failed to read file %s" % fname)
                raise
            for line in reader.readlines():
                words = str(line.strip()).split(':', 1)
                if words[0] == 'Package':
                    pkgname = words[1].strip().rstrip()
                    self.pkgnames.add(pkgname)
                    bdeps[barch][pkgname] = []
                elif words[0] == 'Essential' and self.essential:
                    self.essentialpkgs.add(pkgname)
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
        self.process_files(bdeps, bprov)
