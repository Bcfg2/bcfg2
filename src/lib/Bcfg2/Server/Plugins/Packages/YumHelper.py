""" Libraries for bcfg2-yum-helper plugin, used if yum library support
is enabled.  The yum libs have horrific memory leaks, so apparently
the right way to get around that in long-running processes it to have
a short-lived helper.  No, seriously -- check out the yum-updatesd
code.  It's pure madness. """

import os
import sys
import yum
import logging
import Bcfg2.Options
import Bcfg2.Logger
from Bcfg2.Compat import wraps
from lockfile import FileLock, LockTimeout
try:
    import json
except ImportError:
    import simplejson as json


def pkg_to_tuple(package):
    """ json doesn't distinguish between tuples and lists, but yum
    does, so we convert a package in list format to one in tuple
    format """
    if isinstance(package, list):
        return tuple(package)
    else:
        return package


def pkgtup_to_string(package):
    """ given a package tuple, return a human-readable string
    describing the package """
    if package[3] in ['auto', 'any']:
        return package[0]

    rv = [package[0], "-"]
    if package[2]:
        rv.extend([package[2], ':'])
    rv.extend([package[3], '-', package[4]])
    if package[1]:
        rv.extend(['.', package[1]])
    return ''.join(str(e) for e in rv)


class YumHelper(object):
    """ Yum helper base object """

    def __init__(self, cfgfile, verbose=1):
        self.cfgfile = cfgfile
        self.yumbase = yum.YumBase()
        # pylint: disable=E1121,W0212
        try:
            self.yumbase.preconf.debuglevel = verbose
            self.yumbase.preconf.fn = cfgfile
            self.yumbase._getConfig()
        except AttributeError:
            self.yumbase._getConfig(cfgfile, debuglevel=verbose)
        # pylint: enable=E1121,W0212
        self.logger = logging.getLogger(self.__class__.__name__)


class DepSolver(YumHelper):
    """ Yum dependency solver.  This is used for operations that only
    read from the yum cache, and thus operates in cacheonly mode. """

    def __init__(self, cfgfile, verbose=1):
        YumHelper.__init__(self, cfgfile, verbose=verbose)
        # internally, yum uses an integer, not a boolean, for conf.cache
        self.yumbase.conf.cache = 1
        self._groups = None

    def get_groups(self):
        """ getter for the groups property """
        if self._groups is not None:
            return self._groups
        else:
            return ["noarch"]

    def set_groups(self, groups):
        """ setter for the groups property """
        self._groups = set(groups).union(["noarch"])

    groups = property(get_groups, set_groups)

    def get_package_object(self, pkgtup, silent=False):
        """ given a package tuple, get a yum package object """
        try:
            matches = yum.packageSack.packagesNewestByName(
                self.yumbase.pkgSack.searchPkgTuple(pkgtup))
        except yum.Errors.PackageSackError:
            if not silent:
                self.logger.warning("Package '%s' not found" %
                                    self.get_package_name(pkgtup))
            matches = []
        except yum.Errors.RepoError:
            err = sys.exc_info()[1]
            self.logger.error("Temporary failure loading metadata for %s: %s" %
                              (self.get_package_name(pkgtup), err))
            matches = []

        pkgs = self._filter_arch(matches)
        if pkgs:
            return pkgs[0]
        else:
            return None

    def get_group(self, group, ptype="default"):
        """ Resolve a package group name into a list of packages """
        if group.startswith("@"):
            group = group[1:]

        try:
            if self.yumbase.comps.has_group(group):
                group = self.yumbase.comps.return_group(group)
            else:
                self.logger.error("%s is not a valid group" % group)
                return []
        except yum.Errors.GroupsError:
            err = sys.exc_info()[1]
            self.logger.warning(err)
            return []

        if ptype == "default":
            return [p
                    for p, d in list(group.default_packages.items())
                    if d]
        elif ptype == "mandatory":
            return [p
                    for p, m in list(group.mandatory_packages.items())
                    if m]
        elif ptype == "optional" or ptype == "all":
            return group.packages
        else:
            self.logger.warning("Unknown group package type '%s'" % ptype)
            return []

    def _filter_arch(self, packages):
        """ filter packages in the given list that do not have an
        architecture in the list of groups for this client """
        matching = []
        for pkg in packages:
            if pkg.arch in self.groups:
                matching.append(pkg)
            else:
                self.logger.debug("%s has non-matching architecture (%s)" %
                                  (pkg, pkg.arch))
        if matching:
            return matching
        else:
            # no packages match architecture; we'll assume that the
            # user knows what s/he is doing and this is a multiarch
            # box.
            return packages

    def get_package_name(self, package):
        """ get the name of a package or virtual package from the
        internal representation used by this Collection class """
        if isinstance(package, tuple):
            if len(package) == 3:
                return yum.misc.prco_tuple_to_string(package)
            else:
                return pkgtup_to_string(package)
        else:
            return str(package)

    def complete(self, packagelist):
        """ resolve dependencies and generate a complete package list
        from the given list of initial packages """
        packages = set()
        unknown = set()
        for pkg in packagelist:
            if isinstance(pkg, tuple):
                pkgtup = pkg
            else:
                pkgtup = (pkg, None, None, None, None)
            pkgobj = self.get_package_object(pkgtup)
            if not pkgobj:
                self.logger.debug("Unknown package %s" %
                                  self.get_package_name(pkg))
                unknown.add(pkg)
            else:
                if self.yumbase.tsInfo.exists(pkgtup=pkgobj.pkgtup):
                    self.logger.debug("%s added to transaction multiple times"
                                      % pkgobj)
                else:
                    self.logger.debug("Adding %s to transaction" % pkgobj)
                    self.yumbase.tsInfo.addInstall(pkgobj)
        self.yumbase.resolveDeps()

        for txmbr in self.yumbase.tsInfo:
            packages.add(txmbr.pkgtup)
        return list(packages), list(unknown)


def acquire_lock(func):
    """ decorator for CacheManager methods that gets and release a
    lock while the method runs """
    @wraps(func)
    def inner(self, *args, **kwargs):
        """ Get and release a lock while running the function this
        wraps. """
        self.logger.debug("Acquiring lock at %s" % self.lockfile)
        while not self.lock.i_am_locking():
            try:
                self.lock.acquire(timeout=60)  # wait up to 60 seconds
            except LockTimeout:
                self.lock.break_lock()
                self.lock.acquire()
        try:
            func(self, *args, **kwargs)
        finally:
            self.lock.release()
            self.logger.debug("Released lock at %s" % self.lockfile)

    return inner


class CacheManager(YumHelper):
    """ Yum cache manager.  Unlike :class:`DepSolver`, this can write
    to the yum cache, and so is used for operations that muck with the
    cache.  (Technically, :func:`CacheManager.clean_cache` could be in
    either DepSolver or CacheManager, but for consistency I've put it
    here.) """

    def __init__(self, cfgfile, verbose=1):
        YumHelper.__init__(self, cfgfile, verbose=verbose)
        self.lockfile = \
            os.path.join(os.path.dirname(self.yumbase.conf.config_file_path),
                         "lock")
        self.lock = FileLock(self.lockfile)

    @acquire_lock
    def clean_cache(self):
        """ clean the yum cache """
        for mdtype in ["Headers", "Packages", "Sqlite", "Metadata",
                       "ExpireCache"]:
            # for reasons that are entirely obvious, all of the yum
            # API clean* methods return a tuple of 0 (zero, always
            # zero) and a list containing a single message about how
            # many files were deleted.  so useful.  thanks, yum.
            msg = getattr(self.yumbase, "clean%s" % mdtype)()[1][0]
            if not msg.startswith("0 "):
                self.logger.info(msg)

    @acquire_lock
    def populate_cache(self):
        """ populate the yum cache """
        for repo in self.yumbase.repos.findRepos('*'):
            repo.metadata_expire = 0
            repo.mdpolicy = "group:all"
        self.yumbase.doRepoSetup()
        self.yumbase.repos.doSetup()
        for repo in self.yumbase.repos.listEnabled():
            # this populates the cache as a side effect
            repo.repoXML  # pylint: disable=W0104
            try:
                repo.getGroups()
            except yum.Errors.RepoMDError:
                pass  # this repo has no groups
        self.yumbase.repos.populateSack(mdtype='metadata', cacheonly=1)
        self.yumbase.repos.populateSack(mdtype='filelists', cacheonly=1)
        self.yumbase.repos.populateSack(mdtype='otherdata', cacheonly=1)
        # this does something with the groups cache as a side effect
        self.yumbase.comps  # pylint: disable=W0104


class HelperSubcommand(Bcfg2.Options.Subcommand):
    """ Base class for all yum helper subcommands """

    # the value to JSON encode and print out if the command fails
    fallback = None

    # whether or not this command accepts input on stdin
    accept_input = True

    def __init__(self):
        Bcfg2.Options.Subcommand.__init__(self)
        self.verbosity = 0
        if Bcfg2.Options.setup.debug:
            self.verbosity = 5
        elif Bcfg2.Options.setup.verbose:
            self.verbosity = 1

    def run(self, setup):
        try:
            data = json.loads(sys.stdin.read())
        except ValueError:
            self.logger.error("Error decoding JSON input: %s" %
                              sys.exc_info()[1])
            print(json.dumps(self.fallback))
            return 2

        try:
            print(json.dumps(self._run(setup, data)))
        except:  # pylint: disable=W0702
            self.logger.error("Unexpected error running %s: %s" %
                              self.__class__.__name__.lower(),
                              sys.exc_info()[1], exc_info=1)
            print(json.dumps(self.fallback))
            return 2
        return 0

    def _run(self, setup, data):
        """ Actually run the command """
        raise NotImplementedError


class DepSolverSubcommand(HelperSubcommand):  # pylint: disable=W0223
    """ Base class for helper commands that use the depsolver (i.e.,
    only resolve dependencies, don't modify the cache) """

    def __init__(self):
        HelperSubcommand.__init__(self)
        self.depsolver = DepSolver(Bcfg2.Options.setup.yum_config,
                                   self.verbosity)


class CacheManagerSubcommand(HelperSubcommand):  # pylint: disable=W0223
    """ Base class for helper commands that use the cachemanager
    (i.e., modify the cache) """
    fallback = False
    accept_input = False

    def __init__(self):
        HelperSubcommand.__init__(self)
        self.cachemgr = CacheManager(Bcfg2.Options.setup.yum_config,
                                     self.verbosity)


class Clean(CacheManagerSubcommand):
    """ Clean the cache """
    def _run(self, setup, data):  # pylint: disable=W0613
        self.cachemgr.clean_cache()
        return True


class MakeCache(CacheManagerSubcommand):
    """ Update the on-disk cache """
    def _run(self, setup, data):  # pylint: disable=W0613
        self.cachemgr.populate_cache()
        return True


class Complete(DepSolverSubcommand):
    """ Given an initial set of packages, get a complete set of
    packages with all dependencies resolved """
    fallback = dict(packages=[], unknown=[])

    def _run(self, _, data):
        self.depsolver.groups = data['groups']
        self.fallback['unknown'] = data['packages']
        (packages, unknown) = self.depsolver.complete(
            [pkg_to_tuple(p) for p in data['packages']])
        return dict(packages=list(packages), unknown=list(unknown))


class GetGroups(DepSolverSubcommand):
    """ Resolve the given package groups """
    def _run(self, _, data):
        rv = dict()
        for gdata in data:
            if "type" in gdata:
                packages = self.depsolver.get_group(gdata['group'],
                                                    ptype=gdata['type'])
            else:
                packages = self.depsolver.get_group(gdata['group'])
            rv[gdata['group']] = list(packages)
        return rv


Get_Groups = GetGroups  # pylint: disable=C0103


class CLI(Bcfg2.Options.CommandRegistry):
    """ The bcfg2-yum-helper CLI """
    options = [
        Bcfg2.Options.PathOption(
            "-c", "--yum-config", help="Yum config file"),
        Bcfg2.Options.PositionalArgument(
            "command", help="Yum helper command",
            choices=['clean', 'complete', 'get_groups'])]

    def __init__(self):
        Bcfg2.Options.CommandRegistry.__init__(self)
        self.register_commands(globals().values(), parent=HelperSubcommand)
        parser = Bcfg2.Options.get_parser("Bcfg2 yum helper",
                                          components=[self])
        parser.add_options(self.subcommand_options)
        parser.parse()
        self.logger = logging.getLogger(parser.prog)

    def run(self):
        """ Run bcfg2-yum-helper """
        if not os.path.exists(Bcfg2.Options.setup.yum_config):
            self.logger.error("Config file %s not found" %
                              Bcfg2.Options.setup.yum_config)
            return 1
        return self.runcommand()
