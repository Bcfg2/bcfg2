#!/usr/bin/env python
# $Id: $

class FileBacked(object):
    '''This object caches file data in memory.
    HandleEvent is called whenever fam registers an event.
    Index can parse the data into member data as required.'''
    
    def __init__(self, name):
        self.name = name

    def HandleEvent(self, event=None):
        self.data = file(self.name).read()
        self.Index()

    def Index(self):
        pass

class DirectoryBacked(object):
    def __init__(self, name, fam):
        self.name = name
        self.fam = fam
        self.entries = {}
        self.inventory = False
        fam.AddMonitor(name, self)

    def AddEntry(self, name):
        if self.entries.has_key(name):
            print "got multiple adds"
        else:
            self.entries[name] = FileBacked('%s/%s'%(self.name, name))
            self.entries[name].HandleEvent()

    def HandleEvent(self, event):
        action = event.code2str()
        print "Got event %s %s %s"%(event.requestID, event.code2str(), event.filename)
        if action == 'exists':
            if event.filename != self.name:
                self.AddEntry(event.filename)
        elif action == 'created':
            self.AddEntry(event.filename)
        elif action == 'changed':
            self.entries[event.filename].HandleEvent(event)
        elif action == 'deleted':
            if self.entries.has_key(event.filename):
                del self.entries[event.filename]
        elif action in ['endExist']:
            pass
        else:
            print "Got unknown event %s %s %s"%(event.requestID, event.code2str(), event.filename)

