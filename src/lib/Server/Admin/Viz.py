from metargs import Option
from subprocess import Popen, PIPE
import pipes
import Bcfg2.Server.Admin
import Bcfg2.Options


class Viz(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Produce graphviz diagrams of metadata structures"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin viz [--includehosts] "
                                    "[--includebundles] [--includekey] "
                                    "[--only-client clientname] "
                                    "[-o output.<ext>]\n")
    __usage__ = ("bcfg2-admin viz [options]\n\n"
                 "     %-32s%s\n"
                 "     %-32s%s\n"
                 "     %-32s%s\n"
                 "     %-32s%s\n"
                 "     %-32s%s\n" %
                ("-H, --includehosts",
                 "include hosts in the viz output",
                 "-b, --includebundles",
                 "include bundles in the viz output",
                 "-k, --includekey",
                 "show a key for different digraph shapes",
                 "-c, --only-client <clientname>",
                 "show only the groups, bundles for the named client",
                 "-o, --outfile <file>",
                 "write viz output to an output file"))

    colors = ['steelblue1', 'chartreuse', 'gold', 'magenta',
              'indianred1', 'limegreen', 'orange1', 'lightblue2',
              'green1', 'blue1', 'yellow1', 'darkturquoise', 'gray66']

    __plugin_blacklist__ = ['DBStats', 'Snapshots', 'Cfg', 'Pkgmgr', 'Packages',
                            'Rules', 'Account', 'Decisions', 'Deps', 'Git', 'Svn',
                            'Fossil', 'Bzr', 'Bundler', 'TGenshi', 'SGenshi',
                            'Base']

    def __init__(self):
        Bcfg2.Server.Admin.MetadataCore.__init__(self,
                                                 pblacklist=self.plugin_blacklist)
        Bcfg2.Options.add_options(
            Option('-H', '--includehosts', action='store_true',
                help='include hosts in the viz output'),
            Option('-b', '--includebundles', action='store_true',
                help='include bundles in the viz output'),
            Option('-k', '--includekey', action='store_true',
                help='show a key for different digraph shapes'),
            Option('--only-client',
                help='show only the groups, bundles for the named client'),
            Option('-o', '--outfile', help='write viz output to an output file')
        )

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        data = self.Visualize(self.args.repository_path, args.includehosts,
                              args.includebundles,
                              args.includekey, args.only_client, args.outfile)
        if data:
            print(data)
        raise SystemExit(0)

    def Visualize(self, repopath, hosts=False,
                  bundles=False, key=False, only_client=None, output=False):
        """Build visualization of groups file."""
        if output:
            format = output.split('.')[-1]
        else:
            format = 'png'

        cmd = ["dot", "-T", format]
        if output:
            cmd.extend(["-o", output])
        try:
            dotpipe = Popen(cmd, stdin=PIPE, stdout=PIPE, close_fds=True)
        except OSError:
            # on some systems (RHEL 6), you cannot run dot with
            # shell=True.  on others (Gentoo with Python 2.7), you
            # must.  In yet others (RHEL 5), either way works.  I have
            # no idea what the difference is, but it's kind of a PITA.
            cmd = ["dot", "-T", pipes.quote(format)]
            if output:
                cmd.extend(["-o", pipes.quote(output)])
            dotpipe = Popen(cmd, shell=True,
                            stdin=PIPE, stdout=PIPE, close_fds=True)
        try:
            dotpipe.stdin.write("digraph groups {\n")
        except:
            print("write to dot process failed. Is graphviz installed?")
            raise SystemExit(1)
        dotpipe.stdin.write('\trankdir="LR";\n')
        dotpipe.stdin.write(self.metadata.viz(hosts, bundles,
                                              key, only_client, self.colors))
        if key:
            dotpipe.stdin.write("\tsubgraph cluster_key {\n")
            dotpipe.stdin.write('''\tstyle="filled";\n''')
            dotpipe.stdin.write('''\tcolor="lightblue";\n''')
            dotpipe.stdin.write('''\tBundle [ shape="septagon" ];\n''')
            dotpipe.stdin.write('''\tGroup [shape="ellipse"];\n''')
            dotpipe.stdin.write('''\tProfile [style="bold", shape="ellipse"];\n''')
            dotpipe.stdin.write('''\tHblock [label="Host1|Host2|Host3", shape="record"];\n''')
            dotpipe.stdin.write('''\tlabel="Key";\n''')
            dotpipe.stdin.write("\t}\n")
        dotpipe.stdin.write("}\n")
        dotpipe.stdin.close()
        return dotpipe.stdout.read()
