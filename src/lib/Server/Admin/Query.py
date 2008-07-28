import Bcfg2.Server.Admin, Bcfg2.Logging, logging

class Query(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = 'bcfg2-admin query [-n] [-c] [-f filename] g=group p=profile'
    __longhelp__ = __shorthelp__ + '\n\tQuery clients'
    def __init__(self, cfile):
        logging.root.setLevel(100)
        Bcfg2.Logging.setup_logging(100, to_console=False, to_syslog=False)
        Bcfg2.Server.Admin.Mode.__init__(self, cfile)
        try:
            self.bcore = Bcfg2.Server.Core.Core(self.get_repo_path(), [],
                                                [], [],
                                                'foo', False, 'UTF-8')
        except Bcfg2.Server.Core.CoreInitError, msg:
            self.errExit("Core load failed because %s" % msg)
        [self.bcore.fam.Service() for _ in range(1)]
        self.meta = self.bcore.metadata
        while self.bcore.fam.Service():
            pass

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
                nc = [c for c, p in self.meta.clients.iteritems() if p == v]
            elif k == 'g':
                nc = [c for c in self.meta.clients if v in
                      self.meta.groups[self.meta.clients[c]][1] or
                      v in self.meta.cgroups.get(c, [])]
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
