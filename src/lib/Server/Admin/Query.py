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
                                                ['Metadata'],
                                                'foo', False, 'UTF-8')
        except Bcfg2.Server.Core.CoreInitError, msg:
            self.errExit("Core load failed because %s" % msg)
        self.bcore.fam.handle_events_in_interval(1)
        self.meta = self.bcore.metadata

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        clients = self.meta.clients.keys()
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
                print "Unknown argument %s" % arg
                continue
            if k == 'p':
                nc = self.meta.GetClientByProfile(v)
            elif k == 'g':
                nc = self.meta.GetClientByGroup(v)
            else:
                print "One of g= or p= must be specified"
                raise SystemExit(1)
            clients = [c for c in clients if c in nc]
        if '-n' in args:
            for client in clients:
                print client
        else:
            print ','.join(clients)
        if '-f' in args:
            f = open(filename, "w")
            for client in clients:
                f.write(client + "\n")
            f.close()
            print "Wrote results to %s" % (filename)
