""" Gamin driver for file alteration events """

import os
import stat
import logging
from gamin import WatchMonitor, GAMCreated, GAMExists, GAMEndExist, \
    GAMChanged, GAMDeleted
from Bcfg2.Server.FileMonitor import Event, FileMonitor

logger = logging.getLogger(__name__)


class GaminEvent(Event):
    """
    This class provides an event analogous to
    python-fam events based on gamin sources.
    """
    action_map = {GAMCreated: 'created', GAMExists: 'exists',
                  GAMChanged: 'changed', GAMDeleted: 'deleted',
                  GAMEndExist: 'endExist'}

    def __init__(self, request_id, filename, code):
        Event.__init__(self, request_id, filename, code)
        if code in self.action_map:
            self.action = self.action_map[code]


class Gamin(FileMonitor):
    __priority__ = 10

    def __init__(self, ignore=None, debug=False):
        FileMonitor.__init__(self, ignore=ignore, debug=debug)
        self.mon = None
        self.counter = 0
        self.add_q = []

    def start(self):
        FileMonitor.start(self)
        self.mon = WatchMonitor()
        for monitor in self.add_q:
            self.AddMonitor(*monitor)
        self.add_q = []

    def fileno(self):
        return self.mon.get_fd()

    def queue(self, path, action, request_id):
        """queue up the event for later handling"""
        self.events.append(GaminEvent(request_id, path, action))

    def AddMonitor(self, path, obj, handle=None):
        """Add a monitor to path, installing a callback to obj."""
        if handle is None:
            handle = self.counter
            self.counter += 1

        if not self.started:
            self.add_q.append((path, obj, handle))
            return handle

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
        return FileMonitor.pending(self) or self.mon.event_pending()

    def get_event(self):
        if self.mon.event_pending():
            self.mon.handle_one_event()
        return FileMonitor.get_event(self)
