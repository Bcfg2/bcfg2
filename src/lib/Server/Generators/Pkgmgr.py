'''This module implements a package management scheme for all images'''
__revision__ = '$Revision$'

from re import compile as regcompile

from Bcfg2.Server.Generator import Generator, GeneratorError, DirectoryBacked, XMLFileBacked

class PackageEntry(XMLFileBacked):
    '''PackageEntry is a set of packages and locations for a single image'''
    __identifier__ = 'image'
    rpm = regcompile('^(?P<name>[\w\+\d\.]+(-[\w\+\d\.]+)*)-(?P<version>[\w\d\.]+-([\w\d\.]+))\.(?P<arch>\w+)\.rpm$')

    def Index(self):
        '''Build internal data structures'''
        XMLFileBacked.Index(self)
        self.packages = {}
        for location in self.entries:
            for pkg in location.getchildren():
                if pkg.attrib.has_key("file"):
                    mdata = self.rpm.match(pkg.get('file'))
                    if not mdata:
                        print "failed to rpm match %s" % (pkg.get('file'))
                        continue
                    pkgname = mdata.group('name')
                    self.packages[pkgname] = mdata.groupdict()
                    self.packages[pkgname]['file'] = pkg.attrib['file']
                    self.packages[pkgname]['uri'] = location.attrib['uri']
                    self.packages[pkgname]['type'] = 'rpm'
                else:
                    self.packages[pkg.get('name')] = pkg.attrib

class PackageDir(DirectoryBacked):
    '''A directory of package files'''
    __child__ = PackageEntry

class Pkgmgr(Generator):
    '''This is a generator that handles package assignments'''
    __name__ = 'Pkgmgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Generator.__init__(self, core, datastore)
        self.pkgdir = PackageDir(self.data, self.core.fam)

    def FindHandler(self, entry):
        '''Non static mechanism of determining entry provisioning'''
        if entry.tag != 'Package':
            raise GeneratorError, (entry.tag, entry.get('name'))
        return self.LocatePackage

    def LocatePackage(self, entry, metadata):
        '''Locates a package entry for particular metadata'''
        pkgname = entry.get('name')
        if self.pkgdir.entries.has_key("%s.xml" % metadata.hostname):
            pkglist = self.pkgdir["%s.xml" % metadata.hostname]
            if pkglist.packages.has_key(pkgname):
                entry.attrib.update(pkglist.packages[pkgname])
                return
        pkglist = self.pkgdir["%s.xml" % (metadata.image)]
        if pkglist.packages.has_key(pkgname):
            pkg = pkglist.packages[pkgname]
            if pkg.get('type', None) == 'rpm':
                entry.attrib.update({'url':"%s/%s" % (pkg['uri'], pkg['file']), 'version':pkg['version']})
            else:
                entry.attrib.update(pkg)
        else:
            raise GeneratorError, ("Package", pkgname)
