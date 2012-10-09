""" Unified statistics and reporting plugin """

import time
import platform
import traceback
import lxml.etree
from Bcfg2.Reporting.Transport import load_transport_from_config, \
    TransportError
from Bcfg2.Options import REPORTING_COMMON_OPTIONS
from Bcfg2.Server.Plugin import Statistics, PullSource, PluginInitError, \
    PluginExecutionError

# required for reporting
try:
    import south  # pylint: disable=W0611
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
            raise PluginExecutionError
    return _real_rpc_call


class Reporting(Statistics, PullSource):  # pylint: disable=W0223
    """ Unified statistics and reporting plugin """
    __rmi__ = ['Ping', 'GetExtra', 'GetCurrentEntry']

    CLIENT_METADATA_FIELDS = ('profile', 'bundles', 'aliases', 'addresses',
                              'groups', 'categories', 'uuid', 'version')

    def __init__(self, core, datastore):
        Statistics.__init__(self, core, datastore)
        PullSource.__init__(self)
        self.core = core
        self.experimental = True

        self.whoami = platform.node()
        self.transport = None

        core.setup.update(REPORTING_COMMON_OPTIONS)
        core.setup.reparse()

        if not HAS_SOUTH:
            msg = "Django south is required for Reporting"
            self.logger.error(msg)
            raise PluginInitError(msg)

        try:
            self.transport = load_transport_from_config(core.setup)
        except TransportError:
            msg = "%s: Failed to load transport: %s" % \
                (self.name, traceback.format_exc().splitlines()[-1])
            self.logger.error(msg)
            raise PluginInitError(msg)

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
                self.transport.store(client.hostname, cdata,
                                     lxml.etree.tostring(
                        stats,
                        xml_declaration=False).decode('UTF-8'))
                self.logger.debug("%s: Queued statistics data for %s" %
                    (self.__class__.__name__, client.hostname))
                return
            except TransportError:
                continue
            except:
                self.logger.error("%s: Attempt %s: Failed to add statistic %s"
                                  % (self.__class__.__name__, i,
                                     traceback.format_exc().splitlines()[-1]))
        self.logger.error("%s: Retry limit reached for %s" %
                    (self.__class__.__name__, client.hostname))

    def shutdown(self):
        super(Reporting, self).shutdown()
        if self.transport:
            self.transport.shutdown()

    Ping = _rpc_call('Ping')
    GetExtra = _rpc_call('GetExtra')
    GetCurrentEntry = _rpc_call('GetCurrentEntry')
