import logging
import argparse
from metargs import Option
import Bcfg2.Logger
import Bcfg2.Server.Admin
import Bcfg2.Options


class Query(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Query clients"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin query [-n] [-c] "
                                    "[-f filename] g=group p=profile")
    __usage__ = ("bcfg2-admin query [options] <g=group> <p=profile>\n\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n" %
                ("-n",
                 "query results delimited with newlines",
                 "-c",
                 "query results delimited with commas",
                 "-f filename",
                 "write query to file"))

    def __init__(self):
        logging.root.setLevel(100)
        Bcfg2.Logger.setup_logging(100, to_console=False, to_syslog=False)
        Bcfg2.Server.Admin.MetadataCore.__init__(self)
        Bcfg2.Options.set_help(self.__shorthelp__)

        Bcfg2.Options.add_options(
            Option('-n', '--one-per-line', dest='per_line', action='store_true',
                help="Print one result per line"),
            Option('--comma-separated', dest='per_line', action='store_false',
                help="Print results comma separated"),
            Option('-f', '--output-file', type=argparse.FileType('w'),
                default=None, help="Write the query results to the specified file"),
            Option('query', type=lambda x: x.split('=', 1), nargs='+',
                help='Query parameters. Should start with either p= or g= '
                     'to specify either search by group or profile'),
        )


    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)

        clients = list(self.metadata.clients.keys())
        
        for qtype, qvals in args.query:
            if qtype == 'p':
                nc = self.metadata.get_client_names_by_profiles(qvals.split(','))
            elif qtype == 'g':
                nc = self.metadata.get_client_names_by_groups(qvals.split(','))
                # add probed groups (if present)
                for conn in self.bcore.connectors:
                    if isinstance(conn, Bcfg2.Server.Plugins.Probes.Probes):
                        for c, glist in list(conn.cgroups.items()):
                            for g in glist:
                                if g in qvals.split(','):
                                    nc.append(c)
        
        clients = [c for c in clients if c in nc]
 
        if args.per_line:
            for client in clients:
                print(client)
        else:
            print(','.join(clients))

        if args.output_file is not None:
            for client in clients:
                args.output_file.write(client + "\n")
            print("Wrote results to %s" % (args.output_file.name))
