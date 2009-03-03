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
        self.session = Bcfg2.Server.Snapshots.setup_session()

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
        pdisp = {'Package': 'version',
                 'Service': 'status'}
        for entry in xdata.find('.//Bad'):
            if entry.tag not in pdisp:
                print "Not Found", entry.tag, entry.get('name')
                continue
            else:
                data = [False, False, unicode(entry.get('type')),
                        unicode(entry.get('%s_%s' % ('current', pdisp[entry.tag]))),
                        unicode(entry.get('%s_%s' % ('current', pdisp[entry.tag])))]
                entries[entry.tag][entry.get('name')] = data
        for entry in xdata.find('.//Modified'):
            if entry.tag in pdisp:
                if entry.get('name') in entries[entry.tag]:
                    entries[entry.tag][entry.get('name')][0] = True
                else:
                    data = [False, False, unicode(entry.get('type')),
                            unicode(entry.get('%s_%s' % ('current', pdisp[entry.tag]))),
                            unicode(entry.get(pdisp[entry.tag]))]
                    entries[entry.tag][entry.get('name')] = data
            else:
                print entry.tag, entry.get('name')
        for entry in xdata.find('.//Extra'):
            if entry.tag in pdisp:
                tname = pdisp[entry.tag]
                data = dict([('name', unicode(entry.get('name'))),
                              ('type', unicode(entry.get('type'))),
                              (tname, unicode(entry.get(tname)))])
            else:
                print "extra", entry.tag, entry.get('name')
        t2 = time.time()
        snap = Snapshot.from_data(self.session, metadata, entries, extra)
        self.session.save(snap)
        self.session.commit()
        t3 = time.time()
        return True
