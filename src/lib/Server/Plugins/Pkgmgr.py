'''This module implements a package management scheme for all images'''
__revision__ = '$Revision$'

import logging, re, Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.Pkgmgr')

class PNode(Bcfg2.Server.Plugin.INode):
    '''PNode has a list of packages available at a particular group intersection'''
    splitters = {'rpm':re.compile('^(.*/)?(?P<name>[\w\+\d\.]+(-[\w\+\d\.]+)*)-' + \
                                  '(?P<version>[\w\d\.]+-([\w\d\.]+))\.(?P<arch>\S+)\.rpm$'),
                 'encap':re.compile('^(?P<name>\w+)-(?P<version>[\w\d\.-]+).encap.*$')}
    ignore = ['Package']
    
    def __init__(self, data, pdict, parent=None):
        # copy local attributes to all child nodes if no local attribute exists
        if not pdict.has_key('Package'):
            pdict['Package'] = []
        for child in data.getchildren():
            for attr in [key for key in data.attrib.keys() if key != 'name' and not child.attrib.has_key(key)]:
                child.set(attr, data.get(attr))
        Bcfg2.Server.Plugin.INode.__init__(self, data, pdict, parent)
        if not self.contents.has_key('Package'):
            self.contents['Package'] = {}
        for pkg in data.findall('./Package'):
            if pkg.attrib.has_key('name') and pkg.get('name') not in pdict['Package']:
                pdict['Package'].append(pkg.get('name'))
            if pkg.attrib.has_key('simplefile'):
                pkg.set('url', "%s/%s" % (pkg.get('uri'), pkg.get('simplefile')))
                self.contents['Package'][pkg.get('name')] = pkg.attrib
            else:
                if pkg.attrib.has_key('file'):
                    if pkg.attrib.has_key('multiarch'):
                        archs = pkg.get('multiarch').split()
                        srcs = pkg.get('srcs', pkg.get('multiarch')).split()
                        url = ' '.join(["%s/%s" % (pkg.get('uri'), pkg.get('file') % (srcs[idx], archs[idx]))
                                        for idx in range(len(archs))])
                        pkg.set('url', url)
                    else:
                        pkg.set('url', '%s/%s' % (pkg.get('uri'), pkg.get('file')))
                if self.splitters.has_key(pkg.get('type')) and pkg.get('file') != None:
                    mdata = self.splitters[pkg.get('type')].match(pkg.get('file'))
                    if not mdata:
                        logger.error("Failed to match pkg %s" % pkg.get('file'))
                        continue
                    pkgname = mdata.group('name')
                    self.contents['Package'][pkgname] = mdata.groupdict()
                    if pkg.attrib.get('file'):
                        self.contents['Package'][pkgname]['url'] = pkg.get('url')
                        self.contents['Package'][pkgname]['type'] = pkg.get('type')
                        if pkg.get('verify'):
                            self.contents['Package'][pkgname]['verify'] = pkg.get('verify')
                        if pkg.get('multiarch'):
                            self.contents['Package'][pkgname]['multiarch'] = pkg.get('multiarch')
                    if pkgname not in pdict['Package']:
                        pdict['Package'].append(pkgname)
                else:
                    self.contents['Package'][pkg.get('name')] = pkg.attrib

class PkgSrc(Bcfg2.Server.Plugin.XMLSrc):
    '''PkgSrc files contain a PNode hierarchy that returns matching package entries'''
    __node__ = PNode

class Pkgmgr(Bcfg2.Server.Plugin.PrioDir):
    '''This is a generator that handles package assignments'''
    __name__ = 'Pkgmgr'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = PkgSrc
    __element__ = 'Package'
