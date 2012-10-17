""" Produce graphviz diagrams of metadata structures """

import getopt
from subprocess import Popen, PIPE
import pipes
import Bcfg2.Server.Admin


class Viz(Bcfg2.Server.Admin.MetadataCore):
    """ Produce graphviz diagrams of metadata structures """
    __usage__ = ("[options]\n\n"
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

    __plugin_blacklist__ = ['DBStats', 'Snapshots', 'Cfg', 'Pkgmgr',
                            'Packages', 'Rules', 'Account', 'Decisions',
                            'Deps', 'Git', 'Svn', 'Fossil', 'Bzr', 'Bundler',
                            'TGenshi', 'Base']

    def __call__(self, args):
        # First get options to the 'viz' subcommand
        try:
            opts, args = getopt.getopt(args, 'Hbkc:o:',
                                       ['includehosts', 'includebundles',
                                        'includekey', 'only-client=',
                                        'outfile='])
        except getopt.GetoptError:
            self.usage()

        hset = False
        bset = False
        kset = False
        only_client = None
        outputfile = False
        for opt, arg in opts:
            if opt in ("-H", "--includehosts"):
                hset = True
            elif opt in ("-b", "--includebundles"):
                bset = True
            elif opt in ("-k", "--includekey"):
                kset = True
            elif opt in ("-c", "--only-client"):
                only_client = arg
            elif opt in ("-o", "--outfile"):
                outputfile = arg

        data = self.Visualize(hset, bset, kset, only_client, outputfile)
        if data:
            print(data)

    def Visualize(self, hosts=False, bundles=False, key=False,
                  only_client=None, output=None):
        """Build visualization of groups file."""
        if output:
            fmt = output.split('.')[-1]
        else:
            fmt = 'png'

        cmd = ["dot", "-T", fmt]
        if output:
            cmd.extend(["-o", output])
        try:
            dotpipe = Popen(cmd, stdin=PIPE, stdout=PIPE, close_fds=True)
        except OSError:
            # on some systems (RHEL 6), you cannot run dot with
            # shell=True.  on others (Gentoo with Python 2.7), you
            # must.  In yet others (RHEL 5), either way works.  I have
            # no idea what the difference is, but it's kind of a PITA.
            cmd = ["dot", "-T", pipes.quote(fmt)]
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
            dotpipe.stdin.write('\tstyle="filled";\n')
            dotpipe.stdin.write('\tcolor="lightblue";\n')
            dotpipe.stdin.write('\tBundle [ shape="septagon" ];\n')
            dotpipe.stdin.write('\tGroup [shape="ellipse"];\n')
            dotpipe.stdin.write('\tProfile [style="bold", shape="ellipse"];\n')
            dotpipe.stdin.write('\tHblock [label="Host1|Host2|Host3", '
                                'shape="record"];\n')
            dotpipe.stdin.write('\tlabel="Key";\n')
            dotpipe.stdin.write("\t}\n")
        dotpipe.stdin.write("}\n")
        dotpipe.stdin.close()
        return dotpipe.stdout.read()
