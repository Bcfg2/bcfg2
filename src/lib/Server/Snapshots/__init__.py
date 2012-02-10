__all__ = ['models', 'db_from_config', 'setup_session']

import sqlalchemy
import sqlalchemy.orm
from metargs import Option
import Bcfg2.Options

def register_snapshot_args():
    Bcfg2.Options.add_options(
        Option('snapshots:driver'),
        Option('snapshots:database'),
        Option('snapshots:user'),
        Option('snapshots:password'),
        Option('snapshots:host'),
    )

def db_from_config(args):
    driver = args.snapshots_driver
    if driver == 'sqlite':
        return 'sqlite:///%s' % args.snapshots_database
    elif driver in ['mysql', 'postgres']:
        return '%s://%s:%s@%s/%s' % (
            driver,
            args.snapshots_user,
            args.snapshots_password,
            args.snapshots_host,
            args.snapshots_database)
    else:
        raise Exception("unsupported db driver %s" % driver)


def setup_session(args, debug=False):
    engine = sqlalchemy.create_engine(db_from_config(args),
                                      echo=debug)
    Session = sqlalchemy.orm.sessionmaker()
    Session.configure(bind=engine)
    return Session()
