#!/usr/bin/env python
# $Id$

from os import listdir, stat
from stat import ST_MTIME

class FileBacked(object):
    '''FileBacked is a class that will cache file data and automatically reload it as required from disk.'''

    def __init__(self,filename):
        '''Setup initial structures'''
        self.filename = filename
        try:
            self.mtime = stat(filename)[ST_MTIME]
            self._data = file(filename).read()
        except OSError:
            self.mtime = 0
            self._data = None
            self.setdata('')

    def getdata(self):
        mtime = stat(self.filename)[ST_MTIME]
        if mtime != self.mtime:
            self._data = file(self.filename).read()
            self.mtime = mtime
        return self._data

    def setdata(self,val):
        if val != self._data:
            self._data = val
            file(self.filename,'w').write(val)
            self.mtime = stat(self.filename)[ST_MTIME]

    data=property(getdata,setdata)

class DirectoryBacked(object):
    '''DirectoryBacked caches a complete directory (including proper negative caching).
    This class is READ-ONLY.'''

    def __init__(self,path):
        self.path = path
        self._entries = {}
        self.mtime = stat(path)[ST_MTIME]
        for entry in listdir(path):
            self._entries[entry] = FileBacked("%s/%s"%(path,entry))

    def GetEntries(self):
        mtime = stat(self.path)[ST_MTIME]
        if mtime != self.mtime:
            current = self._entries.keys()
            new = listdir(self.path)
            for key in new:
                if key not in current:
                    self._entries[key] = FileBacked("%s/%s"%(self.path,key))
            for key in current:
                if key not in new:
                    del self._entries[key]
        return self._entries

    def SetEntries(self,val):
        pass

    entries = property(GetEntries,SetEntries)
                
