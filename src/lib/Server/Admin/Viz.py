import getopt
from subprocess import Popen, PIPE
import sys

import Bcfg2.Server.Admin


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

    plugin_blacklist = ['DBStats', 'Snapshots', 'Cfg', 'Pkgmgr', 'Packages',
                        'Rules', 'Account', 'Decisions', 'Deps', 'Git', 'Svn',
                        'Fossil', 'Bzr', 'Bundler', 'TGenshi', 'SGenshi',
                        'Base']

    def __init__(self, cfile):

        Bcfg2.Server.Admin.MetadataCore.__init__(self, cfile,
                                                 self.__usage__,
                                                 pblacklist=self.plugin_blacklist)

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        # First get options to the 'viz' subcommand
        try:
            opts, args = getopt.getopt(args, 'Hbkc:o:',
                                       ['includehosts', 'includebundles',
                                        'includekey', 'only-client=', 'outfile='])
        except getopt.GetoptError:
            msg = sys.exc_info()[1]
            print(msg)
            print(self.__longhelp__)
            raise SystemExit(1)

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

        data = self.Visualize(self.get_repo_path(), hset, bset,
                              kset, only_client, outputfile)
        print(data)
        raise SystemExit(0)

    def Visualize(self, repopath, hosts=False,
                  bundles=False, key=False, only_client=None, output=False):
        """Build visualization of groups file."""
        if output:
            format = output.split('.')[-1]
        else:
            format = 'png'

        cmd = "dot -T%s" % (format)
        if output:
            cmd += " -o %s" % output
        dotpipe = Popen(cmd, shell=True, stdin=PIPE,
                        stdout=PIPE, close_fds=True)
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
