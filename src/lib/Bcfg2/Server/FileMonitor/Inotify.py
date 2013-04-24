"""File monitor backend with `inotify <http://inotify.aiken.cz/>`_
support. """

import os
import errno
import pyinotify
from Bcfg2.Compat import reduce  # pylint: disable=W0622
from Bcfg2.Server.FileMonitor import Event
from Bcfg2.Server.FileMonitor.Pseudo import Pseudo


class Inotify(Pseudo, pyinotify.ProcessEvent):
    """ File monitor backend with `inotify
    <http://inotify.aiken.cz/>`_ support. """

    __rmi__ = Pseudo.__rmi__ + ["list_watches", "list_paths"]

    #: Inotify is the best FAM backend, so it gets a very high
    #: priority
    __priority__ = 99

    # pylint: disable=E1101
    #: Map pyinotify event constants to FAM :ref:`event codes
    #: <development-fam-event-codes>`.  The mapping is not
    #: terrifically exact.
    action_map = {pyinotify.IN_CREATE: 'created',
                  pyinotify.IN_DELETE: 'deleted',
                  pyinotify.IN_MODIFY: 'changed',
                  pyinotify.IN_MOVED_FROM: 'deleted',
                  pyinotify.IN_MOVED_TO: 'created'}
    # pylint: enable=E1101

    #: The pyinotify event mask.  We only ask for events that are
    #: listed in :attr:`action_map`
    mask = reduce(lambda x, y: x | y, action_map.keys())

    def __init__(self, ignore=None, debug=False):
        Pseudo.__init__(self, ignore=ignore, debug=debug)
        pyinotify.ProcessEvent.__init__(self)

        #: inotify can't set useful monitors directly on files, only
        #: on directories, so when a monitor is added on a file we add
        #: its parent directory to ``event_filter`` and then only
        #: produce events on a file in that directory if the file is
        #: listed in ``event_filter``.  Keys are directories -- the
        #: parent directories of individual files that are monitored
        #: -- and values are lists of full paths to files in each
        #: directory that events *should* be produced for.  An event
        #: on a file whose parent directory is in ``event_filter`` but
        #: which is not itself listed will be silently suppressed.
        self.event_filter = dict()

        #: inotify doesn't like monitoring a path twice, so we keep a
        #: dict of :class:`pyinotify.Watch` objects, keyed by monitor
        #: path, to avoid trying to create duplicate monitors.
        #: (Duplicates can happen if an object accidentally requests
        #: duplicate monitors, or if two files in a single directory
        #: are both individually monitored, since inotify can't set
        #: monitors on the files but only on the parent directories.)
        self.watches_by_path = dict()

        #: The :class:`pyinotify.ThreadedNotifier` object.  This is
        #: created in :func:`start` after the server is done
        #: daemonizing.
        self.notifier = None

        #: The :class:`pyinotify.WatchManager` object. This is created
        #: in :func:`start` after the server is done daemonizing.
        self.watchmgr = None

        #: The queue used to record monitors that are added before
        #: :func:`start` has been called and :attr:`notifier` and
        #: :attr:`watchmgr` are created.
        self.add_q = []

    def start(self):
        """ The inotify notifier and manager objects in
        :attr:`notifier` and :attr:`watchmgr` must be created by the
        daemonized process, so they are created in ``start()``. Before
        those objects are created, monitors are added to
        :attr:`add_q`, and are created once the
        :class:`pyinotify.ThreadedNotifier` and
        :class:`pyinotify.WatchManager` objects are created."""
        Pseudo.start(self)
        self.watchmgr = pyinotify.WatchManager()
        self.notifier = pyinotify.ThreadedNotifier(self.watchmgr, self)
        self.notifier.start()
        for monitor in self.add_q:
            self.AddMonitor(*monitor)
        self.add_q = []

    def fileno(self):
        if self.started:
            return self.watchmgr.get_fd()
        else:
            return None
    fileno.__doc__ = Pseudo.fileno.__doc__

    def process_default(self, ievent):
        """ Process all inotify events received.  This process a
        :class:`pyinotify._Event` object, creates a
        :class:`Bcfg2.Server.FileMonitor.Event` object from it, and
        adds that event to :attr:`events`.

        :param ievent: Event to be processed
        :type ievent: pyinotify._Event
        """
        action = ievent.maskname
        for amask, aname in self.action_map.items():
            if ievent.mask & amask:
                action = aname
                break
        else:
            # event action is not in the mask, and thus is not
            # something we care about
            self.debug_log("Ignoring event %s for %s" % (action,
                                                         ievent.pathname))
            return

        try:
            watch = self.watchmgr.watches[ievent.wd]
        except KeyError:
            self.logger.error("Error handling event %s for %s: "
                              "Watch %s not found" %
                              (action, ievent.pathname, ievent.wd))
            return
        # FAM-style file monitors return the full path to the parent
        # directory that is being watched, relative paths to anything
        # contained within the directory. since we can't use inotify
        # to watch files directly, we have to sort of guess at whether
        # this watch was actually added on a file (and thus is in
        # self.event_filter because we're filtering out other events
        # on the directory) or was added directly on a directory.
        if (watch.path == ievent.pathname or ievent.wd in self.event_filter):
            path = ievent.pathname
        else:
            # relative path
            path = os.path.basename(ievent.pathname)
        # figure out the handleID.  start with the path of the event;
        # that should catch events on files that are watched directly.
        # (we have to watch the directory that a file is in, so this
        # lets us handle events on different files in the same
        # directory -- and thus under the same watch -- with different
        # objects.)  If the path to the event doesn't have a handler,
        # use the path of the watch itself.
        handleID = ievent.pathname
        if handleID not in self.handles:
            handleID = watch.path
        evt = Event(handleID, path, action)

        if (ievent.wd not in self.event_filter or
            ievent.pathname in self.event_filter[ievent.wd]):
            self.events.append(evt)

    def AddMonitor(self, path, obj, handleID=None):
        # strip trailing slashes
        path = path.rstrip("/")

        if not self.started:
            self.add_q.append((path, obj))
            return path

        if not os.path.isdir(path):
            # inotify is a little wonky about watching files.  for
            # instance, if you watch /tmp/foo, and then do 'mv
            # /tmp/bar /tmp/foo', it processes that as a deletion of
            # /tmp/foo (which it technically _is_, but that's rather
            # useless -- we care that /tmp/foo changed, not that it
            # was first deleted and then created).  In order to
            # effectively watch a file, we have to watch the directory
            # it's in, and filter out events for other files in the
            # same directory that are not similarly watched.
            # watch_transient_file requires a Processor _class_, not
            # an object, so we can't have this object handle events,
            # which is Wrong, so we can't use that function.
            watch_path = os.path.dirname(path)
            is_dir = False
        else:
            watch_path = path
            is_dir = True

        # see if this path is already being watched
        try:
            watchdir = self.watches_by_path[watch_path]
        except KeyError:
            if not os.path.exists(watch_path):
                raise OSError(errno.ENOENT,
                              "No such file or directory: '%s'" % path)
            watchdir = self.watchmgr.add_watch(watch_path, self.mask,
                                               quiet=False)[watch_path]
            self.watches_by_path[watch_path] = watchdir

        produce_exists = True
        if not is_dir:
            if watchdir not in self.event_filter:
                self.event_filter[watchdir] = [path]
            elif path not in self.event_filter[watchdir]:
                self.event_filter[watchdir].append(path)
            else:
                # we've been asked to watch a file that we're already
                # watching, so we don't need to produce 'exists'
                # events
                produce_exists = False

        # inotify doesn't produce initial 'exists' events, so we
        # inherit from Pseudo to produce those
        if produce_exists:
            return Pseudo.AddMonitor(self, path, obj, handleID=path)
        else:
            self.handles[path] = obj
            return path
    AddMonitor.__doc__ = Pseudo.AddMonitor.__doc__

    def shutdown(self):
        if self.notifier:
            self.notifier.stop()
    shutdown.__doc__ = Pseudo.shutdown.__doc__

    def list_watches(self):
        """ XML-RPC that returns a list of current inotify watches for
        debugging purposes. """
        return list(self.watches_by_path.keys())

    def list_paths(self):
        """ XML-RPC that returns a list of paths that are handled for
        debugging purposes. Because inotify doesn't like watching
        files, but prefers to watch directories, this will be
        different from
        :func:`Bcfg2.Server.FileMonitor.Inotify.Inotify.ListWatches`. For
        instance, if a plugin adds a monitor to
        ``/var/lib/bcfg2/Plugin/foo.xml``, :func:`ListPaths` will
        return ``/var/lib/bcfg2/Plugin/foo.xml``, while
        :func:`ListWatches` will return ``/var/lib/bcfg2/Plugin``. """
        return list(self.handles.keys())
