from sqlalchemy import Table, Column, Integer, Unicode, MetaData, ForeignKey, Boolean, DateTime, create_engine, UnicodeText

from sqlalchemy.orm import relation, backref
from sqlalchemy.ext.declarative import declarative_base

# TODO add administrators models

Base = declarative_base()

class Administrator(Base):
    __tablename__ = 'administrator'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(20))
    email = Column(Unicode(64))

admin_client = Table('admin_client', Base.metadata,
                     Column('admin_id', Integer, ForeignKey('administrator.id')),
                     Column('client_id', Integer, ForeignKey('client.id')))

class Client(Base):
    __tablename__ = 'client'
    id = Column(Integer, primary_key=True)        
    name = Column(Unicode(64))
    admins = relation("Administrator", secondary=admin_client)
    active = Column(Boolean)

class Group(Base):
    __tablename__ = 'group'
    id = Column(Integer, primary_key=True)        
    name = Column(Unicode(32))

class ConnectorKeyVal(Base):
    __tablename__ = 'connkeyval'
    id = Column(Integer, primary_key=True)    
    connector = Column(Unicode(16))
    key = Column(UnicodeText)
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
    name = Column(Unicode(64))
    groups = relation("Group", secondary=meta_group)
    keyvals = relation(ConnectorKeyVal, secondary=meta_conn)

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
    client = relation(Client, backref=backref('snapshots', order_by=timestamp))
    packages = relation(PackageCorrespondence, secondary=package_snap)
    services = relation(ServiceCorrespondence, secondary=service_snap)
    files = relation(FileCorrespondence, secondary=file_snap)

if __name__ == '__main__':
    engine = create_engine('sqlite:///:memory:', echo=True)
    metadata = Base.metadata
    metadata.create_all(engine) 
