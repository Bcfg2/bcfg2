import logging
import difflib
import Bcfg2.Server.Plugin
import Bcfg2.Server.Snapshots
import Bcfg2.Logger
from Bcfg2.Server.Snapshots.model import Snapshot
import sys
import time
import threading

# Compatibility import
from Bcfg2.Compat import Queue, u_str, b64decode

logger = logging.getLogger('Snapshots')

ftypes = ['ConfigFile', 'SymLink', 'Directory']
datafields = {
              'Package': ['version'],
              'Path': ['type'],
              'Service': ['status'],
              'ConfigFile': ['owner', 'group', 'mode'],
              'Directory': ['owner', 'group', 'mode'],
              'SymLink': ['to'],
             }


def build_snap_ent(entry):
    basefields = []
    if entry.tag in ['Package', 'Service']:
        basefields += ['type']
    desired = dict([(key, u_str(entry.get(key))) for key in basefields])
    state = dict([(key, u_str(entry.get(key))) for key in basefields])
    desired.update([(key, u_str(entry.get(key))) for key in \
                 datafields[entry.tag]])
    if entry.tag == 'ConfigFile' or \
       ((entry.tag == 'Path') and (entry.get('type') == 'file')):
        if entry.text == None:
            desired['contents'] = None
        else:
            if entry.get('encoding', 'ascii') == 'ascii':
                desired['contents'] = u_str(entry.text)
            else:
                desired['contents'] = u_str(b64decode(entry.text))

        if 'current_bfile' in entry.attrib:
            state['contents'] = u_str(b64decode(entry.get('current_bfile')))
        elif 'current_bdiff' in entry.attrib:
            diff = b64decode(entry.get('current_bdiff'))
            state['contents'] = u_str( \
                '\n'.join(difflib.restore(diff.split('\n'), 1)))

    state.update([(key, u_str(entry.get('current_' + key, entry.get(key)))) \
                  for key in datafields[entry.tag]])
    if entry.tag in ['ConfigFile', 'Path'] and entry.get('exists', 'true') == 'false':
        state = None
    return [desired, state]


class Snapshots(Bcfg2.Server.Plugin.Statistics):
    name = 'Snapshots'
    deprecated = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Statistics.__init__(self, core, datastore)
        self.session = Bcfg2.Server.Snapshots.setup_session(core.cfile)
        self.work_queue = Queue()
        self.loader = threading.Thread(target=self.load_snapshot)

    def start_threads(self):
        self.loader.start()

    def load_snapshot(self):
        while self.running:
            try:
                (metadata, data) = self.work_queue.get(block=True, timeout=5)
            except:
                continue
            self.statistics_from_old_stats(metadata, data)

    def process_statistics(self, metadata, data):
        return self.work_queue.put((metadata, data))

    def statistics_from_old_stats(self, metadata, xdata):
        # entries are name -> (modified, correct, start, desired, end)
        # not sure we can get all of this from old format stats
        t1 = time.time()
        entries = dict([('Package', dict()),
                        ('Service', dict()), ('Path', dict())])
        extra = dict([('Package', dict()), ('Service', dict()),
                      ('Path', dict())])
        bad = []
        state = xdata.find('.//Statistics')
        correct = state.get('state') == 'clean'
        revision = u_str(state.get('revision', '-1'))
        for entry in state.find('.//Bad'):
            data = [False, False, u_str(entry.get('name'))] \
                   + build_snap_ent(entry)
            if entry.tag in ftypes:
                etag = 'Path'
            else:
                etag = entry.tag
            entries[etag][entry.get('name')] = data
        for entry in state.find('.//Modified'):
            if entry.tag in ftypes:
                etag = 'Path'
            else:
                etag = entry.tag
            if entry.get('name') in entries[etag]:
                data = [True, False, u_str(entry.get('name'))] + \
                       build_snap_ent(entry)
            else:
                data = [True, False, u_str(entry.get('name'))] + \
                       build_snap_ent(entry)
        for entry in state.find('.//Extra'):
            if entry.tag in datafields:
                data = build_snap_ent(entry)[1]
                ename = u_str(entry.get('name'))
                data['name'] = ename
                extra[entry.tag][ename] = data
            else:
                print("extra", entry.tag, entry.get('name'))
        t2 = time.time()
        snap = Snapshot.from_data(self.session, correct, revision,
                                  metadata, entries, extra)
        self.session.add(snap)
        self.session.commit()
        t3 = time.time()
        logger.info("Snapshot storage took %fs" % (t3 - t2))
        return True
