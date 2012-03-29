import os
import sys
import time
import copy
import glob
import shutil
import lxml.etree
import Bcfg2.Logger
import Bcfg2.Server.Plugin
from Bcfg2.Bcfg2Py3k import ConfigParser, urlopen
from Bcfg2.Server.Plugins.Packages import Collection
from Bcfg2.Server.Plugins.Packages.PackagesSources import PackagesSources
from Bcfg2.Server.Plugins.Packages.PackagesConfig import PackagesConfig

class Packages(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.StructureValidator,
               Bcfg2.Server.Plugin.Generator,
               Bcfg2.Server.Plugin.Connector):
    name = 'Packages'
    conflicts = ['Pkgmgr']
    experimental = True
    __rmi__ = Bcfg2.Server.Plugin.Plugin.__rmi__ + ['Refresh', 'Reload']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.StructureValidator.__init__(self)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.Probing.__init__(self)

        self.sentinels = set()
        self.cachepath = os.path.join(self.data, 'cache')
        self.keypath = os.path.join(self.data, 'keys')
        if not os.path.exists(self.keypath):
            # create key directory if needed
            os.makedirs(self.keypath)

        # set up config files
        self.config = PackagesConfig(self)
        self.sources = PackagesSources(os.path.join(self.data, "sources.xml"),
                                       self.cachepath, core.fam, self,
                                       self.config)

    def toggle_debug(self):
        Bcfg2.Server.Plugin.Plugin.toggle_debug(self)
        self.sources.toggle_debug()

    @property
    def disableResolver(self):
        if self.disableMetaData:
            # disabling metadata without disabling the resolver Breaks
            # Things
            return True
        try:
            return not self.config.getboolean("global", "resolver")
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return False
        except ValueError:
            # for historical reasons we also accept "enabled" and
            # "disabled", which are not handled according to the
            # Python docs but appear to be handled properly by
            # ConfigParser in at least some versions
            return self.config.get("global", "resolver",
                                   default="enabled").lower() == "disabled"

    @property
    def disableMetaData(self):
        try:
            return not self.config.getboolean("global", "resolver")
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return False
        except ValueError:
            # for historical reasons we also accept "enabled" and
            # "disabled"
            return self.config.get("global", "metadata",
                                   default="enabled").lower() == "disabled"

    def create_config(self, entry, metadata):
        """ create yum/apt config for the specified host """
        attrib = {'encoding': 'ascii',
                  'owner': 'root',
                  'group': 'root',
                  'type': 'file',
                  'perms': '0644'}

        collection = self._get_collection(metadata)
        entry.text = collection.get_config()
        for (key, value) in list(attrib.items()):
            entry.attrib.__setitem__(key, value)

    def HandleEntry(self, entry, metadata):
        if entry.tag == 'Package':
            collection = self._get_collection(metadata)
            entry.set('version', self.config.get("global",
                                                 "version",
                                                 default="auto"))
            entry.set('type', collection.ptype)
        elif entry.tag == 'Path':
            if (entry.get("name") == self.config.get("global", "yum_config",
                                                     default="") or
                entry.get("name") == self.config.get("global", "apt_config",
                                                     default="")):
                self.create_config(entry, metadata)

    def HandlesEntry(self, entry, metadata):
        if entry.tag == 'Package':
            if self.config.getboolean("global", "magic_groups",
                                      default=True) == True:
                collection = self._get_collection(metadata)
                if collection.magic_groups_match():
                    return True
            else:
                return True
        elif entry.tag == 'Path':
            # managed entries for yum/apt configs
            if (entry.get("name") == self.config.get("global", "yum_config",
                                                     default="") or
                entry.get("name") == self.config.get("global", "apt_config",
                                                     default="")):
                return True
        return False

    def validate_structures(self, metadata, structures):
        '''Ensure client configurations include all needed prerequisites

        Arguments:
        metadata - client metadata instance
        structures - a list of structure-stage entry combinations
        '''
        collection = self._get_collection(metadata)
        indep = lxml.etree.Element('Independent')
        self._build_packages(metadata, indep, structures,
                             collection=collection)
        collection.build_extra_structures(indep)
        structures.append(indep)

    def _build_packages(self, metadata, independent, structures,
                        collection=None):
        """ build list of packages that need to be included in the
        specification by validate_structures() """
        if self.disableResolver:
            # Config requests no resolver
            return

        if collection is None:
            collection = self._get_collection(metadata)
        # initial is the set of packages that are explicitly specified
        # in the configuration
        initial = set()
        # base is the set of initial packages with groups expanded
        base = set()
        to_remove = []
        for struct in structures:
            for pkg in struct.xpath('//Package | //BoundPackage'):
                if pkg.get("name"):
                    initial.add(pkg.get("name"))
                elif pkg.get("group"):
                    try:
                        if pkg.get("type"):
                            gpkgs = collection.get_group(pkg.get("group"),
                                                         ptype=pkg.get("type"))
                        else:
                            gpkgs = collection.get_group(pkg.get("group"))
                        base.update(gpkgs)
                    except TypeError:
                        raise
                        self.logger.error("Could not resolve group %s" %
                                          pkg.get("group"))
                    to_remove.append(pkg)
                else:
                    self.logger.error("Packages: Malformed Package: %s" %
                                      lxml.etree.tostring(pkg))
        base.update(initial)
        for el in to_remove:
            el.getparent().remove(el)

        packages, unknown = collection.complete(base)
        if unknown:
            self.logger.info("Packages: Got %d unknown entries" % len(unknown))
            self.logger.info("Packages: %s" % list(unknown))
        newpkgs = list(packages.difference(initial))
        self.debug_log("Packages: %d initial, %d complete, %d new" %
                       (len(initial), len(packages), len(newpkgs)))
        newpkgs.sort()
        for pkg in newpkgs:
            lxml.etree.SubElement(independent, 'BoundPackage', name=pkg,
                                  version=self.config.get("global", "version",
                                                          default="auto"),
                                  type=collection.ptype, origin='Packages')

    def Refresh(self):
        '''Packages.Refresh() => True|False\nReload configuration
        specification and download sources\n'''
        self._load_config(force_update=True)
        return True

    def Reload(self):
        '''Packages.Refresh() => True|False\nReload configuration
        specification and sources\n'''
        self._load_config()
        return True

    def _load_config(self, force_update=False):
        '''
        Load the configuration data and setup sources

        Keyword args:
            force_update    Force downloading repo data
        '''
        self._load_sources(force_update)
        self._load_gpg_keys(force_update)

    def _load_sources(self, force_update):
        """ Load sources from the config """
        self.sentinels = set()
        cachefiles = set()

        for collection in list(Collection.collections.values()):
            cachefiles.update(collection.cachefiles)
            if not self.disableMetaData:
                collection.setup_data(force_update)
            self.sentinels.update(collection.basegroups)

        Collection.clear_cache()

        for source in self.sources:
            cachefiles.add(source.cachefile)
            if not self.disableMetaData:
                source.setup_data(force_update)

        for cfile in glob.glob(os.path.join(self.cachepath, "cache-*")):
            if cfile not in cachefiles:
                try:
                    if os.path.isdir(cfile):
                        shutil.rmtree(cfile)
                    else:
                        os.unlink(cfile)
                except OSError:
                    err = sys.exc_info()[1]
                    self.logger.error("Packages: Could not remove cache file "
                                      "%s: %s" % (cfile, err))

    def _load_gpg_keys(self, force_update):
        """ Load gpg keys from the config """
        keyfiles = []
        keys = []
        for source in self.sources:
            for key in source.gpgkeys:
                localfile = os.path.join(self.keypath,
                                         os.path.basename(key.rstrip("/")))
                if localfile not in keyfiles:
                    keyfiles.append(localfile)
                if ((force_update and key not in keys) or
                    not os.path.exists(localfile)):
                    self.logger.info("Packages: Downloading and parsing %s" % key)
                    response = urlopen(key)
                    open(localfile, 'w').write(response.read())
                    keys.append(key)

        for kfile in glob.glob(os.path.join(self.keypath, "*")):
            if kfile not in keyfiles:
                os.unlink(kfile)

    def _get_collection(self, metadata):
        return Collection.factory(metadata, self.sources, self.data,
                                  debug=self.debug_flag)

    def get_additional_data(self, metadata):
        collection = self._get_collection(metadata)
        return dict(sources=collection.get_additional_data())
