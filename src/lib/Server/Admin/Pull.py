import sys
from metargs import Option

import Bcfg2.Options
import Bcfg2.Server.Admin


class Pull(Bcfg2.Server.Admin.MetadataCore):
    """Pull mode retrieves entries from clients and
    integrates the information into the repository.
    """
    __shorthelp__ = ("Integrate configuration information "
                     "from clients into the server repository")
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin pull [-v] [-f][-I] [-s] "
                                    "<client> <entry type> <entry name>\n")
    __usage__ = ("bcfg2-admin pull [options] <client> <entry type> "
                 "<entry name>\n\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n" %
                ("-v",
                 "be verbose",
                 "-f",
                 "force",
                 "-I",
                 "interactive",
                 "-s",
                 "stdin"))
    allowed = ['Metadata', 'BB', "DBStats", "Statistics", "Cfg", "SSHbase"]

    def __init__(self):
        Bcfg2.Server.Admin.MetadataCore.__init__(self)
        self.log = False
        self.mode = 'interactive'
        Bcfg2.Options.add_options(
            Bcfg2.Options.VERBOSE,
            Option('-f', '--force'),
            Bcfg2.Options.INTERACTIVE,
            Option('-s', '--stdin', help='Use stdin', action='store_true'),
        )
        
        args = Bcfg2.Options.bootstrap()
        if not args.stdin:
            Bcfg2.Options.add_options(
                Option('client', help='Client to pull', metavar='<client>'),
                Option('type', help='Entry type', metavar='<entry type>'),
                Option('name', help='Entry name', metavar='<entry name>'),
            )

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)

        if args.verbose:
            self.log = True
        if args.force:
            self.mode = 'force'

        if args.interactive:
            self.mode == 'interactive'

        if args.stdin:
            for line in sys.stdin:
                try:
                    self.PullEntry(*line.split(None, 3))
                except SystemExit:
                    print("  for %s" % line)
                except:
                    print("Bad entry: %s" % line.strip())
        else:
            self.PullEntry(args.client, args.type, args.name)

    def BuildNewEntry(self, client, etype, ename):
        """Construct a new full entry for
        given client/entry from statistics.
        """
        new_entry = {'type': etype, 'name': ename}
        for plugin in self.bcore.pull_sources:
            try:
                (owner, group, perms, contents) = \
                        plugin.GetCurrentEntry(client, etype, ename)
                break
            except Bcfg2.Server.Plugin.PluginExecutionError:
                if plugin == self.bcore.pull_sources[-1]:
                    print("Pull Source failure; could not fetch current state")
                    raise SystemExit(1)

        try:
            data = {'owner': owner,
                    'group': group,
                    'perms': perms,
                    'text': contents}
        except UnboundLocalError:
            print("Unable to build entry. "
                  "Do you have a statistics plugin enabled?")
            raise SystemExit(1)
        for k, v in list(data.items()):
            if v:
                new_entry[k] = v
        #print new_entry
        return new_entry

    def Choose(self, choices):
        """Determine where to put pull data."""
        if self.mode == 'interactive':
            for choice in choices:
                print("Plugin returned choice:")
                if id(choice) == id(choices[0]):
                    print("(current entry) ")
                if choice.all:
                    print(" => global entry")
                elif choice.group:
                    print(" => group entry: %s (prio %d)" %
                          (choice.group, choice.prio))
                else:
                    print(" => host entry: %s" % (choice.hostname))
                # py3k compatibility
                try:
                    ans = raw_input("Use this entry? [yN]: ") in ['y', 'Y']
                except NameError:
                    ans = input("Use this entry? [yN]: ") in ['y', 'Y']
                if ans:
                    return choice
            return False
        else:
            # mode == 'force'
            if not choices:
                return False
            return choices[0]

    def PullEntry(self, client, etype, ename):
        """Make currently recorded client state correct for entry."""
        new_entry = self.BuildNewEntry(client, etype, ename)

        meta = self.bcore.build_metadata(client)
        # Find appropriate plugin in bcore
        glist = [gen for gen in self.bcore.generators if
                 ename in gen.Entries.get(etype, {})]
        if len(glist) != 1:
            self.errExit("Got wrong numbers of matching generators for entry:" \
                         + "%s" % ([g.name for g in glist]))
        plugin = glist[0]
        if not isinstance(plugin, Bcfg2.Server.Plugin.PullTarget):
            self.errExit("Configuration upload not supported by plugin %s" \
                         % (plugin.name))
        try:
            choices = plugin.AcceptChoices(new_entry, meta)
            specific = self.Choose(choices)
            if specific:
                plugin.AcceptPullData(specific, new_entry, self.log)
        except Bcfg2.Server.Plugin.PluginExecutionError:
            self.errExit("Configuration upload not supported by plugin %s" \
                         % (plugin.name))
        # Commit if running under a VCS
        for vcsplugin in list(self.bcore.plugins.values()):
            if isinstance(vcsplugin, Bcfg2.Server.Plugin.Version):
                files = "%s/%s" % (plugin.data, ename)
                comment = 'file "%s" pulled from host %s' % (files, client)
                vcsplugin.commit_data([files], comment)
