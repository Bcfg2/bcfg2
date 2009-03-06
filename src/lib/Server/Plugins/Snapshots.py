import lxml.etree
import binascii
import difflib
import sqlalchemy
import sqlalchemy.orm
import Bcfg2.Server.Plugin
import Bcfg2.Server.Snapshots
from Bcfg2.Server.Snapshots.model import Snapshot
import time

ftypes = ['ConfigFile', 'SymLink', 'Directory']
datafields = {'Package': ['version'],
              'Service': ['status'],
              'ConfigFile': ['owner', 'group', 'perms']}

def build_snap_ent(entry):
    basefields = []
    if entry.tag in ['Package', 'Service']:
        basefields += ['type']
    desired = dict([(key, unicode(entry.get(key))) for key in basefields])
    state = dict([(key, unicode(entry.get(key))) for key in basefields])
    desired.update([(key, unicode(entry.get(key))) for key in \
                 datafields[entry.tag]])
    if entry.tag == 'ConfigFile':
        if entry.text == None:
            desired['contents'] = None
        else:
            if entry.get('encoding', 'ascii') == 'ascii':
                desired['contents'] = unicode(entry.text)
            else:
                desired['contents'] = unicode(binascii.a2b_base64(entry.text))

        if 'current_bfile' in entry.attrib:
            state['contents'] = unicode(binascii.a2b_base64( \
                entry.get('current_bfile')))
        elif 'current_bdiff' in entry.attrib:
            diff = binascii.a2b_base64(entry.get('current_bdiff'))
            state['contents'] = unicode( \
                '\n'.join(difflib.restore(diff.split('\n'), 1)))
                             
    state.update([(key, unicode(entry.get('current_' + key, entry.get(key)))) \
                  for key in datafields[entry.tag]])
    if entry.tag == 'ConfigFile' and entry.get('exists', 'true') == 'false':
        state = None
    return [desired, state]

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
        extra = dict([('Package', dict()), ('Service', dict()),
                      ('Path', dict())])
        bad = []
        for entry in xdata.find('.//Bad'):
            data = [False, False, unicode(entry.get('name'))] \
                   + build_snap_ent(entry)
            if entry.tag in ftypes:
                etag = 'Path'
            else:
                etag = entry.tag
            entries[etag][entry.get('name')] = data
        for entry in xdata.find('.//Modified'):
            if entry.tag in ftypes:
                etag = 'Path'
            else:
                etag = entry.tag
            if entry.get('name') in entries[etag]:
                data = [True, False, unicode(entry.get('name'))] + \
                       build_snap_ent(entry)
            else:
                data = [True, False, unicode(entry.get('name'))] + \
                       build_snap_ent(entry)
        for entry in xdata.find('.//Extra'):
            if entry.tag in datafields:
                current = dict([(key, unicode(entry.get(key))) \
                                for key in datafields[entry.tag]])
                extra[entry.tag][unicode(entry.get('name'))] = current
            else:
                print "extra", entry.tag, entry.get('name')
        t2 = time.time()
        snap = Snapshot.from_data(self.session, metadata, entries, extra)
        self.session.add(snap)
        self.session.commit()
        t3 = time.time()
        print "Storage took", t3-t2
        return True
