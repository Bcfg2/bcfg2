""" Unified statistics and reporting plugin """

import sys
import time
import platform
import lxml.etree
import Bcfg2.Options
from Bcfg2.Reporting.Transport.base import TransportError
from Bcfg2.Server.Plugin import Statistics, PullSource, Threaded, \
    PluginInitError, PluginExecutionError

# required for reporting
try:
    import south  # pylint: disable=unused-import
    HAS_SOUTH = True
except ImportError:
    HAS_SOUTH = False


def _rpc_call(method):
    """ Given the name of a Reporting Transport method, get a function
    that defers an XML-RPC call to that method """
    def _real_rpc_call(self, *args, **kwargs):
        """Wrapper for calls to the reporting collector"""
        try:
            return self.transport.rpc(method, *args, **kwargs)
        except TransportError:
            # this is needed for Admin.Pull
            raise PluginExecutionError(sys.exc_info()[1])
    return _real_rpc_call


# pylint: disable=abstract-method
class Reporting(Statistics, Threaded, PullSource):
    """ Unified statistics and reporting plugin """
    __rmi__ = Statistics.__rmi__ + ['Ping', 'GetExtra', 'GetCurrentEntry']

    options = [Bcfg2.Options.Common.reporting_transport]

    CLIENT_METADATA_FIELDS = ('profile', 'bundles', 'aliases', 'addresses',
                              'groups', 'categories', 'uuid', 'version')

    def __init__(self, core):
        Statistics.__init__(self, core)
        PullSource.__init__(self)
        Threaded.__init__(self)

        self.whoami = platform.node()
        self.transport = None

        if not HAS_SOUTH:
            msg = "Django south is required for Reporting"
            self.logger.error(msg)
            raise PluginInitError(msg)

        # This must be loaded here for bcfg2-admin
        try:
            self.transport = Bcfg2.Options.setup.reporting_transport()
        except TransportError:
            raise PluginInitError("%s: Failed to instantiate transport: %s" %
                                  (self.name, sys.exc_info()[1]))
        if self.debug_flag:
            self.transport.set_debug(self.debug_flag)

    def start_threads(self):
        """Nothing to do here"""
        pass

    def set_debug(self, debug):
        rv = Statistics.set_debug(self, debug)
        if self.transport is not None:
            self.transport.set_debug(debug)
        return rv

    def process_statistics(self, client, xdata):
        stats = xdata.find("Statistics")
        stats.set('time', time.asctime(time.localtime()))

        cdata = {'server': self.whoami}
        for field in self.CLIENT_METADATA_FIELDS:
            try:
                value = getattr(client, field)
            except AttributeError:
                continue
            if value:
                if isinstance(value, set):
                    value = [v for v in value]
                cdata[field] = value

        # try 3 times to store the data
        for i in [1, 2, 3]:
            try:
                self.transport.store(
                    client.hostname, cdata,
                    lxml.etree.tostring(
                        stats,
                        xml_declaration=False))
                self.debug_log("%s: Queued statistics data for %s" %
                               (self.__class__.__name__, client.hostname))
                return
            except TransportError:
                continue
            except:  # pylint: disable=bare-except
                self.logger.error("%s: Attempt %s: Failed to add statistic: %s"
                                  % (self.__class__.__name__, i,
                                     sys.exc_info()[1]))
        raise PluginExecutionError("%s: Retry limit reached for %s" %
                                   (self.__class__.__name__, client.hostname))

    def shutdown(self):
        super(Reporting, self).shutdown()
        if self.transport:
            self.transport.shutdown()

    Ping = _rpc_call('Ping')
    GetExtra = _rpc_call('GetExtra')
    GetCurrentEntry = _rpc_call('GetCurrentEntry')
