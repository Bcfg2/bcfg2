"""
The base for all server -> collector Transports
"""

import os.path
import logging 

class TransportError(Exception):
    """Generic TransportError"""
    pass

class TransportImportError(TransportError):
    """Raised when a transport fails to import"""
    pass

class TransportBase(object):
    """The base for all transports"""

    def __init__(self, setup):
        """Do something here"""
        clsname = self.__class__.__name__
        self.logger = logging.getLogger(clsname)
        self.logger.debug("Loading %s transport" % clsname)
        self.data = os.path.join(setup['repo'], 'Reporting', clsname)
        self.setup = setup
        self.timeout = 2

    def start_monitor(self, collector):
        """Called to start monitoring"""
        raise NotImplementedError

    def store(self, hostname, metadata, stats):
        raise NotImplementedError

    def fetch(self):
        raise NotImplementedError

    def shutdown(self):
        """Called at program exit"""
        pass

    def rpc(self, method, *args, **kwargs):
        """Send a request for data to the collector"""
        raise NotImplementedError
