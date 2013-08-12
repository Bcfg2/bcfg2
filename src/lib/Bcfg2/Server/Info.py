""" Subcommands and helpers for bcfg2-info """
# -*- coding: utf-8 -*-

import os
import sys
import cmd
import math
import time
import copy
import pipes
import fnmatch
import argparse
import operator
import lxml.etree
from code import InteractiveConsole
import Bcfg2.Logger
import Bcfg2.Options
import Bcfg2.Server.Core
import Bcfg2.Server.Plugin
import Bcfg2.Client.Tools.POSIX
from Bcfg2.Compat import any  # pylint: disable=W0622

try:
    try:
        import cProfile as profile
    except ImportError:
        import profile
    import pstats
    HAS_PROFILE = True
except ImportError:
    HAS_PROFILE = False


def print_tabular(rows):
    """Print data in tabular format."""
    cmax = tuple([max([len(str(row[index])) for row in rows]) + 1
                  for index in range(len(rows[0]))])
    fstring = (" %%-%ss |" * len(cmax)) % cmax
    fstring = ('|'.join([" %%-%ss "] * len(cmax))) % cmax
    print(fstring % rows[0])
    print((sum(cmax) + (len(cmax) * 2) + (len(cmax) - 1)) * '=')
    for row in rows[1:]:
        print(fstring % row)


def display_trace(trace):
    """ display statistics from a profile trace """
    stats = pstats.Stats(trace)
    stats.sort_stats('cumulative', 'calls', 'time')
    stats.print_stats(200)


def load_interpreters():
    """ Load a dict of available Python interpreters """
    interpreters = dict(python=lambda v: InteractiveConsole(v).interact())
    default = "python"
    try:
        import bpython.cli
        interpreters["bpython"] = lambda v: bpython.cli.main(args=[],
                                                             locals_=v)
        default = "bpython"
    except ImportError:
        pass

    try:
        # whether ipython is actually better than bpython is
        # up for debate, but this is the behavior that existed
        # before --interpreter was added, so we call IPython
        # better
        import IPython
        # pylint: disable=E1101
        if hasattr(IPython, "Shell"):
            interpreters["ipython"] = lambda v: \
                IPython.Shell.IPShell(argv=[], user_ns=v).mainloop()
            default = "ipython"
        elif hasattr(IPython, "embed"):
            interpreters["ipython"] = lambda v: IPython.embed(user_ns=v)
            default = "ipython"
        else:
            print("Unknown IPython API version")
        # pylint: enable=E1101
    except ImportError:
        pass

    return (interpreters, default)


class InfoCmd(Bcfg2.Options.Subcommand):  # pylint: disable=W0223
    """ Base class for bcfg2-info subcommands """

    def _expand_globs(self, globs, candidates):
        """ Given a list of globs, select the items from candidates
        that match the globs """
        # special cases to speed things up:
        if globs is None or '*' in globs:
            return candidates
        has_wildcards = False
        for glob in globs:
            # check if any wildcard characters are in the string
            if set('*?[]') & set(glob):
                has_wildcards = True
                break
        if not has_wildcards:
            return globs

        rv = set()
        cset = set(candidates)
        for glob in globs:
            rv.update(c for c in cset if fnmatch.fnmatch(c, glob))
            cset.difference_update(rv)
        return list(rv)

    def get_client_list(self, globs):
        """ given a list of host globs, get a list of clients that
        match them """
        return self._expand_globs(globs, self.core.metadata.clients)

    def get_group_list(self, globs):
        """ given a list of group glob, get a list of groups that
        match them"""
        # special cases to speed things up:
        return self._expand_globs(globs,
                                  list(self.core.metadata.groups.keys()))


class Help(InfoCmd, Bcfg2.Options.HelpCommand):
    """ Get help on a specific subcommand """
    def command_registry(self):
        return self.core.commands

    def run(self, setup):
        Bcfg2.Options.HelpCommand.run(self, setup)


class Debug(InfoCmd):
    """ Shell out to a Python interpreter """
    interpreters, default_interpreter = load_interpreters()
    options = [
        Bcfg2.Options.BooleanOption(
            "-n", "--non-interactive",
            help="Do not enter the interactive debugger"),
        Bcfg2.Options.PathOption(
            "-f", dest="cmd_list", type=argparse.FileType('r'),
            help="File containing commands to run"),
        Bcfg2.Options.Option(
            "--interpreter", cf=("bcfg2-info", "interpreter"),
            env="BCFG2_INFO_INTERPRETER",
            choices=interpreters.keys(), default=default_interpreter)]

    def run(self, setup):
        if setup.cmd_list:
            console = InteractiveConsole(locals())
            for command in setup.cmd_list.readlines():
                command = command.strip()
                if command:
                    console.push(command)
        if not setup.non_interactive:
            print("Dropping to interpreter; press ^D to resume")
            self.interpreters[setup.interpreter](self.core.get_locals())


class Build(InfoCmd):
    """ Build config for hostname, writing to filename """

    options = [Bcfg2.Options.PositionalArgument("hostname"),
               Bcfg2.Options.PositionalArgument("filename", nargs='?',
                                                default=sys.stdout,
                                                type=argparse.FileType('w'))]

    def run(self, setup):
        etree = lxml.etree.ElementTree(
            self.core.BuildConfiguration(setup.hostname))
        try:
            etree.write(
                setup.filename,
                encoding='UTF-8', xml_declaration=True,
                pretty_print=True)
        except IOError:
            err = sys.exc_info()[1]
            print("Failed to write %s: %s" % (setup.filename, err))


class Builddir(InfoCmd):
    """ Build config for hostname, writing separate files to directory
    """

    # don't try to isntall these types of entries
    blacklisted_types = ["nonexistent", "permissions"]

    options = Bcfg2.Client.Tools.POSIX.POSIX.options + [
        Bcfg2.Options.PositionalArgument("hostname"),
        Bcfg2.Options.PathOption("directory")]

    help = """Generates a config for client <hostname> and writes the
individual configuration files out separately in a tree under <output
dir>.  This only handles file entries, and does not respect 'owner' or
'group' attributes unless run as root. """

    def run(self, setup):
        setup.paranoid = False
        client_config = self.core.BuildConfiguration(setup.hostname)
        if client_config.tag == 'error':
            print("Building client configuration failed.")
            return 1

        entries = []
        for struct in client_config:
            for entry in struct:
                if (entry.tag == 'Path' and
                    entry.get("type") not in self.blacklisted_types):
                    failure = entry.get("failure")
                    if failure is not None:
                        print("Skipping entry %s:%s with bind failure: %s" %
                              (entry.tag, entry.get("name"), failure))
                        continue
                    entry.set('name',
                              os.path.join(setup.directory,
                                           entry.get('name').lstrip("/")))
                    entries.append(entry)

        Bcfg2.Client.Tools.POSIX.POSIX(client_config).Install(entries)


class Buildfile(InfoCmd):
    """ Build config file for hostname """

    options = [
        Bcfg2.Options.Option("-f", "--outfile", metavar="<path>",
                             type=argparse.FileType('w'), default=sys.stdout),
        Bcfg2.Options.PathOption("--altsrc"),
        Bcfg2.Options.PathOption("filename"),
        Bcfg2.Options.PositionalArgument("hostname")]

    def run(self, setup):
        entry = lxml.etree.Element('Path', name=setup.filename)
        if setup.altsrc:
            entry.set("altsrc", setup.altsrc)
        try:
            self.core.Bind(entry, self.core.build_metadata(setup.hostname))
        except:  # pylint: disable=W0702
            print("Failed to build entry %s for host %s" % (setup.filename,
                                                            setup.hostname))
            raise
        try:
            setup.outfile.write(
                lxml.etree.tostring(entry,
                                    xml_declaration=False).decode('UTF-8'))
            setup.outfile.write("\n")
        except IOError:
            err = sys.exc_info()[1]
            print("Failed to write %s: %s" % (setup.outfile.name, err))


class BuildAllMixin(object):
    """ InfoCmd mixin to make a version of an existing command that
    applies to multiple hosts"""

    directory_arg = Bcfg2.Options.PathOption("directory")
    hostname_arg = Bcfg2.Options.PositionalArgument("hostname", nargs='*',
                                                    default=[])
    options = [directory_arg, hostname_arg]

    @property
    def _parent(self):
        """ the parent command """
        for cls in self.__class__.__mro__:
            if (cls != InfoCmd and cls != self.__class__ and
                issubclass(cls, InfoCmd)):
                return cls

    def run(self, setup):
        """ Run the command """
        try:
            os.makedirs(setup.directory)
        except OSError:
            err = sys.exc_info()[1]
            if err.errno != 17:
                print("Could not create %s: %s" % (setup.directory, err))
                return 1
        clients = self.get_client_list(setup.hostname)
        for client in clients:
            csetup = self._get_setup(client, copy.copy(setup))
            csetup.hostname = client
            self._parent.run(self, csetup)  # pylint: disable=E1101

    def _get_setup(self, client, setup):
        """ This can be overridden by children to populate individual
        setup options on a per-client basis """
        raise NotImplementedError


class Buildallfile(Buildfile, BuildAllMixin):
    """ Build config file for all clients in directory """

    options = [BuildAllMixin.directory_arg,
               Bcfg2.Options.PathOption("--altsrc"),
               Bcfg2.Options.PathOption("filename"),
               BuildAllMixin.hostname_arg]

    def run(self, setup):
        BuildAllMixin.run(self, setup)

    def _get_setup(self, client, setup):
        setup.outfile = open(os.path.join(setup.directory, client), 'w')
        return setup


class Buildall(Build, BuildAllMixin):
    """ Build configs for all clients in directory """

    options = BuildAllMixin.options

    def run(self, setup):
        BuildAllMixin.run(self, setup)

    def _get_setup(self, client, setup):
        setup.filename = os.path.join(setup.directory, client + ".xml")
        return setup


class Buildbundle(InfoCmd):
    """ Render a templated bundle for hostname """

    options = [Bcfg2.Options.PositionalArgument("bundle"),
               Bcfg2.Options.PositionalArgument("hostname")]

    def run(self, setup):
        bundler = self.core.plugins['Bundler']
        bundle = None
        if setup.bundle in bundler.entries:
            bundle = bundler.entries[setup.bundle]
        elif not setup.bundle.endswith(".xml"):
            fname = setup.bundle + ".xml"
            if fname in bundler.entries:
                bundle = bundler.entries[bundle]
        if not bundle:
            print("No such bundle %s" % setup.bundle)
            return 1
        try:
            metadata = self.core.build_metadata(setup.hostname)
            print(lxml.etree.tostring(bundle.XMLMatch(metadata),
                                      xml_declaration=False,
                                      pretty_print=True).decode('UTF-8'))
        except:  # pylint: disable=W0702
            print("Failed to render bundle %s for host %s: %s" %
                  (setup.bundle, setup.hostname, sys.exc_info()[1]))
            raise


class Automatch(InfoCmd):
    """ Perform automatch on a Properties file """

    options = [
        Bcfg2.Options.BooleanOption(
            "-f", "--force",
            help="Force automatch even if it's disabled"),
        Bcfg2.Options.PositionalArgument("propertyfile"),
        Bcfg2.Options.PositionalArgument("hostname")]

    def run(self, setup):
        try:
            props = self.core.plugins['Properties']
        except KeyError:
            print("Properties plugin not enabled")
            return 1

        pfile = props.entries[setup.propertyfile]
        if (not Bcfg2.Options.setup.force and
            not Bcfg2.Options.setup.automatch and
            pfile.xdata.get("automatch", "false").lower() != "true"):
            print("Automatch not enabled on %s" % setup.propertyfile)
        else:
            metadata = self.core.build_metadata(setup.hostname)
            print(lxml.etree.tostring(pfile.XMLMatch(metadata),
                                      xml_declaration=False,
                                      pretty_print=True).decode('UTF-8'))


class ExpireCache(InfoCmd):
    """ Expire the metadata cache """

    options = [
        Bcfg2.Options.PositionalArgument(
            "hostname", nargs="*", default=[],
            help="Expire cache for the given host(s)")]

    def run(self, setup):
        if setup.clients:
            for client in self.get_client_list(setup.clients):
                self.core.expire_caches_by_type(Bcfg2.Server.Plugin.Metadata,
                                                key=client)
        else:
            self.core.expire_caches_by_type(Bcfg2.Server.Plugin.Metadata)


class Bundles(InfoCmd):
    """ Print out group/bundle info """

    options = [Bcfg2.Options.PositionalArgument("group", nargs='*')]

    def run(self, setup):
        data = [('Group', 'Bundles')]
        groups = self.get_group_list(setup.group)
        groups.sort()
        for group in groups:
            data.append((group,
                         ','.join(self.core.metadata.groups[group][0])))
        print_tabular(data)


class Clients(InfoCmd):
    """ Print out client/profile info """

    options = [Bcfg2.Options.PositionalArgument("hostname", nargs='*',
                                                default=[])]

    def run(self, setup):
        data = [('Client', 'Profile')]
        for client in sorted(self.get_client_list(setup.hostname)):
            imd = self.core.metadata.get_initial_metadata(client)
            data.append((client, imd.profile))
        print_tabular(data)


class Config(InfoCmd):
    """ Print out the current configuration of Bcfg2"""

    options = [
        Bcfg2.Options.BooleanOption(
            "--raw",
            help="Produce more accurate but less readable raw output")]

    def run(self, setup):
        parser = Bcfg2.Options.get_parser()
        data = [('Description', 'Value')]
        for option in parser.option_list:
            if hasattr(setup, option.dest):
                value = getattr(setup, option.dest)
                if any(issubclass(a.__class__,
                                  Bcfg2.Options.ComponentAction)
                       for a in option.actions.values()):
                    if not setup.raw:
                        try:
                            if option.action.islist:
                                value = [v.__name__ for v in value]
                            else:
                                value = value.__name__
                        except AttributeError:
                            # just use the value as-is
                            pass
                if setup.raw:
                    value = repr(value)
                data.append((getattr(option, "help", option.dest), value))
        print_tabular(data)


class Probes(InfoCmd):
    """ Get probes for the given host """

    options = [
        Bcfg2.Options.BooleanOption("-p", "--pretty",
                                    help="Human-readable output"),
        Bcfg2.Options.PositionalArgument("hostname")]

    def run(self, setup):
        if setup.pretty:
            probes = []
        else:
            probes = lxml.etree.Element('probes')
        metadata = self.core.build_metadata(setup.hostname)
        for plugin in self.core.plugins_by_type(Bcfg2.Server.Plugin.Probing):
            for probe in plugin.GetProbes(metadata):
                probes.append(probe)
        if setup.pretty:
            for probe in probes:
                pname = probe.get("name")
                print("=" * (len(pname) + 2))
                print(" %s" % pname)
                print("=" * (len(pname) + 2))
                print("")
                print(probe.text)
                print("")
        else:
            print(lxml.etree.tostring(probes, xml_declaration=False,
                                      pretty_print=True).decode('UTF-8'))


class Showentries(InfoCmd):
    """ Show abstract configuration entries for a given host """

    options = [Bcfg2.Options.PositionalArgument("hostname"),
               Bcfg2.Options.PositionalArgument("type", nargs='?')]

    def run(self, setup):
        try:
            metadata = self.core.build_metadata(setup.hostname)
        except Bcfg2.Server.Plugin.MetadataConsistencyError:
            print("Unable to build metadata for %s: %s" % (setup.hostname,
                                                           sys.exc_info()[1]))
        structures = self.core.GetStructures(metadata)
        output = [('Entry Type', 'Name')]
        etypes = None
        if setup.type:
            etypes = [setup.type, "Bound%s" % setup.type]
        for item in structures:
            output.extend((child.tag, child.get('name'))
                          for child in item.getchildren()
                          if not etypes or child.tag in etypes)
        print_tabular(output)


class Groups(InfoCmd):
    """ Print out group info """
    options = [Bcfg2.Options.PositionalArgument("group", nargs='*')]

    def _profile_flag(self, group):
        """ Whether or not the group is a profile group """
        if self.core.metadata.groups[group].is_profile:
            return 'yes'
        else:
            return 'no'

    def run(self, setup):
        data = [("Groups", "Profile", "Category")]
        groups = self.get_group_list(setup.group)
        groups.sort()
        for group in groups:
            data.append((group,
                         self._profile_flag(group),
                         self.core.metadata.groups[group].category))
        print_tabular(data)


class Showclient(InfoCmd):
    """ Show metadata for the given hosts """

    options = [Bcfg2.Options.PositionalArgument("hostname", nargs='*')]

    def run(self, setup):
        for client in self.get_client_list(setup.hostname):
            try:
                metadata = self.core.build_metadata(client)
            except Bcfg2.Server.Plugin.MetadataConsistencyError:
                print("Could not build metadata for %s: %s" %
                      (client, sys.exc_info()[1]))
                continue
            fmt = "%-10s  %s"
            print(fmt % ("Hostname:", metadata.hostname))
            print(fmt % ("Profile:", metadata.profile))

            group_fmt = "%-10s  %-30s %s"
            header = False
            for group in sorted(list(metadata.groups)):
                category = ""
                for cat, grp in metadata.categories.items():
                    if grp == group:
                        category = "Category: %s" % cat
                        break
                if not header:
                    print(group_fmt % ("Groups:", group, category))
                    header = True
                else:
                    print(group_fmt % ("", group, category))

            if metadata.bundles:
                print(fmt % ("Bundles:", list(metadata.bundles)[0]))
            for bnd in sorted(list(metadata.bundles)[1:]):
                print(fmt % ("", bnd))
            if metadata.connectors:
                print("Connector data")
                print("=" * 80)
                for conn in metadata.connectors:
                    if getattr(metadata, conn):
                        print(fmt % (conn + ":", getattr(metadata, conn)))
                        print("=" * 80)


class Mappings(InfoCmd):
    """ Print generator mappings for optional type and name """

    options = [Bcfg2.Options.PositionalArgument("type", nargs='?'),
               Bcfg2.Options.PositionalArgument("name", nargs='?')]

    def run(self, setup):
        data = [('Plugin', 'Type', 'Name')]
        for generator in self.core.plugins_by_type(
            Bcfg2.Server.Plugin.Generator):
            etypes = setup.type or list(generator.Entries.keys())
            if setup.name:
                interested = [(etype, [setup.name]) for etype in etypes]
            else:
                interested = [(etype, generator.Entries[etype])
                              for etype in etypes
                              if etype in generator.Entries]
            for etype, names in interested:
                data.extend((generator.name, etype, name)
                            for name in names
                            if name in generator.Entries.get(etype, {}))
        print_tabular(data)


class PackageResolve(InfoCmd):
    """ Resolve packages for the given host"""

    options = [Bcfg2.Options.PositionalArgument("hostname"),
               Bcfg2.Options.PositionalArgument("package", nargs="*")]

    def run(self, setup):
        try:
            pkgs = self.core.plugins['Packages']
        except KeyError:
            print("Packages plugin not enabled")
            return 1

        metadata = self.core.build_metadata(setup.hostname)

        indep = lxml.etree.Element("Independent",
                                   name=self.__class__.__name__.lower())
        if setup.package:
            structures = [lxml.etree.Element("Bundle", name="packages")]
            for package in setup.package:
                lxml.etree.SubElement(structures[0], "Package", name=package)
        else:
            structures = self.core.GetStructures(metadata)

        pkgs._build_packages(metadata, indep,  # pylint: disable=W0212
                             structures)
        print("%d new packages added" % len(indep.getchildren()))
        if len(indep.getchildren()):
            print("    %s" % "\n    ".join(lxml.etree.tostring(p)
                                           for p in indep.getchildren()))


class Packagesources(InfoCmd):
    """ Show package sources """

    options = [Bcfg2.Options.PositionalArgument("hostname")]

    def run(self, setup):
        try:
            pkgs = self.core.plugins['Packages']
        except KeyError:
            print("Packages plugin not enabled")
            return 1
        try:
            metadata = self.core.build_metadata(setup.hostname)
        except Bcfg2.Server.Plugin.MetadataConsistencyError:
            print("Unable to build metadata for %s: %s" % (setup.hostname,
                                                           sys.exc_info()[1]))
            return 1
        print(pkgs.get_collection(metadata).sourcelist())


class Query(InfoCmd):
    """ Query clients """

    options = [
        Bcfg2.Options.ExclusiveOptionGroup(
            Bcfg2.Options.Option(
                "-g", "--group", metavar="<group>", dest="querygroups",
                type=Bcfg2.Options.Types.comma_list),
            Bcfg2.Options.Option(
                "-p", "--profile", metavar="<profile>", dest="queryprofiles",
                type=Bcfg2.Options.Types.comma_list),
            Bcfg2.Options.Option(
                "-b", "--bundle", metavar="<bundle>", dest="querybundles",
                type=Bcfg2.Options.Types.comma_list),
            required=True)]

    def run(self, setup):
        if setup.queryprofiles:
            res = self.core.metadata.get_client_names_by_profiles(
                setup.queryprofiles)
        elif setup.querygroups:
            res = self.core.metadata.get_client_names_by_groups(
                setup.querygroups)
        elif setup.querybundles:
            res = self.core.metadata.get_client_names_by_bundles(
                setup.querybundles)
        print("\n".join(res))


class Shell(InfoCmd):
    """ Open an interactive shell to run multiple bcfg2-info commands """
    interactive = False

    def run(self, setup):
        try:
            self.core.cmdloop('Welcome to bcfg2-info\n'
                              'Type "help" for more information')
        except KeyboardInterrupt:
            print("Ctrl-C pressed, exiting...")


class ProfileTemplates(InfoCmd):
    """ Benchmark template rendering times """

    options = [
        Bcfg2.Options.Option(
            "--clients", type=Bcfg2.Options.Types.comma_list,
            help="Benchmark templates for the named clients"),
        Bcfg2.Options.Option(
            "--runs", help="Number of rendering passes per template",
            default=5, type=int),
        Bcfg2.Options.PositionalArgument(
            "templates", nargs="*", default=[],
            help="Profile the named templates instead of all templates")]

    def profile_entry(self, entry, metadata, runs=5):
        """ Profile a single entry """
        times = []
        for i in range(runs):  # pylint: disable=W0612
            start = time.time()
            try:
                self.core.Bind(entry, metadata)
                times.append(time.time() - start)
            except:  # pylint: disable=W0702
                break
        if times:
            avg = sum(times) / len(times)
            if avg:
                self.logger.debug("   %s: %.02f sec" %
                                  (metadata.hostname, avg))
        return times

    def profile_struct(self, struct, metadata, templates=None, runs=5):
        """ Profile all entries in a given structure """
        times = dict()
        entries = struct.xpath("//Path")
        entry_count = 0
        for entry in entries:
            entry_count += 1
            if templates is None or entry.get("name") in templates:
                self.logger.info("Rendering Path:%s (%s/%s)..." %
                                 (entry.get("name"), entry_count,
                                  len(entries)))
                times.setdefault(entry.get("name"),
                                 self.profile_entry(entry, metadata,
                                                    runs=runs))
        return times

    def profile_client(self, metadata, templates=None, runs=5):
        """ Profile all structures for a given client """
        structs = self.core.GetStructures(metadata)
        struct_count = 0
        times = dict()
        for struct in structs:
            struct_count += 1
            self.logger.info("Rendering templates from structure %s:%s "
                             "(%s/%s)" %
                             (struct.tag, struct.get("name"), struct_count,
                              len(structs)))
            times.update(self.profile_struct(struct, metadata,
                                             templates=templates, runs=runs))
        return times

    def stdev(self, nums):
        """ Calculate the standard deviation of a list of numbers """
        mean = float(sum(nums)) / len(nums)
        return math.sqrt(sum((n - mean) ** 2 for n in nums) / float(len(nums)))

    def run(self, setup):
        clients = self.get_client_list(setup.clients)

        times = dict()
        client_count = 0
        for client in clients:
            client_count += 1
            self.logger.info("Rendering templates for client %s (%s/%s)" %
                             (client, client_count, len(clients)))
            times.update(self.profile_client(self.core.build_metadata(client),
                                             templates=setup.templates,
                                             runs=setup.runs))

        # print out per-file results
        tmpltimes = []
        for tmpl, ptimes in times.items():
            try:
                mean = float(sum(ptimes)) / len(ptimes)
            except ZeroDivisionError:
                continue
            ptimes.sort()
            median = ptimes[len(ptimes) / 2]
            std = self.stdev(ptimes)
            if mean > 0.01 or median > 0.01 or std > 1 or setup.templates:
                tmpltimes.append((tmpl, mean, median, std))
        print("%-50s %-9s  %-11s  %6s" %
              ("Template", "Mean Time", "Median Time", "σ"))
        for info in reversed(sorted(tmpltimes, key=operator.itemgetter(1))):
            print("%-50s %9.02f  %11.02f  %6.02f" % info)


if HAS_PROFILE:
    class Profile(InfoCmd):
        """ Profile a single bcfg2-info command """

        options = [Bcfg2.Options.PositionalArgument("command"),
                   Bcfg2.Options.PositionalArgument("args", nargs="*")]

        def run(self, setup):
            prof = profile.Profile()
            cls = self.core.commands[setup.command]
            prof.runcall(cls, " ".join(pipes.quote(a) for a in setup.args))
            display_trace(prof)


class InfoCore(cmd.Cmd,
               Bcfg2.Server.Core.Core,
               Bcfg2.Options.CommandRegistry):
    """Main class for bcfg2-info."""

    def __init__(self):
        cmd.Cmd.__init__(self)
        Bcfg2.Server.Core.Core.__init__(self)
        Bcfg2.Options.CommandRegistry.__init__(self)
        self.prompt = 'bcfg2-info> '

    def get_locals(self):
        """ Expose the local variables of the core to subcommands that
        need to reference them (i.e., the interactive interpreter) """
        return locals()

    def do_quit(self, _):
        """ quit|exit - Exit program """
        raise SystemExit(0)

    do_EOF = do_quit
    do_exit = do_quit

    def do_eventdebug(self, _):
        """ eventdebug - Enable debugging output for FAM events """
        self.fam.set_debug(True)

    do_event_debug = do_eventdebug

    def do_update(self, _):
        """ update - Process pending filesystem events """
        self.fam.handle_events_in_interval(0.1)

    def run(self):
        self.load_plugins()
        self.block_for_fam_events(handle_events=True)

    def _run(self):
        pass

    def _block(self):
        pass

    def shutdown(self):
        Bcfg2.Options.CommandRegistry.shutdown(self)
        Bcfg2.Server.Core.Core.shutdown(self)


class CLI(object):
    """ The bcfg2-info CLI """
    options = [Bcfg2.Options.BooleanOption("-p", "--profile", help="Profile")]

    def __init__(self):
        Bcfg2.Options.register_commands(InfoCore, globals().values(),
                                        parent=InfoCmd)
        parser = Bcfg2.Options.get_parser(
            description="Inspect a running Bcfg2 server",
            components=[self, InfoCore])
        parser.parse()

        if Bcfg2.Options.setup.profile and HAS_PROFILE:
            prof = profile.Profile()
            self.core = prof.runcall(InfoCore)
            display_trace(prof)
        else:
            if Bcfg2.Options.setup.profile:
                print("Profiling functionality not available.")
            self.core = InfoCore()

        for command in self.core.commands.values():
            command.core = self.core

    def run(self):
        """ Run bcfg2-info """
        if Bcfg2.Options.setup.subcommand != 'help':
            self.core.run()
        return self.core.runcommand()
