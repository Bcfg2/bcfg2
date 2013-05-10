""" APT backend for :mod:`Bcfg2.Server.Plugins.Packages` """

import re
import gzip
from Bcfg2.Server.Plugins.Packages.Collection import Collection
from Bcfg2.Server.Plugins.Packages.Source import Source


class AptCollection(Collection):
    """ Handle collections of APT sources.  This is a no-op object
    that simply inherits from
    :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`,
    overrides nothing, and defers all operations to :class:`PacSource`
    """

    def __init__(self, metadata, sources, cachepath, basepath, fam,
                 debug=False):
        # we define an __init__ that just calls the parent __init__,
        # so that we can set the docstring on __init__ to something
        # different from the parent __init__ -- namely, the parent
        # __init__ docstring, minus everything after ``.. -----``,
        # which we use to delineate the actual docs from the
        # .. autoattribute hacks we have to do to get private
        # attributes included in sphinx 1.0 """
        Collection.__init__(self, metadata, sources, cachepath, basepath, fam,
                            debug=debug)
    __init__.__doc__ = Collection.__init__.__doc__.split(".. -----")[0]

    def get_config(self):
        """ Get an APT configuration file (i.e., ``sources.list``).

        :returns: string """
        lines = ["# This config was generated automatically by the Bcfg2 "
                 "Packages plugin", '']

        for source in self:
            if source.rawurl:
                self.logger.info("Packages: Skipping rawurl %s" %
                                 source.rawurl)
            else:
                lines.append("deb %s %s %s" % (source.url, source.version,
                                               " ".join(source.components)))
                if source.debsrc:
                    lines.append("deb-src %s %s %s" %
                                 (source.url,
                                  source.version,
                                  " ".join(source.components)))
                lines.append("")

        return "\n".join(lines)


class AptSource(Source):
    """ Handle APT sources """

    #: :ref:`server-plugins-generators-packages-magic-groups` for
    #: ``AptSource`` are "apt", "debian", "ubuntu", and "nexenta"
    basegroups = ['apt', 'debian', 'ubuntu', 'nexenta']

    #: AptSource sets the ``type`` on Package entries to "deb"
    ptype = 'deb'

    @property
    def urls(self):
        """ A list of URLs to the base metadata file for each
        repository described by this source. """
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
                if not isinstance(line, str):
                    line = line.decode('utf-8')
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
                            cdeps = [re.sub(r'\s+', '',
                                            re.sub(r'\(.*\)', '', cdep))
                                     for cdep in dep.split('|')]
                            dyn_dname = "choice-%s-%s-%s" % (pkgname,
                                                             barch,
                                                             vindex)
                            vindex += 1
                            bdeps[barch][pkgname].append(dyn_dname)
                            bprov[barch][dyn_dname] = set(cdeps)
                        else:
                            raw_dep = re.sub(r'\(.*\)', '', dep)
                            raw_dep = raw_dep.rstrip().strip()
                            bdeps[barch][pkgname].append(raw_dep)
                elif words[0] == 'Provides':
                    for pkg in words[1].split(','):
                        dname = pkg.rstrip().strip()
                        if dname not in bprov[barch]:
                            bprov[barch][dname] = set()
                        bprov[barch][dname].add(pkgname)
        self.process_files(bdeps, bprov)
    read_files.__doc__ = Source.read_files.__doc__
