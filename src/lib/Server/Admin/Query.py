import logging
import Bcfg2.Logger
import Bcfg2.Server.Admin


class Query(Bcfg2.Server.Admin.Mode):
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

    def __init__(self, cfile):
        logging.root.setLevel(100)
        Bcfg2.Logger.setup_logging(100, to_console=False, to_syslog=False)
        Bcfg2.Server.Admin.Mode.__init__(self, cfile)
        try:
            self.bcore = Bcfg2.Server.Core.Core(self.get_repo_path(),
                                                ['Metadata', 'Probes'],
                                                'foo', False, 'UTF-8')
        except Bcfg2.Server.Core.CoreInitError:
            msg = sys.exc_info()[1]
            self.errExit("Core load failed because %s" % msg)
        self.bcore.fam.handle_events_in_interval(1)
        self.meta = self.bcore.metadata

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        clients = list(self.meta.clients.keys())
        filename_arg = False
        filename = None
        for arg in args:
            if filename_arg == True:
                filename = arg
                filename_arg = False
                continue
            if arg in ['-n', '-c']:
                continue
            if arg in ['-f']:
                filename_arg = True
                continue
            try:
                k, v = arg.split('=')
            except:
                print("Unknown argument %s" % arg)
                continue
            if k == 'p':
                nc = self.meta.get_client_names_by_profiles(v.split(','))
            elif k == 'g':
                nc = self.meta.get_client_names_by_groups(v.split(','))
                # add probed groups (if present)
                for conn in self.bcore.connectors:
                    if isinstance(conn, Bcfg2.Server.Plugins.Probes.Probes):
                        for c, glist in list(conn.cgroups.items()):
                            for g in glist:
                                if g in v.split(','):
                                    nc.append(c)
            else:
                print("One of g= or p= must be specified")
                raise SystemExit(1)
            clients = [c for c in clients if c in nc]
        if '-n' in args:
            for client in clients:
                print(client)
        else:
            print(','.join(clients))
        if '-f' in args:
            f = open(filename, "w")
            for client in clients:
                f.write(client + "\n")
            f.close()
            print("Wrote results to %s" % (filename))
