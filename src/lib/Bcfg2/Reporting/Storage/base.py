"""
The base for all Storage backends
"""

import logging 

class StorageError(Exception):
    """Generic StorageError"""
    pass

class StorageImportError(StorageError):
    """Raised when a storage module fails to import"""
    pass

class StorageBase(object):
    """The base for all storages"""

    __rmi__ = ['Ping', 'GetExtra', 'GetCurrentEntry']

    def __init__(self, setup):
        """Do something here"""
        clsname = self.__class__.__name__
        self.logger = logging.getLogger(clsname)
        self.logger.debug("Loading %s storage" % clsname)
        self.setup = setup
        self.encoding = setup['encoding']

    def import_interaction(self, interaction):
        """Import the data into the backend"""
        raise NotImplementedError

    def validate(self):
        """Validate backend storage.  Should be called once when loaded"""
        raise NotImplementedError

    def shutdown(self):
        """Called at program exit"""
        pass

    def Ping(self):
        """Test for communication with reporting collector"""
        return "Pong"

    def GetExtra(self, client):
        """Return a list of extra entries for a client.  Minestruct"""
        raise NotImplementedError

    def GetCurrentEntry(self, client, e_type, e_name):
        """Get the current status of an entry on the client"""
        raise NotImplementedError

