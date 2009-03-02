import lxml.etree
import sqlalchemy
import sqlalchemy.orm
import Bcfg2.Server.Plugin
import Bcfg2.Server.Snapshots
from Bcfg2.Server.Snapshots.model import Snapshot
import time

class Snapshots(Bcfg2.Server.Plugin.Statistics,
                Bcfg2.Server.Plugin.Plugin):
    name = 'Snapshots'
    experimental = True
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Statistics.__init__(self)
        self.session = Bcfg2.Server.Snapshots.db_from_config()

    def process_statistics(self, metadata, data):
        return self.statistics_from_old_stats(metadata, data)

    def statistics_from_old_stats(self, metadata, xdata):
        # entries are name -> (modified, correct, start, desired, end)
        # not sure we can get all of this from old format stats
        t1 = time.time()
        entries = dict([('Package', dict()),
                        ('Service', dict()), ('Path', dict())])
        extra = dict([('Package', list()), ('Service', list()),
                      ('Path', list())])
        for entry in xdata.find('.//Bad'):
            print entry.tag, entry.get('name')
            if entry.tag == 'Package':
                data = [False, False, unicode(entry.get('type')),
                        unicode(entry.get('current_version')),
                        unicode(entry.get('current_version'))]
                entries['Package'][entry.get('name')] = data
        for entry in xdata.find('.//Modified'):
            print entry.tag, entry.get('name')
            if entry.tag == 'Package':
                if entry.get('name') in entries['Package']:
                    entries['Package'][entry.get('name')][0] = True
                else:
                    data = [True, True, unicode(entry.get('type')),
                            unicode(entry.get('current_version')),
                            unicode(entry.get('version'))]
        for entry in xdata.find('.//Extra'):
            if entry.tag == 'Package':
                edata = dict([('name', unicode(entry.get('name'))),
                              ('type', unicode(entry.get('type'))),
                              ('version', unicode(entry.get('version')))]) 
                extra['Package'].append(edata)
        t2 = time.time()
        snap = Snapshot.from_data(self.session, metadata, entries, extra)
        self.session.save(snap)
        self.session.commit()
        t3 = time.time()
        return True
