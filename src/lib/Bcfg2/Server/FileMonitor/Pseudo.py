""" Pseudo provides static monitor support for file alteration events """

import os
from Bcfg2.Server.FileMonitor import FileMonitor, Event


class Pseudo(FileMonitor):
    """ file monitor that only produces events on server startup and
    doesn't actually monitor at all """

    __priority__ = 99

    def AddMonitor(self, path, obj, handleID=None):
        """add a monitor to path, installing a callback to obj.HandleEvent"""
        if handleID is None:
            handleID = len(list(self.handles.keys()))
        self.events.append(Event(handleID, path, 'exists'))
        if os.path.isdir(path):
            dirlist = os.listdir(path)
            for fname in dirlist:
                self.events.append(Event(handleID, fname, 'exists'))
            self.events.append(Event(handleID, path, 'endExist'))

        if obj != None:
            self.handles[handleID] = obj
        return handleID
