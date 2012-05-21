"""Bcfg2.Server.FileMonitor provides the support for monitoring files."""

import os
import fnmatch
import logging
import pkgutil
from time import sleep, time

logger = logging.getLogger(__name__)

class Event(object):
    def __init__(self, request_id, filename, code):
        self.requestID = request_id
        self.filename = filename
        self.action = code

    def code2str(self):
        """return static code for event"""
        return self.action

    def __str__(self):
        return "%s: %s %s" % (self.__class__.__name__,
                              self.filename, self.action)

    def __repr__(self):
        return "%s (request ID %s)" % (str(self), self.requestID)


class FileMonitor(object):
    """File Monitor baseclass."""
    def __init__(self, ignore=None, debug=False):
        object.__init__(self)
        self.debug = debug
        self.handles = dict()
        self.events = []
        if ignore is None:
            ignore = []
        self.ignore = ignore

    def __str__(self):
        return "%s: %s" % (__name__, self.__class__.__name__)

    def __repr__(self):
        return "%s (%s events, fd %s)" % (str(self), len(events), self.fileno)

    def should_ignore(self, event):
        for pattern in self.ignore:
            if (fnmatch.fnmatch(event.filename, pattern) or 
                fnmatch.fnmatch(os.path.split(event.filename)[-1], pattern)):
                if self.debug:
                    logger.info("Ignoring %s" % event)
                return True
        return False

    def pending(self):
        return bool(self.events)

    def get_event(self):
        return self.events.pop(0)

    def fileno(self):
        return 0

    def handle_one_event(self, event):
        if self.should_ignore(event):
            return
        if event.requestID not in self.handles:
            logger.info("Got event for unexpected id %s, file %s" %
                        (event.requestID, event.filename))
            return
        if self.debug:
            logger.info("Dispatching event %s %s to obj %s" %
                        (event.code2str(), event.filename,
                         self.handles[event.requestID]))
        try:
            self.handles[event.requestID].HandleEvent(event)
        except:
            logger.error("Error in handling of event for %s" %
                         event.filename, exc_info=1)

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

    def shutdown(self):
        pass


available = dict()

# todo: loading the monitor drivers should be automatic
from Bcfg2.Server.FileMonitor.Pseudo import Pseudo
available['pseudo'] = Pseudo

try:
    from Bcfg2.Server.FileMonitor.Fam import Fam
    available['fam'] = Fam
except ImportError:
    pass

try:
    from Bcfg2.Server.FileMonitor.Gamin import Gamin
    available['gamin'] = Gamin
except ImportError:
    pass

try:
    from Bcfg2.Server.FileMonitor.Inotify import Inotify
    available['inotify'] = Inotify
except ImportError:
    pass    

for fdrv in sorted(available.keys(), key=lambda k: available[k].__priority__):
    if fdrv in available:
        available['default'] = available[fdrv]
        break
