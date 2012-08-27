import sys
from sqlalchemy import Table, Column, Integer, Unicode, ForeignKey, Boolean, \
                       DateTime, UnicodeText, desc
import datetime
import sqlalchemy.exceptions
from sqlalchemy.orm import relation, backref
from sqlalchemy.ext.declarative import declarative_base

from Bcfg2.Compat import u_str


class Uniquer(object):
    force_rt = True

    @classmethod
    def by_value(cls, session, **kwargs):
        if cls.force_rt:
            try:
                return session.query(cls).filter_by(**kwargs).one()
            except sqlalchemy.exceptions.InvalidRequestError:
                return cls(**kwargs)
        else:
            return cls(**kwargs)

    @classmethod
    def from_record(cls, session, data):
        return cls.by_value(session, **data)

Base = declarative_base()


class Administrator(Uniquer, Base):
    __tablename__ = 'administrator'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(20), unique=True)
    email = Column(Unicode(64))

admin_client = Table('admin_client', Base.metadata,
                     Column('admin_id',
                            Integer,
                            ForeignKey('administrator.id')),
                     Column('client_id',
                            Integer,
                            ForeignKey('client.id')))

admin_group = Table('admin_group', Base.metadata,
                    Column('admin_id',
                           Integer,
                           ForeignKey('administrator.id')),
                    Column('group_id',
                           Integer,
                           ForeignKey('group.id')))


class Client(Uniquer, Base):
    __tablename__ = 'client'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(64), unique=True)
    admins = relation("Administrator", secondary=admin_client,
                      backref='clients')
    active = Column(Boolean, default=True)
    online = Column(Boolean, default=True)
    online_ts = Column(DateTime)


class Group(Uniquer, Base):
    __tablename__ = 'group'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(32), unique=True)
    admins = relation("Administrator", secondary=admin_group,
                      backref='groups')


class ConnectorKeyVal(Uniquer, Base):
    __tablename__ = 'connkeyval'
    id = Column(Integer, primary_key=True)
    connector = Column(Unicode(16))
    key = Column(Unicode(32))
    value = Column(UnicodeText)

meta_group = Table('meta_group', Base.metadata,
                   Column('metadata_id',
                          Integer,
                          ForeignKey('metadata.id')),
                   Column('group_id',
                          Integer,
                          ForeignKey('group.id')))

meta_conn = Table('meta_conn', Base.metadata,
                  Column('metadata_id',
                         Integer,
                         ForeignKey('metadata.id')),
                  Column('connkeyval_id',
                         Integer,
                         ForeignKey('connkeyval.id')))


class Metadata(Base):
    __tablename__ = 'metadata'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('client.id'))
    client = relation(Client)
    groups = relation("Group", secondary=meta_group)
    keyvals = relation(ConnectorKeyVal, secondary=meta_conn)
    timestamp = Column(DateTime)

    @classmethod
    def from_metadata(cls, mysession, mymetadata):
        client = Client.by_value(mysession, name=u_str(mymetadata.hostname))
        m = cls(client=client)
        for group in mymetadata.groups:
            m.groups.append(Group.by_value(mysession, name=u_str(group)))
        for connector in mymetadata.connectors:
            data = getattr(mymetadata, connector)
            if not isinstance(data, dict):
                continue
            for key, value in list(data.items()):
                if not isinstance(value, str):
                    continue
                m.keyvals.append(ConnectorKeyVal.by_value(mysession,
                                                          connector=u_str(connector),
                                                          key=u_str(key),
                                                          value=u_str(value)))
        return m


class Package(Base, Uniquer):
    __tablename__ = 'package'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(24))
    type = Column(Unicode(16))
    version = Column(Unicode(16))
    verification_status = Column(Boolean)


class CorrespondenceType(object):
    mtype = Package

    @classmethod
    def from_record(cls, mysession, record):
        (mod, corr, name, s_dict, e_dict) = record
        if not s_dict:
            start = None
        else:
            start = cls.mtype.by_value(mysession, name=name, **s_dict)
        if s_dict != e_dict:
            end = cls.mtype.by_value(mysession, name=name, **e_dict)
        else:
            end = start
        return cls(start=start, end=end, modified=mod, correct=corr)


class PackageCorrespondence(Base, CorrespondenceType):
    mtype = Package
    __tablename__ = 'package_pair'
    id = Column(Integer, primary_key=True)
    start_id = Column(Integer, ForeignKey('package.id'))
    start = relation(Package, primaryjoin=start_id == Package.id)
    end_id = Column(Integer, ForeignKey('package.id'), nullable=True)
    end = relation(Package, primaryjoin=end_id == Package.id)
    modified = Column(Boolean)
    correct = Column(Boolean)

package_snap = Table('package_snap', Base.metadata,
                     Column('ppair_id',
                            Integer,
                            ForeignKey('package_pair.id')),
                     Column('snapshot_id',
                            Integer,
                            ForeignKey('snapshot.id')))


class Service(Base, Uniquer):
    __tablename__ = 'service'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(16))
    type = Column(Unicode(12))
    status = Column(Boolean)


class ServiceCorrespondence(Base, CorrespondenceType):
    mtype = Service
    __tablename__ = 'service_pair'
    id = Column(Integer, primary_key=True)
    start_id = Column(Integer, ForeignKey('service.id'))
    start = relation(Service, primaryjoin=start_id == Service.id)
    end_id = Column(Integer, ForeignKey('service.id'), nullable=True)
    end = relation(Service, primaryjoin=end_id == Service.id)
    modified = Column(Boolean)
    correct = Column(Boolean)

service_snap = Table('service_snap', Base.metadata,
                     Column('spair_id',
                            Integer,
                            ForeignKey('service_pair.id')),
                     Column('snapshot_id',
                            Integer,
                            ForeignKey('snapshot.id')))


class File(Base, Uniquer):
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    type = Column(Unicode(12))
    owner = Column(Unicode(12))
    group = Column(Unicode(16))
    perms = Column(Integer)
    contents = Column(UnicodeText)


class FileCorrespondence(Base, CorrespondenceType):
    mtype = File
    __tablename__ = 'file_pair'
    id = Column(Integer, primary_key=True)
    start_id = Column(Integer, ForeignKey('file.id'))
    start = relation(File, primaryjoin=start_id == File.id)
    end_id = Column(Integer, ForeignKey('file.id'), nullable=True)
    end = relation(File, primaryjoin=end_id == File.id)
    modified = Column(Boolean)
    correct = Column(Boolean)

file_snap = Table('file_snap', Base.metadata,
                  Column('fpair_id',
                         Integer,
                         ForeignKey('file_pair.id')),
                  Column('snapshot_id',
                         Integer,
                         ForeignKey('snapshot.id')))

extra_pkg_snap = Table('extra_pkg_snap', Base.metadata,
                       Column('package_id',
                              Integer,
                              ForeignKey('package.id')),
                       Column('snapshot_id',
                              Integer,
                              ForeignKey('snapshot.id')))

extra_file_snap = Table('extra_file_snap', Base.metadata,
                       Column('file_id',
                              Integer,
                              ForeignKey('file.id')),
                       Column('snapshot_id',
                              Integer,
                              ForeignKey('snapshot.id')))

extra_service_snap = Table('extra_service_snap', Base.metadata,
                       Column('service_id',
                              Integer,
                              ForeignKey('service.id')),
                       Column('snapshot_id',
                              Integer,
                              ForeignKey('snapshot.id')))


class Action(Base):
    __tablename__ = 'action'
    id = Column(Integer, primary_key=True)
    command = Column(UnicodeText)
    return_code = Column(Integer)
    output = Column(UnicodeText)

action_snap = Table('action_snap', Base.metadata,
                    Column('action_id', Integer, ForeignKey('action.id')),
                    Column('snapshot_id', Integer, ForeignKey('snapshot.id')))


class Snapshot(Base):
    __tablename__ = 'snapshot'
    id = Column(Integer, primary_key=True)
    correct = Column(Boolean)
    revision = Column(Unicode(36))
    metadata_id = Column(Integer, ForeignKey('metadata.id'))
    client_metadata = relation(Metadata, primaryjoin=metadata_id == Metadata.id)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    client_id = Column(Integer, ForeignKey('client.id'))
    client = relation(Client, backref=backref('snapshots'))
    packages = relation(PackageCorrespondence, secondary=package_snap)
    services = relation(ServiceCorrespondence, secondary=service_snap)
    files = relation(FileCorrespondence, secondary=file_snap)
    actions = relation(Action, secondary=action_snap)
    extra_packages = relation(Package, secondary=extra_pkg_snap)
    extra_services = relation(Service, secondary=extra_service_snap)
    extra_files = relation(File, secondary=extra_file_snap)

    c_dispatch = dict([('Package', ('packages', PackageCorrespondence)),
                       ('Service', ('services', ServiceCorrespondence)),
                       ('Path', ('files', FileCorrespondence))])
    e_dispatch = dict([('Package', ('extra_packages', Package)),
                       ('Service', ('extra_services', Service)),
                       ('Path', ('extra_files', File))])

    @classmethod
    def from_data(cls, session, correct, revision, metadata, entries, extra):
        dbm = Metadata.from_metadata(session, metadata)
        snap = cls(correct=correct, client_metadata=dbm, revision=revision,
                   timestamp=datetime.datetime.now(), client=dbm.client)
        for (dispatch, data) in [(cls.c_dispatch, entries),
                                 (cls.e_dispatch, extra)]:
            for key in dispatch:
                dest, ecls = dispatch[key]
                for edata in list(data[key].values()):
                    getattr(snap, dest).append(ecls.from_record(session, edata))
        return snap

    @classmethod
    def by_client(cls, session, clientname):
        return session.query(cls).join(cls.client_metadata,
                                       Metadata.client).filter(Client.name == clientname)

    @classmethod
    def get_current(cls, session, clientname):
        return session.query(Snapshot).join(Snapshot.client_metadata,
                                            Metadata.client).filter(Client.name == clientname).order_by(desc(Snapshot.timestamp)).first()

    @classmethod
    def get_by_date(cls, session, clientname, timestamp):
        return session.query(Snapshot)\
                      .join(Snapshot.client_metadata, Metadata.client)\
                      .filter(Snapshot.timestamp < timestamp)\
                      .filter(Client.name == clientname)\
                      .order_by(desc(Snapshot.timestamp))\
                      .first()
