""" File monitor backend with support for the `File Alteration Monitor
<http://oss.sgi.com/projects/fam/>`_.  The FAM backend is deprecated. """

import os
import _fam
import stat
import logging
from time import time
from Bcfg2.Server.FileMonitor import FileMonitor

LOGGER = logging.getLogger(__name__)


class Fam(FileMonitor):
    """ **Deprecated** file monitor backend with support for the `File
    Alteration Monitor <http://oss.sgi.com/projects/fam/>`_ (also
    abbreviated "FAM")."""

    #: FAM is the worst actual monitor backend, so give it a low
    #: priority.
    __priority__ = 10

    def __init__(self, ignore=None, debug=False):
        FileMonitor.__init__(self, ignore=ignore, debug=debug)
        self.filemonitor = _fam.open()
        self.users = {}
        LOGGER.warning("The Fam file monitor backend is deprecated. Please "
                       "switch to a supported file monitor.")
    __init__.__doc__ = FileMonitor.__init__.__doc__

    def fileno(self):
        return self.filemonitor.fileno()
    fileno.__doc__ = FileMonitor.fileno.__doc__

    def handle_event_set(self, _=None):
        self.Service()
    handle_event_set.__doc__ = FileMonitor.handle_event_set.__doc__

    def handle_events_in_interval(self, interval):
        now = time()
        while (time() - now) < interval:
            if self.Service():
                now = time()
    handle_events_in_interval.__doc__ = \
        FileMonitor.handle_events_in_interval.__doc__

    def AddMonitor(self, path, obj, _=None):
        mode = os.stat(path)[stat.ST_MODE]
        if stat.S_ISDIR(mode):
            handle = self.filemonitor.monitorDirectory(path, None)
        else:
            handle = self.filemonitor.monitorFile(path, None)
        self.handles[handle.requestID()] = handle
        if obj is not None:
            self.users[handle.requestID()] = obj
        return handle.requestID()
    AddMonitor.__doc__ = FileMonitor.AddMonitor.__doc__

    def Service(self, interval=0.50):
        """ Handle events for the specified period of time (in
        seconds).  This call will block for ``interval`` seconds.

        :param interval: The interval, in seconds, during which events
                         should be handled.  Any events that are
                         already pending when :func:`Service` is
                         called will also be handled.
        :type interval: int
        :returns: None
        """
        count = 0
        collapsed = 0
        rawevents = []
        start = time()
        now = time()
        while (time() - now) < interval:
            if self.filemonitor.pending():
                while self.filemonitor.pending():
                    count += 1
                    rawevents.append(self.filemonitor.nextEvent())
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
                except:  # pylint: disable=W0702
                    LOGGER.error("Handling event for file %s" % event.filename,
                                 exc_info=1)
        end = time()
        LOGGER.info("Processed %s fam events in %03.03f seconds. "
                    "%s coalesced" % (count, (end - start), collapsed))
        return count
