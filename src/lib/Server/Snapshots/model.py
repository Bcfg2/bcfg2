from sqlalchemy import Table, Column, Integer, Unicode, MetaData, ForeignKey, Boolean, DateTime, create_engine, UnicodeText

import sqlalchemy.exceptions
from sqlalchemy.orm import relation, backref, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# TODO pingtime?
# backlinks Client -> Snapshot
# entry missing fields
# extra entries

class Uniquer(object):
    @classmethod
    def by_value(cls, session, **kwargs):
        try:
            return session.query(cls).filter_by(**kwargs).one()
        except sqlalchemy.exceptions.InvalidRequestError:
            return cls(**kwargs)

Base = declarative_base()

class Administrator(Uniquer, Base):
    __tablename__ = 'administrator'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(20), unique=True)
    email = Column(Unicode(64))

admin_client = Table('admin_client', Base.metadata,
                     Column('admin_id', Integer, ForeignKey('administrator.id')),
                     Column('client_id', Integer, ForeignKey('client.id')))

class Client(Uniquer, Base):
    __tablename__ = 'client'
    id = Column(Integer, primary_key=True)        
    name = Column(Unicode(64), unique=True)
    admins = relation("Administrator", secondary=admin_client)
    active = Column(Boolean, default=True)

class Group(Uniquer, Base):
    __tablename__ = 'group'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(32), unique=True)

class ConnectorKeyVal(Uniquer, Base):
    __tablename__ = 'connkeyval'
    id = Column(Integer, primary_key=True)    
    connector = Column(Unicode(16))
    key = Column(Unicode(32))
    value = Column(UnicodeText)

meta_group = Table('meta_group', Base.metadata,
                   Column('metadata_id', Integer, ForeignKey('metadata.id')),
                   Column('group_id', Integer, ForeignKey('group.id')))

meta_conn = Table('meta_conn', Base.metadata,
                  Column('metadata_id', Integer, ForeignKey('metadata.id')),
                  Column('connkeyval_id', Integer, ForeignKey('connkeyval.id')))

class Metadata(Base):
    __tablename__ = 'metadata'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('client.id'))
    client = relation(Client)
    groups = relation("Group", secondary=meta_group)
    keyvals = relation(ConnectorKeyVal, secondary=meta_conn)

    @classmethod
    def from_metadata(cls, session, metadata):
        client = Client.by_value(session, name=metadata.hostname)
        m = cls(client=client)
        for group in metadata.groups:
            m.groups.append(Group.by_value(session, name=unicode(group)))
        for connector in metadata.connectors:
            data = getattr(metadata, connector)
            if not isinstance(data, dict):
                continue
            for key, value in data.iteritems():
                if not isinstance(value, str):
                    continue
                m.keyvals.append(ConnectorKeyVal.by_value(session,
                                                          connector=unicode(connector),
                                                          key=unicode(key),
                                                          value=unicode(value)))
        return m

class Package(Base):
    __tablename__ = 'package'
    id = Column(Integer, primary_key=True)        
    name = Column(Unicode(24))
    type = Column(Unicode(16))
    version = Column(Unicode(16))
    verification_status = Column(Boolean)

class PackageCorrespondence(Base):
    __tablename__ = 'package_pair'
    id = Column(Integer, primary_key=True)    
    desired_id = Column(Integer, ForeignKey('package.id'))
    desired = relation(Package, primaryjoin=desired_id == Package.id)
    incorrect_id = Column(Integer, ForeignKey('package.id'), nullable=True)
    incorrect = relation(Package, primaryjoin=incorrect_id == Package.id)
    modified = Column(Boolean)

package_snap = Table('package_snap', Base.metadata,
                     Column('ppair_id', Integer, ForeignKey('package_pair.id')),
                     Column('snapshot_id', Integer, ForeignKey('snapshot.id')))

class Service(Base):
    __tablename__ = 'service'
    id = Column(Integer, primary_key=True)        
    name = Column(Unicode(16))
    type = Column(Unicode(12))
    status = Column(Boolean)

class ServiceCorrespondence(Base):
    __tablename__ = 'service_pair'
    id = Column(Integer, primary_key=True)    
    desired_id = Column(Integer, ForeignKey('service.id'))
    desired = relation(Service, primaryjoin=desired_id == Service.id)
    incorrect_id = Column(Integer, ForeignKey('service.id'), nullable=True)
    incorrect = relation(Service, primaryjoin=incorrect_id == Service.id)
    modified = Column(Boolean)

service_snap = Table('service_snap', Base.metadata,
                     Column('spair_id', Integer, ForeignKey('service_pair.id')),
                     Column('snapshot_id', Integer, ForeignKey('snapshot.id')))

class File(Base):
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True)        
    name = Column(UnicodeText)
    type = Column(Unicode(12))
    owner = Column(Unicode(12))
    group = Column(Unicode(16))
    perms = Column(Integer(5))
    contents = Column(UnicodeText)

class FileCorrespondence(Base):
    __tablename__ = 'file_pair'
    id = Column(Integer, primary_key=True)    
    desired_id = Column(Integer, ForeignKey('file.id'))
    desired = relation(File, primaryjoin=desired_id == File.id)
    incorrect_id = Column(Integer, ForeignKey('file.id'), nullable=True)
    incorrect = relation(File, primaryjoin=incorrect_id == File.id)
    modified = Column(Boolean)

file_snap = Table('file_snap', Base.metadata,
                  Column('fpair_id', Integer, ForeignKey('file_pair.id')),
                  Column('snapshot_id', Integer, ForeignKey('snapshot.id')))

class Action(Base):
    __tablename__ = 'action'
    id = Column(Integer, primary_key=True)    
    command = Column(UnicodeText)
    return_code = Column(Integer)
    output = Column(UnicodeText)

class Snapshot(Base):
    __tablename__ = 'snapshot'
    id = Column(Integer, primary_key=True)
    metadata_id = Column(Integer, ForeignKey('metadata.id'))
    client_metadata = relation(Metadata, primaryjoin=metadata_id==Metadata.id)
    timestamp = Column(DateTime)
    client_id = Column(Integer, ForeignKey('client.id'))
    client = relation(Client, backref=backref('snapshots', order_by=timestamp))
    packages = relation(PackageCorrespondence, secondary=package_snap)
    services = relation(ServiceCorrespondence, secondary=service_snap)
    files = relation(FileCorrespondence, secondary=file_snap)

engine = create_engine('sqlite:///:memory:', echo=True)
metadata = Base.metadata
metadata.create_all(engine) 
Session = sessionmaker()
Session.configure(bind=engine)
session = Session()
