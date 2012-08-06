import sys
import copy
import logging
import Bcfg2.Server.Plugin

logger = logging.getLogger(__name__)

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

# we have to cache Collection objects so that calling Packages.Refresh
# or .Reload can tell the collection objects to clean up their cache,
# but we don't actually use the cache to return a Collection object
# when one is requested, because that prevents new machines from
# working, since a Collection object gets created by
# get_additional_data(), which is called for all clients at server
# startup.  (It would also prevent machines that change groups from
# working properly; e.g., if you reinstall a machine with a new OS,
# then returning a cached Collection object would give the wrong
# sources to that client.)  These are keyed by the collection
# cachekey, a unique key identifying the collection by its _config_,
# which could be shared among multiple clients.
collections = dict()

# cache mapping of hostname -> collection cachekey.  this _is_ used to
# return a Collection object when one is requested, so each entry is
# very short-lived -- it's purged at the end of each client run.
clients = dict()

class Collection(Bcfg2.Server.Plugin.Debuggable):
    def __init__(self, metadata, sources, basepath, debug=False):
        """ don't call this directly; use the factory function """
        Bcfg2.Server.Plugin.Debuggable.__init__(self)
        self.debug_flag = debug
        self.metadata = metadata
        self.sources = sources
        self.basepath = basepath
        self.virt_pkgs = dict()

        try:
            self.setup = sources[0].setup
            self.cachepath = sources[0].basepath
            self.ptype = sources[0].ptype
        except IndexError:
            self.setup = None
            self.cachepath = None
            self.ptype = "unknown"

        self.cachefile = None

    @property
    def cachekey(self):
        return md5(self.sourcelist().encode(self.setup['encoding'])).hexdigest()

    def get_config(self):
        self.logger.error("Packages: Cannot generate config for host %s with "
                          "no sources or multiple source types" %
                          self.metadata.hostname)
        return ""

    def sourcelist(self):
        srcs = []
        for source in self.sources:
            # get_urls() loads url_map as a side-effect
            source.get_urls()
            for url_map in source.url_map:
                reponame = source.get_repo_name(url_map)
                srcs.append("Name: %s" % reponame)
                srcs.append("  Type: %s" % source.ptype)
                if url_map['url']:
                    srcs.append("  URL: %s" % url_map['url'])
                elif url_map['rawurl']:
                    srcs.append("  RAWURL: %s" % url_map['rawurl'])
                if source.gpgkeys:
                    srcs.append("  GPG Key(s): %s" % ", ".join(source.gpgkeys))
                else:
                    srcs.append("  GPG Key(s): None")
                if len(source.blacklist):
                    srcs.append("  Blacklist: %s" % ", ".join(source.blacklist))
                if len(source.whitelist):
                    srcs.append("  Whitelist: %s" % ", ".join(source.whitelist))
                srcs.append("")
        return "\n".join(srcs)

    def get_relevant_groups(self):
        groups = []
        for source in self.sources:
            groups.extend(source.get_relevant_groups(self.metadata))
        return sorted(list(set(groups)))

    @property
    def basegroups(self):
        groups = set()
        for source in self.sources:
            groups.update(source.basegroups)
        return list(groups)

    @property
    def cachefiles(self):
        cachefiles = set([self.cachefile])
        for source in self.sources:
            cachefiles.add(source.cachefile)
        return list(cachefiles)

    def get_groups(self, grouplist):
        """ provided since some backends may be able to query multiple
        groups at once faster than serially """
        rv = dict()
        for group, ptype in grouplist:
            rv[group] = self.get_group(group, ptype)
        return rv

    def get_group(self, group, ptype=None):
        for source in self.sources:
            pkgs = source.get_group(self.metadata, group, ptype=ptype)
            if pkgs:
                return pkgs
        self.logger.warning("Packages: '%s' is not a valid group" % group)
        return []

    def is_package(self, package):
        for source in self.sources:
            if source.is_package(self.metadata, package):
                return True
        return False

    def is_virtual_package(self, package):
        for source in self.sources:
            if source.is_virtual_package(self.metadata, package):
                return True
        return False

    def get_deps(self, package):
        for source in self.sources:
            if source.is_package(self.metadata, package):
                return source.get_deps(self.metadata, package)
        return []

    def get_essential(self):
        essential = set()
        for source in self.sources:
            essential |= source.essentialpkgs
        return essential

    def get_provides(self, package):
        for source in self.sources:
            providers = source.get_provides(self.metadata, package)
            if providers:
                return providers
        return []

    def get_vpkgs(self):
        """ get virtual packages """
        vpkgs = dict()
        for source in self.sources:
            s_vpkgs = source.get_vpkgs(self.metadata)
            for name, prov_set in list(s_vpkgs.items()):
                if name not in vpkgs:
                    vpkgs[name] = set(prov_set)
                else:
                    vpkgs[name].update(prov_set)
        return vpkgs

    def filter_unknown(self, unknown):
        for source in self.sources:
            source.filter_unknown(unknown)

    def magic_groups_match(self):
        for source in self.sources:
            if source.magic_groups_match(self.metadata):
                return True

    def build_extra_structures(self, independent):
        pass

    def get_additional_data(self):
        sdata = []
        for source in self.sources:
            sdata.extend(copy.deepcopy(source.url_map))
        return sdata

    def setup_data(self, force_update=False):
        """ do any collection-level data setup tasks """
        pass

    def packages_from_entry(self, entry):
        """ given a Package or BoundPackage entry, get a list of the
        package(s) described by it in a format appropriate for passing
        to complete().  by default, that's just the name; only the Yum
        backend supports getting versions"""
        return [entry.get("name")]

    def packages_to_entry(self, pkglist, entry):
        for pkg in pkglist:
            lxml.etree.SubElement(entry, 'BoundPackage', name=pkg,
                                  version=self.setup.cfp.get("packages",
                                                             "version",
                                                             default="auto"),
                                  type=self.ptype, origin='Packages')

    def get_new_packages(self, initial, complete):
        """ compute the difference between the complete package list
        and the initial package list.  this is necessary because the
        format may be different between the two lists due to
        packages_{to,from}_entry() """
        return list(complete.difference(initial))

    def complete(self, packagelist):
        '''Build the transitive closure of all package dependencies

        Arguments:
        packageslist - set of package names
        returns => (set(packages), set(unsatisfied requirements))
        '''

        # setup vpkg cache
        pgrps = tuple(self.get_relevant_groups())
        if pgrps not in self.virt_pkgs:
            self.virt_pkgs[pgrps] = self.get_vpkgs()
        vpkg_cache = self.virt_pkgs[pgrps]

        # unclassified is set of unsatisfied requirements (may be pkg
        # for vpkg)
        unclassified = set(packagelist)
        vpkgs = set()
        both = set()
        pkgs = set(packagelist)

        packages = set()
        examined = set()
        unknown = set()

        final_pass = False
        really_done = False
        # do while unclassified or vpkgs or both or pkgs
        while unclassified or pkgs or both or final_pass:
            if really_done:
                break
            if len(unclassified) + len(pkgs) + len(both) == 0:
                # one more pass then exit
                really_done = True

            while unclassified:
                current = unclassified.pop()
                examined.add(current)
                is_pkg = False
                if self.is_package(current):
                    is_pkg = True

                is_vpkg = current in vpkg_cache

                if is_pkg and is_vpkg:
                    both.add(current)
                elif is_pkg and not is_vpkg:
                    pkgs.add(current)
                elif is_vpkg and not is_pkg:
                    vpkgs.add(current)
                elif not is_vpkg and not is_pkg:
                    unknown.add(current)

            while pkgs:
                # direct packages; current can be added, and all deps
                # should be resolved
                current = pkgs.pop()
                self.debug_log("Packages: handling package requirement %s" %
                               current)
                packages.add(current)
                deps = self.get_deps(current)
                newdeps = set(deps).difference(examined)
                if newdeps:
                    self.debug_log("Packages: Package %s added requirements %s"
                                   % (current, newdeps))
                unclassified.update(newdeps)

            satisfied_vpkgs = set()
            for current in vpkgs:
                # virtual dependencies, satisfied if one of N in the
                # config, or can be forced if only one provider
                if len(vpkg_cache[current]) == 1:
                    self.debug_log("Packages: requirement %s satisfied by %s" %
                                   (current, vpkg_cache[current]))
                    unclassified.update(vpkg_cache[current].difference(examined))
                    satisfied_vpkgs.add(current)
                else:
                    satisfiers = [item for item in vpkg_cache[current]
                                  if item in packages]
                    self.debug_log("Packages: requirement %s satisfied by %s" %
                                   (current, satisfiers))
                    satisfied_vpkgs.add(current)
            vpkgs.difference_update(satisfied_vpkgs)

            satisfied_both = set()
            for current in both:
                # packages that are both have virtual providers as
                # well as a package with that name. allow use of virt
                # through explicit specification, then fall back to
                # forcing current on last pass
                satisfiers = [item for item in vpkg_cache[current]
                              if item in packages]
                if satisfiers:
                    self.debug_log("Packages: requirement %s satisfied by %s" %
                                   (current, satisfiers))
                    satisfied_both.add(current)
                elif current in packagelist or final_pass:
                    pkgs.add(current)
                    satisfied_both.add(current)
            both.difference_update(satisfied_both)

            if len(unclassified) + len(pkgs) == 0:
                final_pass = True
            else:
                final_pass = False

            self.filter_unknown(unknown)

        return packages, unknown

    def __len__(self):
        return len(self.sources)

    def __getitem__(self, item):
        return self.sources[item]

    def __setitem__(self, item, value):
        self.sources[item] = value

    def __delitem__(self, item):
        del self.sources[item]

    def append(self, item):
        self.sources.append(item)

    def count(self):
        return self.sources.count()

    def index(self, item):
        return self.sources.index(item)

    def extend(self, items):
        self.sources.extend(items)

    def insert(self, index, item):
        self.sources.insert(index, item)

    def pop(self, index=None):
        self.sources.pop(index)

    def remove(self, item):
        self.sources.remove(item)

    def sort(self, cmp=None, key=None, reverse=False):
        self.sources.sort(cmp, key, reverse)

def get_collection_class(source_type):
    modname = "Bcfg2.Server.Plugins.Packages.%s" % source_type.title()
    
    try:
        module = sys.modules[modname]
    except KeyError:
        try:
            module = __import__(modname).Server.Plugins.Packages
        except ImportError:
            msg = "Packages: Unknown source type %s" % source_type
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
    
    try:
        cclass = getattr(module, source_type.title() + "Collection")
    except AttributeError:
        msg = "Packages: No collection class found for %s sources" % source_type
        logger.error(msg)
        raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
    
    return cclass

def clear_cache():
    global collections
    global clients
    collections = dict()
    clients = dict()

def factory(metadata, sources, basepath, debug=False):
    global collections

    if not sources.loaded:
        # if sources.xml has not received a FAM event yet, defer;
        # instantiate a dummy Collection object
        return Collection(metadata, [], basepath)

    if metadata.hostname in clients:
        return collections[clients[metadata.hostname]]

    sclasses = set()
    relevant = list()

    for source in sources:
        if source.applies(metadata):
            relevant.append(source)
            sclasses.update([source.__class__])

    if len(sclasses) > 1:
        logger.warning("Packages: Multiple source types found for %s: %s" %
                       ",".join([s.__name__ for s in sclasses]))
        cclass = Collection
    elif len(sclasses) == 0:
        logger.error("Packages: No sources found for %s" % metadata.hostname)
        cclass = Collection
    else:
        cclass = get_collection_class(sclasses.pop().__name__.replace("Source",
                                                                      ""))

    if debug:
        logger.error("Packages: Using %s for Collection of sources for %s" %
                     (cclass.__name__, metadata.hostname))

    collection = cclass(metadata, relevant, basepath, debug=debug)
    ckey = collection.cachekey
    clients[metadata.hostname] = ckey
    collections[ckey] = collection
    return collection
