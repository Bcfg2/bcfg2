__all__ = ['models', 'db_from_config', 'setup_session']

import sqlalchemy, sqlalchemy.orm, ConfigParser

def db_from_config(fname='/etc/bcfg2.conf'):
    cp = ConfigParser.ConfigParser()
    cp.read([fname])
    driver = cp.get('snapshots', 'driver')
    if driver == 'sqlite':
        path = cp.get('snapshots', 'database')
        return 'sqlite:///%s' % path
    else:
        raise Exception, "not done yet"


def setup_session(debug=False):
    engine = sqlalchemy.create_engine(db_from_config(),
                                      echo=debug)
    Session = sqlalchemy.orm.sessionmaker()
    Session.configure(bind=engine)
    return Session()
