""" Inotify driver for file alteration events """

import os
import sys
import logging
import pyinotify
from Bcfg2.Compat import reduce
from Bcfg2.Server.FileMonitor import Event
from Bcfg2.Server.FileMonitor.Pseudo import Pseudo

logger = logging.getLogger(__name__)


class Inotify(Pseudo, pyinotify.ProcessEvent):
    __priority__ = 1
    action_map = {pyinotify.IN_CREATE: 'created',
                  pyinotify.IN_DELETE: 'deleted',
                  pyinotify.IN_MODIFY: 'changed',
                  pyinotify.IN_MOVED_FROM: 'deleted',
                  pyinotify.IN_MOVED_TO: 'created'}
    mask = reduce(lambda x, y: x | y, action_map.keys())

    def __init__(self, ignore=None, debug=False):
        Pseudo.__init__(self, ignore=ignore, debug=debug)
        pyinotify.ProcessEvent(self)
        self.event_filter = dict()
        self.watches_by_path = dict()
        # these are created in start() after the server is done forking
        self.notifier = None
        self.wm = None
        self.add_q = []

    def start(self):
        Pseudo.start(self)
        self.wm = pyinotify.WatchManager()
        self.notifier = pyinotify.ThreadedNotifier(self.wm, self)
        self.notifier.start()
        for monitor in self.add_q:
            self.AddMonitor(*monitor)
        self.add_q = []

    def fileno(self):
        if self.started:
            return self.wm.get_fd()
        else:
            return None

    def process_default(self, ievent):
        action = ievent.maskname
        for amask, aname in self.action_map.items():
            if ievent.mask & amask:
                action = aname
                break
        try:
            watch = self.wm.watches[ievent.wd]
        except KeyError:
            logger.error("Error handling event for %s: Watch %s not found" %
                         (ievent.pathname, ievent.wd))
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

    def AddMonitor(self, path, obj):
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
            wd = self.watches_by_path[watch_path]
        except KeyError:
            wd = self.wm.add_watch(watch_path, self.mask,
                                   quiet=False)[watch_path]
            self.watches_by_path[watch_path] = wd

        produce_exists = True
        if not is_dir:
            if wd not in self.event_filter:
                self.event_filter[wd] = [path]
            elif path not in self.event_filter[wd]:
                self.event_filter[wd].append(path)
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

    def shutdown(self):
        if self.notifier:
            self.notifier.stop()
