"""Bcfg2.Server.FileMonitor provides the support for monitoring files."""

import os
import sys
import fnmatch
import logging
from time import sleep, time

LOGGER = logging.getLogger(__name__)


class Event(object):
    """ Base class for all FAM events """
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
        self.started = False

    def __str__(self):
        return "%s: %s" % (__name__, self.__class__.__name__)

    def __repr__(self):
        return "%s (%s events, fd %s)" % (self.__class__.__name__,
                                          len(self.events),
                                          self.fileno())

    def start(self):
        """ start threads or anything else that needs to be done after
        the server forks and daemonizes """
        self.started = True

    def debug_log(self, msg):
        """ log a debug message """
        if self.debug:
            LOGGER.info(msg)

    def should_ignore(self, event):
        """ returns true if an event should be ignored """
        for pattern in self.ignore:
            if (fnmatch.fnmatch(event.filename, pattern) or
                fnmatch.fnmatch(os.path.split(event.filename)[-1], pattern)):
                self.debug_log("Ignoring %s" % event)
                return True
        return False

    def pending(self):
        """ returns True if there are pending events """
        return bool(self.events)

    def get_event(self):
        """ get the oldest pending event """
        return self.events.pop(0)

    def fileno(self):
        """ get the file descriptor of the file monitor thread """
        return 0

    def handle_one_event(self, event):
        """ handle the given event by dispatching it to the object
        that handles events for the path """
        if not self.started:
            self.start()
        if self.should_ignore(event):
            return
        if event.requestID not in self.handles:
            LOGGER.info("Got event for unexpected id %s, file %s" %
                        (event.requestID, event.filename))
            return
        self.debug_log("Dispatching event %s %s to obj %s" %
                       (event.code2str(), event.filename,
                        self.handles[event.requestID]))
        try:
            self.handles[event.requestID].HandleEvent(event)
        except:  # pylint: disable=W0702
            err = sys.exc_info()[1]
            LOGGER.error("Error in handling of event %s for %s: %s" %
                         (event.code2str(), event.filename, err))

    def handle_event_set(self, lock=None):
        """ Handle all pending events """
        if not self.started:
            self.start()
        count = 1
        event = self.get_event()
        start = time()
        if lock:
            lock.acquire()
        self.handle_one_event(event)
        while self.pending():
            self.handle_one_event(self.get_event())
            count += 1
        if lock:
            lock.release()
        end = time()
        LOGGER.info("Handled %d events in %.03fs" % (count, (end - start)))

    def handle_events_in_interval(self, interval):
        """ handle events for the specified period of time (in
        seconds) """
        if not self.started:
            self.start()
        end = time() + interval
        while time() < end:
            if self.pending():
                self.handle_event_set()
                end = time() + interval
            else:
                sleep(0.5)

    def shutdown(self):
        """ shutdown the monitor """
        self.started = False

    def AddMonitor(self, path, obj, handleID=None):
        """ watch the specified path, alerting obj to events """
        raise NotImplementedError


available = dict()  # pylint: disable=C0103

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
