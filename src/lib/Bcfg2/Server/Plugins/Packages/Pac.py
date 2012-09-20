""" Pacman backend for :mod:`Bcfg2.Server.Plugins.Packages` """

import tarfile
from Bcfg2.Server.Plugins.Packages.Collection import Collection
from Bcfg2.Server.Plugins.Packages.Source import Source


class PacCollection(Collection):
    """ Handle collections of Pacman sources.  This is a no-op object
    that simply inherits from
    :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`,
    overrides nothing, and defers all operations to :class:`PacSource`
    """
    pass


class PacSource(Source):
    """ Handle Pacman sources """

    #: :ref:`server-plugins-generators-packages-magic-groups` for
    #: ``PacSource`` are "arch" and "parabola"
    basegroups = ['arch', 'parabola']

    #: PacSource sets the ``type`` on Package entries to "pacman"
    ptype = 'pacman'

    @property
    def urls(self):
        """ A list of URLs to the base metadata file for each
        repository described by this source. """
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
    read_files.__doc__ = Source.read_files.__doc__
