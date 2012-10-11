""" File monitor backend with `Gamin
<http://people.gnome.org/~veillard/gamin/>`_ support. """

import os
import stat
from gamin import WatchMonitor, GAMCreated, GAMExists, GAMEndExist, \
    GAMChanged, GAMDeleted
from Bcfg2.Server.FileMonitor import Event, FileMonitor


class GaminEvent(Event):
    """ This class maps Gamin event constants to FAM :ref:`event codes
    <development-fam-event-codes>`. """

    #: The map of gamin event constants (which mirror FAM event names
    #: closely) to :ref:`event codes <development-fam-event-codes>`
    action_map = {GAMCreated: 'created', GAMExists: 'exists',
                  GAMChanged: 'changed', GAMDeleted: 'deleted',
                  GAMEndExist: 'endExist'}

    def __init__(self, request_id, filename, code):
        Event.__init__(self, request_id, filename, code)
        if code in self.action_map:
            self.action = self.action_map[code]
    __init__.__doc__ = Event.__init__.__doc__


class Gamin(FileMonitor):
    """ File monitor backend with `Gamin
    <http://people.gnome.org/~veillard/gamin/>`_ support. """

    #: The Gamin backend is fairly decent, particularly newer
    #: releases, so it has a fairly high priority.
    __priority__ = 90

    def __init__(self, ignore=None, debug=False):
        FileMonitor.__init__(self, ignore=ignore, debug=debug)

        #: The :class:`Gamin.WatchMonitor` object for this monitor.
        self.mon = None

        #: The counter used to produce monotonically increasing
        #: monitor handle IDs
        self.counter = 0

        #: The queue used to record monitors that are added before
        #: :func:`start` has been called and :attr:`mon` is created.
        self.add_q = []
    __init__.__doc__ = FileMonitor.__init__.__doc__

    def start(self):
        """ The Gamin watch monitor in :attr:`mon` must be created by
        the daemonized process, so is created in ``start()``. Before
        the :class:`Gamin.WatchMonitor` object is created, monitors
        are added to :attr:`add_q`, and are created once the watch
        monitor is created."""
        FileMonitor.start(self)
        self.mon = WatchMonitor()
        for monitor in self.add_q:
            self.AddMonitor(*monitor)
        self.add_q = []

    def fileno(self):
        if self.started:
            return self.mon.get_fd()
        else:
            return None
    fileno.__doc__ = FileMonitor.fileno.__doc__

    def queue(self, path, action, request_id):
        """ Create a new :class:`GaminEvent` and add it to the
        :attr:`events` queue for later handling. """
        self.events.append(GaminEvent(request_id, path, action))

    def AddMonitor(self, path, obj, handle=None):
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
    AddMonitor.__doc__ = FileMonitor.AddMonitor.__doc__

    def pending(self):
        return FileMonitor.pending(self) or self.mon.event_pending()
    pending.__doc__ = FileMonitor.pending.__doc__

    def get_event(self):
        if self.mon.event_pending():
            self.mon.handle_one_event()
        return FileMonitor.get_event(self)
    get_event.__doc__ = FileMonitor.get_event.__doc__
