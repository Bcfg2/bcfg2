'''This module implements a package management scheme for all images'''
__revision__ = '$Revision$'

from copy import deepcopy
from re import compile as regcompile

from Bcfg2.Server.Plugin import Plugin, PluginInitError, PluginExecutionError, DirectoryBacked, XMLFileBacked

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
                if location.attrib.has_key('type'):
                    pkg.set('type', location.get('type'))
                if pkg.attrib.has_key("simplefile"):
                    self.packages[pkg.get('name')] = deepcopy(pkg.attrib)
                    # most attribs will be set from pkg
                    self.packages[pkg.get('name')]['uri'] = "%s/%s" % (location.get('uri'), pkg.get('simplefile'))
                elif pkg.attrib.has_key("file"):
                    mdata = self.rpm.match(pkg.get('file'))
                    if not mdata:
                        print "failed to rpm match %s" % (pkg.get('file'))
                        continue
                    pkgname = mdata.group('name')
                    self.packages[pkgname] = mdata.groupdict()
                    self.packages[pkgname]['file'] = pkg.get('file')
                    self.packages[pkgname]['uri'] = location.get('uri')
                    self.packages[pkgname]['type'] = 'rpm'
                else:
                    self.packages[pkg.get('name')] = pkg.attrib

class PackageDir(DirectoryBacked):
    '''A directory of package files'''
    __child__ = PackageEntry

class Pkgmgr(Plugin):
    '''This is a generator that handles package assignments'''
    __name__ = 'Pkgmgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        try:
            self.pkgdir = PackageDir(self.data, self.core.fam)
        except OSError:
            self.LogError("Pkgmgr: Failed to load package indices")
            raise PluginInitError

    def FindHandler(self, entry):
        '''Non static mechanism of determining entry provisioning'''
        if entry.tag != 'Package':
            raise PluginExecutionError, (entry.tag, entry.get('name'))
        return self.LocatePackage

    def LocatePackage(self, entry, metadata):
        '''Locates a package entry for particular metadata'''
        pkgname = entry.get('name')
        if self.pkgdir.entries.has_key("%s.xml" % metadata.hostname):
            pkglist = self.pkgdir["%s.xml" % metadata.hostname]
            if pkglist.packages.has_key(pkgname):
                entry.attrib.update(pkglist.packages[pkgname])
                return
        elif not self.pkgdir.entries.has_key("%s.xml" % metadata.image):
            self.LogError("Pkgmgr: no package index for image %s" % metadata.image)
            raise PluginExecutionError, ("Image", metadata.image)
        pkglist = self.pkgdir["%s.xml" % (metadata.image)]
        if pkglist.packages.has_key(pkgname):
            pkg = pkglist.packages[pkgname]
            if pkg.get('type', None) == 'rpm':
                entry.attrib.update({'url':"%s/%s" % (pkg['uri'], pkg['file']), 'version':pkg['version']})
            else:
                entry.attrib.update(pkg)
        else:
            raise PluginExecutionError, ("Package", pkgname)
