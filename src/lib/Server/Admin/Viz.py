import getopt
from subprocess import Popen, PIPE
import Bcfg2.Server.Admin

class Viz(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Produce graphviz diagrams of metadata structures"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin viz [--includehosts] "
                                    "[--includebundles] [--includekey] "
                                    "[-o output.png] [--raw]")
    __usage__ = ("bcfg2-admin viz [options]\n\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n" %
                ("-H, --includehosts",
                 "include hosts in the viz output",
                 "-b, --includebundles",
                 "include bundles in the viz output",
                 "-k, --includekey",
                 "show a key for different digraph shapes",
                 "-o, --outfile <file>",
                 "write viz output to an output file"))

    colors = ['steelblue1', 'chartreuse', 'gold', 'magenta',
              'indianred1', 'limegreen', 'orange1', 'lightblue2',
              'green1', 'blue1', 'yellow1', 'darkturquoise', 'gray66']

    def __init__(self, cfile):
        Bcfg2.Server.Admin.MetadataCore.__init__(self, cfile,
                                                 self.__usage__)

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        # First get options to the 'viz' subcommand
        try:
            opts, args = getopt.getopt(args, 'rHbko:',
                                       ['raw', 'includehosts', 'includebundles',
                                        'includekey', 'outfile='])
        except getopt.GetoptError, msg:
            print msg
            raise SystemExit(1)

        rset = False
        hset = False
        bset = False
        kset = False
        outputfile = False
        for opt, arg in opts:
            if opt in ("-r", "--raw"):
                rset = True
            elif opt in ("-H", "--includehosts"):
                hset = True
            elif opt in ("-b", "--includebundles"):
                bset = True
            elif opt in ("-k", "--includekey"):
                kset = True
            elif opt in ("-o", "--outfile"):
                outputfile = arg

        data = self.Visualize(self.get_repo_path(), rset, hset, bset,
                              kset, outputfile)
        print data

    def Visualize(self, repopath, raw=False, hosts=False,
                  bundles=False, key=False, output=False):
        '''Build visualization of groups file'''
        if raw:
            cmd = "dd bs=4M"
            if output:
                cmd += " of=%s" % output
        else:
            cmd = "dot -Tpng"
            if output:
                cmd += " -o %s" % output
        dotpipe = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, close_fds=True)
        try:
            dotpipe.stdin.write("digraph groups {\n")
        except:
            print "write to dot process failed. Is graphviz installed?"
            raise SystemExit(1)
        dotpipe.stdin.write('\trankdir="LR";\n')
        dotpipe.stdin.write(self.metadata.viz(hosts, bundles,
                                                key, self.colors))
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
