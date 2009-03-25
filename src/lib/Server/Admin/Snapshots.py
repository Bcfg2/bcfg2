import Bcfg2.Server.Admin
import sys

try:
    import sqlalchemy, sqlalchemy.orm
except:
    # FIXME should probably do something smarter here for folks without SA
    pass
import Bcfg2.Server.Snapshots
import Bcfg2.Server.Snapshots.model
from Bcfg2.Server.Snapshots.model import Snapshot, Client, Metadata, Base, \
     Group, Package

class Snapshots(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = "Interact with the Snapshots system"
    __longhelp__ = (__shorthelp__)
    __usage__ = ("bcfg2-admin snapshots [init|query qtype]")

    q_dispatch = {'client':Client,
                  'group':Group,
                  'metadata':Metadata,
                  'package':Package,
                  'snapshot':Snapshot}

    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)
        #self.session = Bcfg2.Server.Snapshots.setup_session(debug=True)
        self.session = Bcfg2.Server.Snapshots.setup_session()

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if len(args) == 0 or args[0] == '-h':
            print(self.__usage__)
            raise SystemExit(0)

        if args[0] == 'query':
            if args[1] in self.q_dispatch:
                q_obj = self.q_dispatch[args[1]]
                if q_obj == Client:
                    print("\nInactive hosts:")
                    for host in self.session.query(q_obj).filter(q_obj.active == False):
                        print(" %s" % host.name)
                    print("\nActive hosts:")
                    for host in self.session.query(q_obj).filter(q_obj.active == True):
                        print(" %s" % host.name)
                else:
                    results = self.session.query(q_obj).all()
            else:
                print 'error'
                raise SystemExit, 1
        elif args[0] == 'init':
            dbpath = Bcfg2.Server.Snapshots.db_from_config()
            engine = sqlalchemy.create_engine(dbpath, echo=True)
            metadata = Base.metadata
            metadata.create_all(engine)
            Session = sqlalchemy.orm.sessionmaker()
            Session.configure(bind=engine)
            session = Session()
            session.commit()
        elif args[0] == 'dump':
            client = args[1]
            snap = Snapshot.get_current(self.session, unicode(client))
            if not snap:
                print("Current snapshot for %s not found" % client)
                sys.exit(1)
            print("Client %s last run at %s" % (client, snap.timestamp))
            for pkg in snap.packages:
                print "C:", pkg.correct, 'M:', pkg.modified
                print "start", pkg.start.name, pkg.start.version
                print "end", pkg.end.name, pkg.end.version
            #print("\nExtra packages:")
            #for pkg in snap.extra_packages:
            #    print("  %s" % pkg.name)
            #print("\nExtra services:")
            #for svc in snap.extra_services:
            #    print("  %s" % svc.name)
        elif args[0] == 'reports':
            if '-a' in args[1:]:
                q = self.session.query(Client.name,
                                       Snapshot.correct,
                                       Snapshot.timestamp).filter(Client.id==Snapshot.client_id)\
                                       .group_by(Client.id)
                print "Client\tCorrect\tTime"
                print 60* '='
                for item in q.all():
                    print "%s\t%s\t%s" % (item)
            else:
                print "Unknown options: ", args[1:]
