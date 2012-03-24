"""Bcfg2.Server.FileMonitor provides the support for monitorung files."""

import logging
import os
import stat
from time import sleep, time

logger = logging.getLogger('Bcfg2.Server.FileMonitor')


def ShouldIgnore(event):
    """Test if the event should be suppresed."""
    # FIXME should move event suppression out of the core
    if event.filename.split('/')[-1] == '.svn':
        return True
    if event.filename.endswith('~') or \
           event.filename.startswith('#') or event.filename.startswith('.#'):
        #logger.error("Suppressing event for file %s" % (event.filename))
        return True
    return False


class Event(object):
    def __init__(self, request_id, filename, code):
        self.requestID = request_id
        self.filename = filename
        self.action = code

    def code2str(self):
        """return static code for event"""
        return self.action

available = {}


class FileMonitor(object):
    """File Monitor baseclass."""
    def __init__(self, debug=False):
        object.__init__(self)
        self.debug = debug
        self.handles = dict()

    def get_event(self):
        return None

    def pending(self):
        return False

    def fileno(self):
        return 0

    def handle_one_event(self, event):
        if ShouldIgnore(event):
            return
        if event.requestID not in self.handles:
            logger.info("Got event for unexpected id %s, file %s" %
                        (event.requestID, event.filename))
            return
        if self.debug:
            logger.info("Dispatching event %s %s to obj %s" \
                        % (event.code2str(), event.filename,
                           self.handles[event.requestID]))
        try:
            self.handles[event.requestID].HandleEvent(event)
        except:
            logger.error("error in handling of gamin event for %s" % \
                         (event.filename), exc_info=1)

    def handle_event_set(self, lock=None):
        count = 1
        event = self.get_event()
        start = time()
        if lock:
            lock.acquire()
        try:
            self.handle_one_event(event)
            while self.pending():
                self.handle_one_event(self.get_event())
                count += 1
        except:
            pass
        if lock:
            lock.release()
        end = time()
        logger.info("Handled %d events in %.03fs" % (count, (end - start)))

    def handle_events_in_interval(self, interval):
        end = time() + interval
        while time() < end:
            if self.pending():
                self.handle_event_set()
                end = time() + interval
            else:
                sleep(0.5)


class FamFam(object):
    """The fam object is a set of callbacks for
    file alteration events (FAM support).
    """

    def __init__(self):
        object.__init__(self)
        self.fm = _fam.open()
        self.users = {}
        self.handles = {}
        self.debug = False

    def fileno(self):
        """Return fam file handle number."""
        return self.fm.fileno()

    def handle_event_set(self, _):
        self.Service()

    def handle_events_in_interval(self, interval):
        now = time()
        while (time() - now) < interval:
            if self.Service():
                now = time()

    def AddMonitor(self, path, obj):
        """Add a monitor to path, installing a callback to obj.HandleEvent."""
        mode = os.stat(path)[stat.ST_MODE]
        if stat.S_ISDIR(mode):
            handle = self.fm.monitorDirectory(path, None)
        else:
            handle = self.fm.monitorFile(path, None)
        self.handles[handle.requestID()] = handle
        if obj != None:
            self.users[handle.requestID()] = obj
        return handle.requestID()

    def Service(self, interval=0.50):
        """Handle all fam work."""
        count = 0
        collapsed = 0
        rawevents = []
        start = time()
        now = time()
        while (time() - now) < interval:
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
            if event.requestID in self.users:
                try:
                    self.users[event.requestID].HandleEvent(event)
                except:
                    logger.error("handling event for file %s" % (event.filename), exc_info=1)
        end = time()
        logger.info("Processed %s fam events in %03.03f seconds. %s coalesced" %
                    (count, (end - start), collapsed))
        return count


class Fam(FileMonitor):
    """
       The fam object is a set of callbacks for
       file alteration events (FAM support).
    """

    def __init__(self, debug=False):
        FileMonitor.__init__(self, debug)
        self.fm = _fam.open()

    def fileno(self):
        return self.fm.fileno()

    def AddMonitor(self, path, obj):
        """Add a monitor to path, installing a callback to obj.HandleEvent."""
        mode = os.stat(path)[stat.ST_MODE]
        if stat.S_ISDIR(mode):
            handle = self.fm.monitorDirectory(path, None)
        else:
            handle = self.fm.monitorFile(path, None)
        if obj != None:
            self.handles[handle.requestID()] = obj
        return handle.requestID()

    def pending(self):
        return self.fm.pending()

    def get_event(self):
        return self.fm.nextEvent()


class Pseudo(FileMonitor):
    """
       The fam object is a set of callbacks for
       file alteration events (static monitor support).
    """

    def __init__(self, debug=False):
        FileMonitor.__init__(self, debug=False)
        self.pending_events = []

    def pending(self):
        return len(self.pending_events) != 0

    def get_event(self):
        return self.pending_events.pop()

    def AddMonitor(self, path, obj):
        """add a monitor to path, installing a callback to obj.HandleEvent"""
        handleID = len(list(self.handles.keys()))
        mode = os.stat(path)[stat.ST_MODE]
        handle = Event(handleID, path, 'exists')
        if stat.S_ISDIR(mode):
            dirList = os.listdir(path)
            self.pending_events.append(handle)
            for includedFile in dirList:
                self.pending_events.append(Event(handleID,
                                                 includedFile,
                                                 'exists'))
            self.pending_events.append(Event(handleID, path, 'endExist'))
        else:
            self.pending_events.append(Event(handleID, path, 'exists'))
        if obj != None:
            self.handles[handleID] = obj
        return handleID


try:
    from gamin import WatchMonitor, GAMCreated, GAMExists, GAMEndExist, \
                      GAMChanged, GAMDeleted, GAMMoved

    class GaminEvent(Event):
        """
        This class provides an event analogous to
        python-fam events based on gamin sources.
        """
        def __init__(self, request_id, filename, code):
            Event.__init__(self, request_id, filename, code)
            action_map = {GAMCreated: 'created', GAMExists: 'exists',
                          GAMChanged: 'changed', GAMDeleted: 'deleted',
                          GAMEndExist: 'endExist', GAMMoved: 'moved'}
            if code in action_map:
                self.action = action_map[code]

    class Gamin(FileMonitor):
        """
        The fam object is a set of callbacks for
        file alteration events (Gamin support)
        """
        def __init__(self, debug=False):
            FileMonitor.__init__(self, debug)
            self.mon = WatchMonitor()
            self.counter = 0
            self.events = []

        def fileno(self):
            return self.mon.get_fd()

        def queue(self, path, action, request_id):
            """queue up the event for later handling"""
            self.events.append(GaminEvent(request_id, path, action))

        def AddMonitor(self, path, obj):
            """Add a monitor to path, installing a callback to obj.HandleEvent."""
            handle = self.counter
            self.counter += 1
            mode = os.stat(path)[stat.ST_MODE]

            # Flush queued gamin events
            while self.mon.event_pending():
                self.mon.handle_one_event()

            if stat.S_ISDIR(mode):
                self.mon.watch_directory(path, self.queue, handle)
            else:
                self.mon.watch_file(path, self.queue, handle)
            self.handles[handle] = obj
            return handle

        def pending(self):
            return len(self.events) > 0 or self.mon.event_pending()

        def get_event(self):
            if self.mon.event_pending():
                self.mon.handle_one_event()
            return self.events.pop(0)

    available['gamin'] = Gamin
except ImportError:
    # fall back to _fam
    pass

try:
    import _fam
    available['fam'] = FamFam
except ImportError:
    pass
available['pseudo'] = Pseudo

for fdrv in ['gamin', 'fam', 'pseudo']:
    if fdrv in available:
        available['default'] = available[fdrv]
        break
