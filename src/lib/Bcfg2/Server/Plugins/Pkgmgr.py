'''This module implements a package management scheme for all images'''

import re
import sys
import logging
import lxml.etree
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugin import PluginExecutionError


logger = logging.getLogger('Bcfg2.Plugins.Pkgmgr')


class FuzzyDict(dict):
    fuzzy = re.compile(r'(?P<name>.*):(?P<alist>\S+(,\S+)*)')

    def __getitem__(self, key):
        if isinstance(key, str):
            mdata = self.fuzzy.match(key)
            if mdata:
                return dict.__getitem__(self, mdata.groupdict()['name'])
        else:
            print("got non-string key %s" % str(key))
        return dict.__getitem__(self, key)

    def __contains__(self, key):
        if isinstance(key, str):
            mdata = self.fuzzy.match(key)
            if mdata:
                return dict.__contains__(self, mdata.groupdict()['name'])
        else:
            print("got non-string key %s" % str(key))
        return dict.__contains__(self, key)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            if default:
                return default
            raise


class PNode(object):
    """PNode has a list of packages available at a
    particular group intersection.
    """
    splitters = dict(
        rpm=re.compile(
            r'^(.*/)?(?P<name>[\w\+\d\.]+(-[\w\+\d\.]+)*)-' +
            r'(?P<version>[\w\d\.]+-([\w\d\.]+))\.(?P<arch>\S+)\.rpm$'),
        encap=re.compile(
            r'^(?P<name>[\w-]+)-(?P<version>[\w\d\.+-]+).encap.*$'))
    raw = dict(
        Client="lambda m, e:'%(name)s' == m.hostname and predicate(m, e)",
        Group="lambda m, e:'%(name)s' in m.groups and predicate(m, e)")
    nraw = dict(
        Client="lambda m, e:'%(name)s' != m.hostname and predicate(m, e)",
        Group="lambda m, e:'%(name)s' not in m.groups and predicate(m, e)")
    containers = ['Group', 'Client']
    ignore = ['Package']

    def __init__(self, data, pdict, parent=None):
        # copy local attributes to all child nodes if no local attribute exists
        if 'Package' not in pdict:
            pdict['Package'] = set()
        for child in data.getchildren():
            attrs = set(data.attrib.keys()).difference(
                child.attrib.keys() + ['name'])
            for attr in attrs:
                try:
                    child.set(attr, data.get(attr))
                except:
                    # don't fail on things like comments and other
                    # immutable elements
                    pass
        self.data = data
        self.contents = {}
        if parent is None:
            self.predicate = lambda m, e: True
        else:
            predicate = parent.predicate
            if data.get('negate', 'false').lower() == 'true':
                psrc = self.nraw
            else:
                psrc = self.raw
            if data.tag in list(psrc.keys()):
                self.predicate = eval(psrc[data.tag] %
                                      {'name': data.get('name')},
                                      {'predicate': predicate})
            else:
                raise PluginExecutionError("Unknown tag: %s" % data.tag)
        self.children = []
        self._load_children(data, pdict)

        if 'Package' not in self.contents:
            self.contents['Package'] = FuzzyDict()
        for pkg in data.findall('./Package'):
            if ('name' in pkg.attrib and
                    pkg.get('name') not in pdict['Package']):
                pdict['Package'].add(pkg.get('name'))
            if pkg.get('name') is not None:
                self.contents['Package'][pkg.get('name')] = {}
                if pkg.getchildren():
                    self.contents['Package'][pkg.get('name')]['__children__'] \
                        = pkg.getchildren()
            if 'simplefile' in pkg.attrib:
                pkg.set('url',
                        "%s/%s" % (pkg.get('uri'), pkg.get('simplefile')))
                self.contents['Package'][pkg.get('name')].update(pkg.attrib)
            else:
                if 'file' in pkg.attrib:
                    if 'multiarch' in pkg.attrib:
                        archs = pkg.get('multiarch').split()
                        srcs = pkg.get('srcs', pkg.get('multiarch')).split()
                        url = ' '.join(
                            ["%s/%s" % (pkg.get('uri'),
                                        pkg.get('file') % {'src': srcs[idx],
                                                           'arch': archs[idx]})
                             for idx in range(len(archs))])
                        pkg.set('url', url)
                    else:
                        pkg.set('url', '%s/%s' % (pkg.get('uri'),
                                                  pkg.get('file')))
                if (pkg.get('type') in self.splitters and
                        pkg.get('file') is not None):
                    mdata = \
                        self.splitters[pkg.get('type')].match(pkg.get('file'))
                    if not mdata:
                        logger.error("Failed to match pkg %s" %
                                     pkg.get('file'))
                        continue
                    pkgname = mdata.group('name')
                    self.contents['Package'][pkgname] = mdata.groupdict()
                    self.contents['Package'][pkgname].update(pkg.attrib)
                    if pkg.attrib.get('file'):
                        self.contents['Package'][pkgname]['url'] = \
                            pkg.get('url')
                        self.contents['Package'][pkgname]['type'] = \
                            pkg.get('type')
                        if pkg.get('verify'):
                            self.contents['Package'][pkgname]['verify'] = \
                                pkg.get('verify')
                        if pkg.get('multiarch'):
                            self.contents['Package'][pkgname]['multiarch'] = \
                                pkg.get('multiarch')
                    if pkgname not in pdict['Package']:
                        pdict['Package'].add(pkgname)
                    if pkg.getchildren():
                        self.contents['Package'][pkgname]['__children__'] = \
                            pkg.getchildren()
                else:
                    self.contents['Package'][pkg.get('name')].update(
                        pkg.attrib)

    def _load_children(self, data, idict):
        """ load children """
        for item in data.getchildren():
            if item.tag in self.ignore:
                continue
            elif item.tag in self.containers:
                self.children.append(self.__class__(item, idict, self))
            else:
                try:
                    self.contents[item.tag][item.get('name')] = \
                        dict(item.attrib)
                except KeyError:
                    self.contents[item.tag] = \
                        {item.get('name'): dict(item.attrib)}
                if item.text:
                    self.contents[item.tag][item.get('name')]['__text__'] = \
                        item.text
                if item.getchildren():
                    self.contents[item.tag][item.get('name')]['__children__'] \
                        = item.getchildren()
                try:
                    idict[item.tag].append(item.get('name'))
                except KeyError:
                    idict[item.tag] = [item.get('name')]

    def Match(self, metadata, data, entry=lxml.etree.Element("None")):
        """Return a dictionary of package mappings."""
        if self.predicate(metadata, entry):
            for key in self.contents:
                data.setdefault(key, FuzzyDict).update(self.contents[key])
            for child in self.children:
                child.Match(metadata, data)


class PkgSrc(Bcfg2.Server.Plugin.XMLFileBacked):
    """ XMLSrc files contain a
    :class:`Bcfg2.Server.Plugin.helpers.INode` hierarchy that returns
    matching entries. XMLSrc objects are deprecated and
    :class:`Bcfg2.Server.Plugin.helpers.StructFile` should be
    preferred where possible."""
    __node__ = PNode
    __cacheobj__ = FuzzyDict
    __priority_required__ = True

    def __init__(self, filename, should_monitor=False):
        Bcfg2.Server.Plugin.XMLFileBacked.__init__(self, filename,
                                                   should_monitor)
        self.items = {}
        self.cache = None
        self.pnode = None
        self.priority = -1

    def HandleEvent(self, _=None):
        """Read file upon update."""
        try:
            data = open(self.name).read()
        except IOError:
            msg = "Failed to read file %s: %s" % (self.name, sys.exc_info()[1])
            logger.error(msg)
            raise PluginExecutionError(msg)
        self.items = {}
        try:
            xdata = lxml.etree.XML(data, parser=Bcfg2.Server.XMLParser)
        except lxml.etree.XMLSyntaxError:
            msg = "Failed to parse file %s: %s" % (self.name,
                                                   sys.exc_info()[1])
            logger.error(msg)
            raise PluginExecutionError(msg)
        self.pnode = self.__node__(xdata, self.items)
        self.cache = None
        try:
            self.priority = int(xdata.get('priority'))
        except (ValueError, TypeError):
            if self.__priority_required__:
                msg = "Got bogus priority %s for file %s" % \
                    (xdata.get('priority'), self.name)
                logger.error(msg)
                raise PluginExecutionError(msg)

        del xdata, data

    def Cache(self, metadata):
        """Build a package dict for a given host."""
        if self.cache is None or self.cache[0] != metadata:
            cache = (metadata, self.__cacheobj__())
            if self.pnode is None:
                logger.error("Cache method called early for %s; "
                             "forcing data load" % self.name)
                self.HandleEvent()
                return
            self.pnode.Match(metadata, cache[1])
            self.cache = cache

    def __str__(self):
        return str(self.items)


class Pkgmgr(Bcfg2.Server.Plugin.PrioDir):
    """This is a generator that handles package assignments."""
    name = 'Pkgmgr'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = PkgSrc
    __element__ = 'Package'

    def HandleEvent(self, event):
        '''Handle events and update dispatch table'''
        Bcfg2.Server.Plugin.XMLDirectoryBacked.HandleEvent(self, event)
        for src in list(self.entries.values()):
            for itype, children in list(src.items.items()):
                for child in children:
                    try:
                        self.Entries[itype][child] = self.BindEntry
                    except KeyError:
                        self.Entries[itype] = FuzzyDict([(child,
                                                          self.BindEntry)])

    def BindEntry(self, entry, metadata):
        """Bind data for entry, and remove instances that are not requested."""
        pname = entry.get('name')
        Bcfg2.Server.Plugin.PrioDir.BindEntry(self, entry, metadata)
        if entry.findall('Instance'):
            mdata = FuzzyDict.fuzzy.match(pname)
            if mdata:
                arches = mdata.group('alist').split(',')
                for inst in entry.findall('Instance'):
                    if inst.get('arch') not in arches:
                        entry.remove(inst)

    def HandlesEntry(self, entry, metadata):
        return (
            entry.tag == 'Package' and
            entry.get('name').split(':')[0] in self.Entries['Package'].keys())

    def HandleEntry(self, entry, metadata):
        self.BindEntry(entry, metadata)
