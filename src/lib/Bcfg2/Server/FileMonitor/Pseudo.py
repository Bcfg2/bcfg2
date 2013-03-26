""" Pseudo provides static monitor support for file alteration events.
That is, it only produces "exists" and "endExist" events and does not
monitor for ongoing changes. """

import os
from Bcfg2.Server.FileMonitor import FileMonitor, Event


class Pseudo(FileMonitor):
    """ File monitor that only produces events on server startup and
    doesn't actually monitor for ongoing changes at all. """

    #: The ``Pseudo`` monitor should only be used if no other FAM
    #: backends are available.
    __priority__ = 1

    def AddMonitor(self, path, obj, handleID=None):
        if handleID is None:
            handleID = len(list(self.handles.keys()))
        self.events.append(Event(handleID, path, 'exists'))
        if os.path.isdir(path):
            dirlist = os.listdir(path)
            for fname in dirlist:
                self.events.append(Event(handleID, fname, 'exists'))
            self.events.append(Event(handleID, path, 'endExist'))

        if obj is not None:
            self.handles[handleID] = obj
        return handleID
