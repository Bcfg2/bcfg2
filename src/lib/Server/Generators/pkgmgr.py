#!/usr/bin/env python

'''This module implements a package management scheme for all images'''
__revision__ = '$Revision$'

from re import compile as regcompile

from Bcfg2.Server.Generator import Generator, DirectoryBacked, XMLFileBacked

class PackageEntry(XMLFileBacked):
    '''PackageEntry is a set of packages and locations for a single image'''
    __identifier__ = 'image'
    rpm = regcompile('^(?P<name>[\w\+\d\.]+(-[\w\+\d\.]+)*)-(?P<version>[\w\d\.]+-([\w\d\.]+))\.(?P<arch>\w+)\.rpm$')

    def Index(self):
        XMLFileBacked.Index(self)
        self.packages = {}
        for location in self.entries:
            for pkg in location.getchildren():
                if pkg.attrib.has_key("file"):
                    m = self.rpm.match(pkg.get('file'))
                    if not m:
                        print "failed to rpm match %s" % (pkg.get('file'))
                        continue
                    self.packages[m.group('name')] = m.groupdict()
                    self.packages[m.group('name')]['file'] = pkg.attrib['file']
                    self.packages[m.group('name')]['uri'] = location.attrib['uri']
                    self.packages[m.group('name')]['type'] = 'rpm'
                else:
                    self.packages[pkg.get('name')] = pkg.attrib

class PackageDir(DirectoryBacked):
    __child__ = PackageEntry

class pkgmgr(Generator):
    '''This is a generator that handles package assignments'''
    __name__ = 'pkgmgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __setup__(self):
        self.pkgdir = PackageDir(self.data, self.core.fam)

    def FindHandler(self, entry):
        if entry.tag != 'Package':
            raise KeyError, (entry.tag, entry.get('name'))
        return self.LocatePackage

    def LocatePackage(self, entry, metadata):
        '''Locates a package entry for particular metadata'''
        pkgname = entry.get('name')
        pl = self.pkgdir["%s.xml" % (metadata.image)]
        if pl.packages.has_key(pkgname):
            p = pl.packages[pkgname]
            if p.get('type', None) == 'rpm':
                entry.attrib.update({'url':"%s/%s" % (p['uri'], p['file']), 'version':p['version']})
            else:
                entry.attrib.update(p)
        else:
            raise KeyError, ("Package", pkgname)
