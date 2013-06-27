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


class DepSolver(object):
    """ Yum dependency solver """

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


class HelperSubcommand(Bcfg2.Options.Subcommand):
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
        self.depsolver = DepSolver(Bcfg2.Options.setup.yum_config,
                                   self.verbosity)

    def run(self, setup):
        try:
            data = json.loads(sys.stdin.read())
        except:  # pylint: disable=W0702
            self.logger.error("Unexpected error decoding JSON input: %s" %
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
        raise NotImplementedError


class Clean(HelperSubcommand):
    fallback = False
    accept_input = False

    def _run(self, setup, data):  # pylint: disable=W0613
        self.depsolver.clean_cache()
        return True


class Complete(HelperSubcommand):
    fallback = dict(packages=[], unknown=[])

    def _run(self, _, data):
        self.depsolver.groups = data['groups']
        self.fallback['unknown'] = data['packages']
        (packages, unknown) = self.depsolver.complete(
            [pkg_to_tuple(p) for p in data['packages']])
        return dict(packages=list(packages), unknown=list(unknown))


class GetGroups(HelperSubcommand):
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


Get_Groups = GetGroups


class CLI(Bcfg2.Options.CommandRegistry):
    options = [
        Bcfg2.Options.PathOption(
            "-c", "--yum-config", help="Yum config file"),
        Bcfg2.Options.PositionalArgument(
            "command", help="Yum helper command",
            choices=['clean', 'complete', 'get_groups'])]

    def __init__(self):
        Bcfg2.Options.CommandRegistry.__init__(self)
        Bcfg2.Options.register_commands(self.__class__, globals().values(),
                                        parent=HelperSubcommand)
        parser = Bcfg2.Options.get_parser("Bcfg2 yum helper",
                                          components=[self])
        parser.parse()
        self.logger = logging.getLogger(parser.prog)

    def run(self):
        if not os.path.exists(Bcfg2.Options.setup.yum_config):
            self.logger.error("Config file %s not found" %
                              Bcfg2.Options.setup.yum_config)
            return 1
        return self.runcommand()
