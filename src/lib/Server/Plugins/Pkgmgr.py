'''This module implements a package management scheme for all images'''
__revision__ = '$Revision$'

import re
from syslog import syslog, LOG_ERR
import Bcfg2.Server.Plugin

class PNode(Bcfg2.Server.Plugin.LNode):
    '''PNode has a list of packages available at a particular group intersection'''
    splitters = {'rpm':re.compile('^(?P<name>[\w\+\d\.]+(-[\w\+\d\.]+)*)-' + \
                                  '(?P<version>[\w\d\.]+-([\w\d\.]+))\.(?P<arch>\w+)\.rpm$'),
                 'encap':re.compile('^(?P<name>\w+)-(?P<version>[\w\d\.-]+).encap.*$')}
    
    def __init__(self, data, plist, parent=None):
        # copy local attributes to all child nodes if no local attribute exists
        for child in data.getchildren():
            for attr in [key for key in data.attrib.keys() if key != 'name' and not child.attrib.has_key(key)]:
                child.set(attr, data.get(attr))
        Bcfg2.Server.Plugin.LNode.__init__(self, data, plist, parent)
        for pkg in data.findall('./Package'):
            if pkg.attrib.has_key('name') and pkg.get('name') not in plist:
                plist.append(pkg.get('name'))
            if pkg.attrib.has_key('simplefile'):
                pkg.set('url', "%s/%s" % (pkg.get('uri'), pkg.get('simplefile')))
                self.contents[pkg.get('name')] = pkg.attrib
            else:
                if pkg.attrib.has_key('file'):
                    pkg.set('url', '%s/%s' % (pkg.get('uri'), pkg.get('file')))
                if self.splitters.has_key(pkg.get('type')):
                    mdata = self.splitters[pkg.get('type')].match(pkg.get('file'))
                    if not mdata:
                        syslog(LOG_ERR, "Pkgmgr: Failed to match pkg %s" % pkg.get('file'))
                        continue
                    pkgname = mdata.group('name')
                    self.contents[pkgname] = mdata.groupdict()
                    if pkg.attrib.get('file'):
                        self.contents[pkgname]['url'] = pkg.get('url')
                        self.contents[pkgname]['type'] = pkg.get('type')
                    if pkgname not in plist:
                        plist.append(pkgname)
                else:
                    self.contents[pkg.get('name')] = pkg.attrib

class PkgSrc(Bcfg2.Server.Plugin.XMLSrc):
    '''PkgSrc files contain a PNode hierarchy that returns matching package entries'''
    __node__ = PNode

class Pkgmgr(Bcfg2.Server.Plugin.XMLPrioDir):
    '''This is a generator that handles package assignments'''
    __name__ = 'Pkgmgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = PkgSrc
    __element__ = 'Package'
