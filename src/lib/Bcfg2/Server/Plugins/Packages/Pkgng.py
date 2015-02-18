""" pkgng backend for :mod:`Bcfg2.Server.Plugins.Packages` """

import lzma
import tarfile

try:
    import json
    # py2.4 json library is structured differently
    json.loads  # pylint: disable=W0104
except (ImportError, AttributeError):
    import simplejson as json

from Bcfg2.Server.Plugins.Packages.Collection import Collection
from Bcfg2.Server.Plugins.Packages.Source import Source


class PkgngCollection(Collection):
    """ Handle collections of pkgng sources.  This is a no-op object
    that simply inherits from
    :class:`Bcfg2.Server.Plugins.Packages.Collection.Collection`,
    overrides nothing, and defers all operations to :class:`PacSource`
    """

    def __init__(self, metadata, sources, cachepath, basepath, debug=False):
        # we define an __init__ that just calls the parent __init__,
        # so that we can set the docstring on __init__ to something
        # different from the parent __init__ -- namely, the parent
        # __init__ docstring, minus everything after ``.. -----``,
        # which we use to delineate the actual docs from the
        # .. autoattribute hacks we have to do to get private
        # attributes included in sphinx 1.0 """
        Collection.__init__(self, metadata, sources, cachepath, basepath,
                            debug=debug)
    __init__.__doc__ = Collection.__init__.__doc__.split(".. -----")[0]


class PkgngSource(Source):
    """ Handle pkgng sources """

    #: PkgngSource sets the ``type`` on Package entries to "pkgng"
    ptype = 'pkgng'

    @property
    def urls(self):
        """ A list of URLs to the base metadata file for each
        repository described by this source. """
        if not self.rawurl:
            rv = []
            for part in self.components:
                for arch in self.arches:
                    rv.append("%s/freebsd:%s:%s/%s/packagesite.txz" %
                              (self.url, self.version, arch, part))
            return rv
        else:
            return ["%s/packagesite.txz" % self.rawurl]

    def read_files(self):
        bdeps = dict()
        for fname in self.files:
            if not self.rawurl:
                abi = [x
                       for x in fname.split('@')
                       if x.startswith('freebsd:')][0][8:]
                barch = ':'.join(abi.split(':')[1:])
            else:
                # RawURL entries assume that they only have one <Arch></Arch>
                # element and that it is the architecture of the source.
                barch = self.arches[0]
            if barch not in bdeps:
                bdeps[barch] = dict()
            try:
                tar = tarfile.open(fileobj=lzma.LZMAFile(fname))
                reader = tar.extractfile('packagesite.yaml')
            except (IOError, tarfile.TarError):
                self.logger.error("Packages: Failed to read file %s" % fname)
                raise
            for line in reader.readlines():
                if not isinstance(line, str):
                    line = line.decode('utf-8')
                pkg = json.loads(line)
                pkgname = pkg['name']
                self.pkgnames.add(pkgname)
                if 'deps' in pkg:
                    bdeps[barch][pkgname] = pkg['deps'].keys()
        self.process_files(bdeps, dict())
    read_files.__doc__ = Source.read_files.__doc__
