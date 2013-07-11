""" Produce graphviz diagrams of metadata structures """

import getopt
import Bcfg2.Server.Admin
from Bcfg2.Utils import Executor


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

    __plugin_blacklist__ = ['DBStats', 'Cfg', 'Pkgmgr',
                            'Packages', 'Rules', 'Decisions',
                            'Deps', 'Git', 'Svn', 'Fossil', 'Bzr', 'Bundler']

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

        exc = Executor()
        cmd = ["dot", "-T", fmt]
        if output:
            cmd.extend(["-o", output])
        idata = ["digraph groups {",
                 '\trankdir="LR";',
                 self.metadata.viz(hosts, bundles,
                                   key, only_client, self.colors)]
        if key:
            idata.extend(
                ["\tsubgraph cluster_key {",
                 '\tstyle="filled";',
                 '\tcolor="lightblue";',
                 '\tBundle [ shape="septagon" ];',
                 '\tGroup [shape="ellipse"];',
                 '\tProfile [style="bold", shape="ellipse"];',
                 '\tHblock [label="Host1|Host2|Host3",shape="record"];',
                 '\tlabel="Key";',
                 "\t}"])
        idata.append("}")
        try:
            result = exc.run(cmd, inputdata=idata)
        except OSError:
            # on some systems (RHEL 6), you cannot run dot with
            # shell=True.  on others (Gentoo with Python 2.7), you
            # must.  In yet others (RHEL 5), either way works.  I have
            # no idea what the difference is, but it's kind of a PITA.
            result = exc.run(cmd, shell=True, inputdata=idata)
        if not result.success:
            print("Error running %s: %s" % (cmd, result.error))
            raise SystemExit(result.retval)
