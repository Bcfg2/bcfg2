
import getopt, popen2, lxml.etree
import Bcfg2.Server.Admin

class Viz(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = '''bcfg2-admin viz [--includehosts] [--includebundles] [--includekey] [-o output.png] [--raw]'''
    __longhelp__ = __shorthelp__ + '\n\tProduce graphviz diagrams of metadata structures'

    colors = ['steelblue1', 'chartreuse', 'gold', 'magenta',
              'indianred1', 'limegreen', 'orange1', 'lightblue2',
              'green1', 'blue1', 'yellow1', 'darkturquoise', 'gray66']

    def __init__(self, cfile):
	Bcfg2.Server.Admin.MetadataCore.__init__(self, cfile)

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        # First get options to the 'viz' subcommand
        try:
            opts, args = getopt.getopt(args, 'rhbko:',
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
        dotpipe = popen2.Popen4(cmd)
        try:
            dotpipe.tochild.write("digraph groups {\n")
        except:
            print "write to dot process failed. Is graphviz installed?"
            raise SystemExit(1)
        dotpipe.tochild.write('\trankdir="LR";\n')
        dotpipe.tochild.write(self.metadata.viz(hosts, bundles, key, self.colors))
        if key:
            dotpipe.tochild.write("\tsubgraph cluster_key {\n")
            dotpipe.tochild.write('''\tstyle="filled";\n''')
            dotpipe.tochild.write('''\tcolor="lightblue";\n''')
            dotpipe.tochild.write('''\tBundle [ shape="septagon" ];\n''')
            dotpipe.tochild.write('''\tGroup [shape="ellipse"];\n''')
            dotpipe.tochild.write('''\tProfile [style="bold", shape="ellipse"];\n''')
            dotpipe.tochild.write('''\tHblock [label="Host1|Host2|Host3", shape="record"];\n''')
            dotpipe.tochild.write('''\tlabel="Key";\n''')
            dotpipe.tochild.write("\t}\n")
        dotpipe.tochild.write("}\n")
        dotpipe.tochild.close()
        return dotpipe.fromchild.read()
