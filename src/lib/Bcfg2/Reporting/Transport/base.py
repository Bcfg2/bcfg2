"""
The base for all server -> collector Transports
"""

import os
import sys
from Bcfg2.Server.Plugin import Debuggable


class TransportError(Exception):
    """Generic TransportError"""
    pass


class TransportImportError(TransportError):
    """Raised when a transport fails to import"""
    pass


class TransportBase(Debuggable):
    """The base for all transports"""

    def __init__(self, setup):
        """Do something here"""
        clsname = self.__class__.__name__
        Debuggable.__init__(self, name=clsname)
        self.debug_log("Loading %s transport" % clsname)
        self.data = os.path.join(setup['repo'], 'Reporting', clsname)
        if not os.path.exists(self.data):
            self.logger.info("%s does not exist, creating" % self.data)
            try:
                os.makedirs(self.data)
            except OSError:
                self.logger.warning("Could not create %s: %s" %
                                    (self.data, sys.exc_info()[1]))
                self.logger.warning("The transport may not function properly")
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
