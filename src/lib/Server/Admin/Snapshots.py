import sys
try:
    import sqlalchemy, sqlalchemy.orm
except:
    # FIXME should probably do something smarter here for folks without SA
    pass

import Bcfg2.Server.Admin
import Bcfg2.Server.Snapshots
import Bcfg2.Server.Snapshots.model
from Bcfg2.Server.Snapshots.model import Snapshot, Client, Metadata, Base, \
     Group, Package

def print_table(rows, justify='left', hdr=True, vdelim=" ", padding=1):
    """Pretty print a table

    rows - list of rows ([[row 1], [row 2], ..., [row n]])
    hdr - if True the first row is treated as a table header
    vdelim - vertical delimiter between columns
    padding - # of spaces around the longest element in the column
    justify - may be left,center,right
    """
    hdelim = "="
    justify = {'left':str.ljust,
               'center':str.center,
               'right':str.rjust}[justify.lower()]

    '''calculate column widths (longest item in each column
       plus padding on both sides)'''
    cols = zip(*rows)
    colWidths = [max([len(str(item))+2*padding for \
                 item in col]) for col in cols]
    borderline = vdelim.join([w*hdelim for w in colWidths])

    # print out the table
    print(borderline)
    for row in rows:
        print(vdelim.join([justify(str(item), width) for \
             (item, width) in zip(row, colWidths)]))
        if hdr:
            print(borderline)
            hdr = False
    print(borderline)

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
                    rows = []
                    labels = ('Client', 'Active')
                    for host in \
                       self.session.query(q_obj).filter(q_obj.active == False):
                        rows.append([host.name, 'No'])
                    for host in \
                       self.session.query(q_obj).filter(q_obj.active == True):
                        rows.append([host.name, 'Yes'])
                    print_table([labels]+rows, justify='left', hdr=True, vdelim=" ", padding=1)
                elif q_obj == Group:
                    print("Groups:")
                    for group in self.session.query(q_obj).all():
                        print(" %s" % group.name)
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
                                       Snapshot.revision,
                                       Snapshot.timestamp).filter(Client.id==Snapshot.client_id)\
                                       .group_by(Client.id)
                rows = []
                labels = ('Client', 'Correct', 'Revision', 'Time')
                for item in q.all():
                    cli, cor, time, rev = item
                    rows.append([cli, cor, time, rev])
                print_table([labels]+rows, justify='left', hdr=True, vdelim=" ", padding=1)
            else:
                print "Unknown options: ", args[1:]
