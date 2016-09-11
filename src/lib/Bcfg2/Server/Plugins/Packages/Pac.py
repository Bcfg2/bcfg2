""" Pacman backend for :mod:`Bcfg2.Server.Plugins.Packages` """

import os
import tarfile
from Bcfg2.Server.Plugins.Packages.Collection import Collection
from Bcfg2.Server.Plugins.Packages.Source import Source


def parse_db_file(pkgfile):
    """ Parse a Pacman database file, returning a dictionary with
    section headings for keys and lists of strings for values.
    (Reference: ``sync_db_read`` in ``lib/libalpm/be_sync.c``)
    """

    pkg = {}
    section = None

    for line in pkgfile:
        line = line.strip()

        if section is not None:
            if not line:
                section = None
            else:
                pkg[section].append(line)
        elif len(line) >= 2 and line[0] == line[-1] == '%':
            section = line
            pkg[section] = []

    return pkg


def parse_dep(dep):
    """ Parse a Pacman dependency string, returning the package name,
    version restriction (or ``None``), and description (or ``None``).
    (Reference: ``alpm_dep_from_string`` in ``lib/libalpm/deps.c``)
    """

    rest_desc = dep.split(': ', 1)
    if len(rest_desc) == 1:
        rest, desc = rest_desc[0], None
    else:
        rest, desc = rest_desc

    # Search for '=' last, since '<=' and '>=' are possible.
    for symb in ['<', '>', '=']:
        idx = rest.find(symb)
        if idx >= 0:
            name = rest[:idx]
            version = rest[idx:]
            break
    else:
        name = rest
        version = None

    return name, version, desc


class PacCollection(Collection):
    """ Handle collections of Pacman sources.  This is a no-op object
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


class PacSource(Source):
    """ Handle Pacman sources """

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
        bdeps = {}
        brecs = {}
        bprov = {}

        for fname in self.files:
            if not self.rawurl:
                barch = [x for x in fname.split('@') if x in self.arches][0]
            else:
                # RawURL entries assume that they only have one <Arch></Arch>
                # element and that it is the architecture of the source.
                barch = self.arches[0]

            if barch not in bdeps:
                bdeps[barch] = {}
                brecs[barch] = {}
                bprov[barch] = {}
            try:
                self.debug_log("Packages: try to read %s" % fname)
                tar = tarfile.open(fname, "r")
            except (IOError, tarfile.TarError):
                self.logger.error("Packages: Failed to read file %s" % fname)
                raise

            packages = {}
            for tarinfo in tar:
                if not tarinfo.isfile():
                    continue
                prefix = os.path.dirname(tarinfo.name)
                if prefix not in packages:
                    packages[prefix] = {}
                pkg = parse_db_file(tar.extractfile(tarinfo))
                packages[prefix].update(pkg)

            for pkg in packages.values():
                pkgname = pkg['%NAME%'][0]
                self.pkgnames.add(pkgname)
                bdeps[barch][pkgname] = []
                brecs[barch][pkgname] = []

                if '%DEPENDS%' in pkg:
                    for dep in pkg['%DEPENDS%']:
                        dname = parse_dep(dep)[0]
                        bdeps[barch][pkgname].append(dname)

                if '%OPTDEPENDS%' in pkg:
                    for dep in pkg['%OPTDEPENDS%']:
                        dname = parse_dep(dep)[0]
                        brecs[barch][pkgname].append(dname)

                if '%PROVIDES%' in pkg:
                    for dep in pkg['%PROVIDES%']:
                        dname = parse_dep(dep)[0]
                        if dname not in bprov[barch]:
                            bprov[barch][dname] = set()
                        bprov[barch][dname].add(pkgname)

            tar.close()
        self.process_files(bdeps, bprov, brecs)
    read_files.__doc__ = Source.read_files.__doc__
