import Bcfg2.Server.Admin, Bcfg2.Logging, logging

class Query(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = 'bcfg2-admin query <pattern>'
    __longhelp__ = __shorthelp__ + '\n\tCreate or delete client entries'
    def __init__(self, cfile):
        logging.root.setLevel(100)
        Bcfg2.Logging.setup_logging(100, to_console=False, to_syslog=False)
        Bcfg2.Server.Admin.Mode.__init__(self, cfile)
        try:
            self.bcore = Bcfg2.Server.Core.Core(self.get_repo_path(),
                                                [], ['Metadata'],
                                                'foo', False)
        except Bcfg2.Server.Core.CoreInitError, msg:
            self.errExit("Core load failed because %s" % msg)
        [self.bcore.fam.Service() for _ in range(1)]
        self.meta = self.bcore.metadata
        self.meta.load_probedata()
        while self.bcore.fam.Service():
            pass

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        clients = None
        for arg in args:
            k, v = arg.split('=')
            if k == 'p':
                nc = [c for c, p in self.meta.clients.iteritems() if p == v]
            elif k == 'g':
                nc = [c for c in self.meta.clients if v in
                      self.meta.groups[self.meta.clients[c]][1] or
                      v in self.meta.cgroups.get(c, [])]
            if clients == None:
                clients = nc
            else:
                clients = [c for c in clients if c in nc]
            
        print ','.join(clients)
