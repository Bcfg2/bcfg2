from time import time
import logging, os, stat

logger = logging.getLogger('Bcfg2.Server.FileMonitor')

def ShouldIgnore(event):
    '''Test if the event should be suppresed'''
    # FIXME should move event suppression out of the core
    if event.filename.split('/')[-1] == '.svn':
        return True
    if event.filename.endswith('~') or event.filename.endswith('.tmp') \
    or event.filename.startswith('#') or event.filename.startswith('.#'):
        logger.error("Suppressing event for file %s" % (event.filename))
        return True
    return False

class FamFam(object):
    '''The fam object is a set of callbacks for file alteration events (FAM support)'''
    
    def __init__(self):
        object.__init__(self)
        self.fm = _fam.open()
        self.users = {}
        self.handles = {}
        self.debug = False

    def fileno(self):
        '''return fam file handle number'''
        return self.fm.fileno()

    def AddMonitor(self, path, obj):
        '''add a monitor to path, installing a callback to obj.HandleEvent'''
        mode = os.stat(path)[stat.ST_MODE]
        if stat.S_ISDIR(mode):
            handle = self.fm.monitorDirectory(path, None)
        else:
            handle = self.fm.monitorFile(path, None)
        self.handles[handle.requestID()] = handle
        if obj != None:
            self.users[handle.requestID()] = obj
        return handle.requestID()

    def Service(self):
        '''Handle all fam work'''
        count = 0
        collapsed = 0
        rawevents = []
        start = time()
        now = time()
        while (time() - now) < 0.10:
            if self.fm.pending():
                while self.fm.pending():
                    count += 1
                    rawevents.append(self.fm.nextEvent())
                now = time()
        unique = []
        bookkeeping = []
        for event in rawevents:
            if ShouldIgnore(event):
                continue
            if event.code2str() != 'changed':
                # process all non-change events
                unique.append(event)
            else:
                if (event.filename, event.requestID) not in bookkeeping:
                    bookkeeping.append((event.filename, event.requestID))
                    unique.append(event)
                else:
                    collapsed += 1
        for event in unique:
            if self.users.has_key(event.requestID):
                try:
                    self.users[event.requestID].HandleEvent(event)
                except:
                    logger.error("handling event for file %s" % (event.filename), exc_info=1)
        end = time()
        logger.info("Processed %s fam events in %03.03f seconds. %s coalesced" %
                    (count, (end - start), collapsed))
        return count

class Event(object):
    def __init(self, request_id, filename, code):
        self.requestID = request_id
        self.filename = filename
        self.action = code

    def code2str(self):
        '''return static code for event'''
        return self.action


class GaminEvent(Event):
    '''This class provides an event analogous to python-fam events based on gamin sources'''
    def __init__(self, request_id, filename, code):
        Event.__init__(self, request_id, filename, code)
        action_map = {GAMCreated: 'created', GAMExists: 'exists', GAMChanged: 'changed',
                      GAMDeleted: 'deleted', GAMEndExist: 'endExist', GAMMoved: 'moved'}
        if action_map.has_key(code):
            self.action = action_map[code]

class GaminFam(object):
    '''The fam object is a set of callbacks for file alteration events (Gamin support)'''
    def __init__(self):
        object.__init__(self)
        self.mon = WatchMonitor()
        self.handles = {}
        self.counter = 0
        self.events = []
        self.debug = False

    def fileno(self):
        '''return fam file handle number'''
        return self.mon.get_fd()

    def queue(self, path, action, request_id):
        '''queue up the event for later handling'''
        self.events.append(GaminEvent(request_id, path, action))

    def AddMonitor(self, path, obj):
        '''add a monitor to path, installing a callback to obj.HandleEvent'''
        handle = self.counter
        self.counter += 1
        mode = os.stat(path)[stat.ST_MODE]
        if stat.S_ISDIR(mode):
            self.mon.watch_directory(path, self.queue, handle)
        else:
            self.mon.watch_file(path, self.queue, handle)
        self.handles[handle] = obj
        return handle

    def Service(self):
        '''Handle all gamin work'''
        count = 0
        collapsed = 0
        start = time()
        now = time()
        while (time() - now) < 0.10:
            if self.mon.event_pending():
                while self.mon.event_pending():
                    count += 1
                    self.mon.handle_one_event()
                now = time()
        unique = []
        bookkeeping = []
        for event in self.events:
            if ShouldIgnore(event):
                continue
            if event.code2str() != 'changed':
                # process all non-change events
                unique.append(event)
            else:
                if (event.filename, event.requestID) not in bookkeeping:
                    bookkeeping.append((event.filename, event.requestID))
                    unique.append(event)
                else:
                    collapsed += 1
        self.events = []
        for event in unique:
            if event.requestID not in self.handles:
                logger.info("Got event for unexpected id %s, file %s" %
                            (event.requestID, event.filename))
                continue
            if self.debug:
                logger.info("Dispatching event %s %s to obj %s" \
                            % (event.code2str(), event.filename,
                               self.handles[event.requestID]))
            try:
                self.handles[event.requestID].HandleEvent(event)
            except:
                logger.error("error in handling of gamin event for %s" % \
                             (event.filename), exc_info=1)
        end = time()
        logger.info("Processed %s gamin events in %03.03f seconds. %s collapsed" %
                    (count, (end - start), collapsed))
        return count

class PseudoFam(object):
    '''The fam object is a set of callbacks for file alteration events (FAM support)'''
    
    def __init__(self):
        object.__init__(self)
        self.users = {}
        self.handles = {}
        self.debug = False
        self.pending = []

    def AddMonitor(self, path, obj):
        '''add a monitor to path, installing a callback to obj.HandleEvent'''
        handleID = len(self.handles.keys())
        mode = os.stat(path)[stat.ST_MODE]
        handle = GaminEvent(handleID, path, 'exists')
        if stat.S_ISDIR(mode):
            dirList = os.listdir(path)
            self.pending.append(handle)
            for includedFile in dirList:
                self.pending.append(GaminEvent(handleID, includedFile, 'exists'))
            self.pending.append(GaminEvent(handleID, path, 'endExist'))
        else:
            self.pending.append(GaminEvent(handleID, path, 'exists'))
        self.handles[handleID] = handle
        if obj != None:
            self.users[handleID] = obj
        return handleID

    def Service(self):
        '''Handle all fam work'''
        count = 0
        rawevents = []
        for event in self.pending:
            count += 1
            rawevents.append(event)
        self.pending = []
        for event in rawevents:
            if self.users.has_key(event.requestID):
                self.users[event.requestID].HandleEvent(event)
        return count
        
available = {}
try:
    from gamin import WatchMonitor, GAMCreated, GAMExists, GAMEndExist, GAMChanged, GAMDeleted, GAMMoved
    available['gamin'] = GaminFam
except ImportError:
    # fall back to _fam
    pass
try:
    import _fam
    available['fam'] = FamFam
except ImportError:
    pass
available['pseudo'] = PseudoFam

for fdrv in ['gamin', 'fam', 'pseudo']:
    if fdrv in available:
        default = available[fdrv]
        break
