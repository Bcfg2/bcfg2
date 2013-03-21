""" Bcfg2.Server.FileMonitor provides the support for monitoring
files.  The FAM acts as a dispatcher for events: An event is detected
on a file (e.g., the file content is changed), and then that event is
dispatched to the ``HandleEvent`` method of an object that knows how
to handle the event.  Consequently,
:func:`Bcfg2.Server.FileMonitor.FileMonitor.AddMonitor` takes two
arguments: the path to monitor, and the object that handles events
detected on that event.

``HandleEvent`` is called with a single argument, the
:class:`Bcfg2.Server.FileMonitor.Event` object to be handled.

Assumptions
-----------

The FAM API Bcfg2 uses is based on the API of SGI's `File Alteration
Monitor <http://oss.sgi.com/projects/fam/>`_ (also called "FAM").
Consequently, a few assumptions apply:

* When a file or directory is monitored for changes, we call that a
  "monitor"; other backends my use the term "watch," but for
  consistency we will use "monitor."
* Monitors can be set on files or directories.
* A monitor set on a directory monitors all files within that
  directory, non-recursively.  If the object that requested the
  monitor wishes to monitor recursively, it must implement that
  itself.
* Setting a monitor immediately produces "exists" and "endExist"
  events for the monitored file or directory and all files or
  directories contained within it (non-recursively).
* An event on a file or directory that is monitored directly yields
  the full path to the file or directory.
* An event on a file or directory that is *only* contained within a
  monitored directory yields the relative path to the file or
  directory within the monitored parent.  It is the responsibility of
  the handler to reconstruct full paths as necessary.
* Each monitor that is set must have a unique ID that identifies it,
  in order to make it possible to reconstruct full paths as
  necessary.  This ID will be stored in
  :attr:`Bcfg2.Server.FileMonitor.FileMonitor.handles`.  It may be any
  hashable value; some FAM backends use monotonically increasing
  integers, while others use the path to the monitor.

Base Classes
------------
"""

import os
import sys
import fnmatch
import logging
from time import sleep, time
from Bcfg2.Server.Plugin import Debuggable

LOGGER = logging.getLogger(__name__)


class Event(object):
    """ Base class for all FAM events. """

    def __init__(self, request_id, filename, code):
        """
        :param request_id: The handler ID of the monitor that produced
                           this event
        :type request_id: Varies
        :param filename: The file or directory on which the event was
                         detected. An event on a file or directory
                         that is monitored directly yields the full
                         path to the file or directory; an event on a
                         file or directory that is *only* contained
                         within a monitored directory yields the
                         relative path to the file or directory within
                         the monitored parent.
        :type filename: string
        :param code: The :ref:`event code
                     <development-fam-event-codes>` produced.  I.e.,
                     the type of event.
        :type code: string
        """
        #: The handler ID of the monitor that produced this event
        self.requestID = request_id

        #: The file or directory on which the event was detected. An
        #: event on a file or directory that is monitored directly
        #: yields the full path to the file or directory; an event on
        #: a file or directory that is *only* contained within a
        #: monitored directory yields the relative path to the file or
        #: directory within the monitored parent.
        self.filename = filename

        #: The :ref:`event code <development-fam-event-codes>`
        #: produced.  I.e., the type of event.
        self.action = code

    def code2str(self):
        """ Return the :ref:`event code <development-fam-event-codes>`
        for this event.  This is just an alias for :attr:`action`. """
        return self.action

    def __str__(self):
        return "%s: %s %s" % (self.__class__.__name__,
                              self.filename, self.action)

    def __repr__(self):
        return "%s (request ID %s)" % (str(self), self.requestID)


class FileMonitor(Debuggable):
    """ The base class that all FAM implementions must inherit.

    The simplest instance of a FileMonitor subclass needs only to add
    monitor objects to :attr:`handles` and received events to
    :attr:`events`; the basic interface will handle the rest. """

    #: The relative priority of this FAM backend.  Better backends
    #: should have higher priorities.
    __priority__ = -1

    #: List of names of methods to be exposed as XML-RPC functions
    __rmi__ = Debuggable.__rmi__ + ["list_event_handlers"]

    def __init__(self, ignore=None, debug=False):
        """
        :param ignore: A list of filename globs describing events that
                       should be ignored (i.e., not processed by any
                       object)
        :type ignore: list of strings (filename globs)
        :param debug: Produce debugging information about the events
                      received and handled.
        :type debug: bool

        .. -----
        .. autoattribute:: __priority__
        """
        Debuggable.__init__(self)
        self.debug_flag = debug

        #: A dict that records which objects handle which events.
        #: Keys are monitor handle IDs and values are objects whose
        #: ``HandleEvent`` method will be called to handle an event
        self.handles = dict()

        #: Queue of events to handle
        self.events = []

        if ignore is None:
            ignore = []
        #: List of filename globs to ignore events for.  For events
        #: that include the full path, both the full path and the bare
        #: filename will be checked against ``ignore``.
        self.ignore = ignore

        #: Whether or not the FAM has been started.  See :func:`start`.
        self.started = False

    def __str__(self):
        return "%s: %s" % (__name__, self.__class__.__name__)

    def __repr__(self):
        return "%s (%s events, fd %s)" % (self.__class__.__name__,
                                          len(self.events),
                                          self.fileno())

    def start(self):
        """ Start threads or anything else that needs to be done after
        the server forks and daemonizes. Note that monitors may (and
        almost certainly will) be added before ``start()`` is called,
        so if a backend depends on being started to add monitors,
        those requests will need to be enqueued and added after
        ``start()``.  See
        :class:`Bcfg2.Server.FileMonitor.Inotify.Inotify` for an
        example of this. """
        self.started = True

    def should_ignore(self, event):
        """ Returns True if an event should be ignored, False
        otherwise. For events that include the full path, both the
        full path and the bare filename will be checked against
        :attr:`ignore`.  If the event is ignored, a debug message will
        be logged with :func:`debug_log`.

        :param event: Check if this event matches :attr:`ignore`
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: bool - Whether not to ignore the event
        """
        for pattern in self.ignore:
            if (fnmatch.fnmatch(event.filename, pattern) or
                fnmatch.fnmatch(os.path.split(event.filename)[-1], pattern)):
                self.debug_log("Ignoring %s" % event)
                return True
        return False

    def pending(self):
        """ Returns True if there are pending events (i.e., events in
        :attr:`events` that have not been processed), False
        otherwise. """
        return bool(self.events)

    def get_event(self):
        """ Get the oldest pending event in :attr:`events`.

        :returns: :class:`Bcfg2.Server.FileMonitor.Event`
        """
        return self.events.pop(0)

    def fileno(self):
        """ Get the file descriptor of the file monitor thread.

        :returns: int - The FD number
        """
        return 0

    def handle_one_event(self, event):
        """ Handle the given event by dispatching it to the object
        that handles it.  This is only called by
        :func:`handle_event_set`, so if a backend overrides that
        method it does not necessarily need to implement this
        function.

        :param event: The event to handle.
        :type event: Bcfg2.Server.FileMonitor.Event
        :returns: None
        """
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
        """ Handle all pending events.

        :param lock: A thread lock to use while handling events.  If
                     None, then no thread locking will be performed.
                     This can possibly lead to race conditions in
                     event handling, although it's unlikely to cause
                     any real problems.
        :type lock: threading.Lock
        :returns: None
        """
        if not self.started:
            self.start()
        count = 0
        start = time()
        if lock:
            lock.acquire()
        while self.pending():
            self.handle_one_event(self.get_event())
            count += 1
        if lock:
            lock.release()
        end = time()
        if count > 0:
            LOGGER.info("Handled %d events in %.03fs" % (count, (end - start)))

    def handle_events_in_interval(self, interval):
        """ Handle events for the specified period of time (in
        seconds).  This call will block for ``interval`` seconds and
        handle all events received during that period by calling
        :func:`handle_event_set`.

        :param interval: The interval, in seconds, during which events
                         should be handled.  Any events that are
                         already pending when
                         :func:`handle_events_in_interval` is called
                         will also be handled.
        :type interval: int
        :returns: None
        """
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
        """ Handle any tasks required to shut down the monitor. """
        self.debug_log("Shutting down %s file monitor" %
                       self.__class__.__name__)
        self.started = False

    def AddMonitor(self, path, obj, handleID=None):
        """ Monitor the specified path, alerting obj to events.  This
        method must be overridden by a subclass of
        :class:`Bcfg2.Server.FileMonitor.FileMonitor`.

        :param path: The path to monitor
        :type path: string
        :param obj: The object whose ``HandleEvent`` method will be
                    called when an event is produced.
        :type obj: Varies
        :param handleID: The handle ID to use for the monitor.  This
                         is useful when requests to add a monitor must
                         be enqueued and the actual monitors added
                         after :func:`start` is called.
        :type handleID: Varies
        :returns: Varies - The handler ID for the newly created
                  monitor
        """
        raise NotImplementedError

    def list_event_handlers(self):
        """ XML-RPC that returns
        :attr:`Bcfg2.Server.FileMonitor.FileMonitor.handles` for
        debugging purposes. """
        rv = dict()
        for watch, handler in self.handles.items():
            rv[watch] = getattr(handler, "name", handler.__class__.__name__)
        return rv


#: A dict of all available FAM backends.  Keys are the human-readable
#: names of the backends, which are used in bcfg2.conf to select a
#: backend; values are the backend classes.  In addition, the
#: ``default`` key will be set to the best FAM backend as determined
#: by :attr:`Bcfg2.Server.FileMonitor.FileMonitor.__priority__`
available = dict()  # pylint: disable=C0103

# TODO: loading the monitor drivers should be automatic
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

for fdrv in reversed(sorted(available.keys(),
                            key=lambda k: available[k].__priority__)):
    if fdrv in available:
        available['default'] = available[fdrv]
        break
