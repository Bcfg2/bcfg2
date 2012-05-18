""" Fam provides FAM support for file alteration events """

import os
import _fam
import stat
import logging
from time import time
from Bcfg2.Server.FileMonitor import FileMonitor

logger = logging.getLogger(__name__)

class Fam(FileMonitor):
    __priority__ = 90

    def __init__(self, ignore=None, debug=False):
        FileMonitor.__init__(self, ignore=ignore, debug=debug)
        self.fm = _fam.open()
        self.users = {}

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
            if self.should_ignore(event):
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
                    logger.error("Handling event for file %s" % event.filename,
                                 exc_info=1)
        end = time()
        logger.info("Processed %s fam events in %03.03f seconds. %s coalesced" %
                    (count, (end - start), collapsed))
        return count
