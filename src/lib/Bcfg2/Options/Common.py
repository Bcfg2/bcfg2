""" Common options used in multiple different contexts. """

from Bcfg2.Utils import classproperty
from Bcfg2.Options import Types
from Bcfg2.Options.Actions import PluginsAction, ComponentAction
from Bcfg2.Options.Parser import repository as _repository_option
from Bcfg2.Options import Option, PathOption, BooleanOption

__all__ = ["Common"]


class ReportingTransportAction(ComponentAction):
    """ :class:`Bcfg2.Options.ComponentAction` that loads a single
    reporting transport from :mod:`Bcfg2.Reporting.Transport`. """
    islist = False
    bases = ['Bcfg2.Reporting.Transport']


class ReportingStorageAction(ComponentAction):
    """ :class:`Bcfg2.Options.ComponentAction` that loads a single
    reporting storage driver from :mod:`Bcfg2.Reporting.Storage`. """
    islist = False
    bases = ['Bcfg2.Reporting.Storage']


class Common(object):
    """ Common options used in multiple different contexts. """
    _plugins = None
    _filemonitor = None
    _reporting_storage = None
    _reporting_transport = None

    @classproperty
    def plugins(cls):
        """ Load a list of Bcfg2 server plugins """
        if cls._plugins is None:
            cls._plugins = Option(
                cf=('server', 'plugins'),
                type=Types.comma_list, help="Server plugin list",
                action=PluginsAction,
                default=['Bundler', 'Cfg', 'Metadata', 'Pkgmgr', 'Rules',
                         'SSHbase'])
        return cls._plugins

    @classproperty
    def filemonitor(cls):
        """ Load a single Bcfg2 file monitor (from
        :attr:`Bcfg2.Server.FileMonitor.available`) """
        if cls._filemonitor is None:
            import Bcfg2.Server.FileMonitor

            class FileMonitorAction(ComponentAction):
                """ ComponentAction for loading a single FAM backend
                class """
                islist = False
                mapping = Bcfg2.Server.FileMonitor.available

            cls._filemonitor = Option(
                cf=('server', 'filemonitor'), action=FileMonitorAction,
                default='default', help='Server file monitoring driver')
        return cls._filemonitor

    @classproperty
    def reporting_storage(cls):
        """ Load a Reporting storage backend """
        if cls._reporting_storage is None:
            cls._reporting_storage = Option(
                cf=('reporting', 'storage'), dest="reporting_storage",
                help='Reporting storage engine',
                action=ReportingStorageAction, default='DjangoORM')
        return cls._reporting_storage

    @classproperty
    def reporting_transport(cls):
        """ Load a Reporting transport backend """
        if cls._reporting_transport is None:
            cls._reporting_transport = Option(
                cf=('reporting', 'transport'), dest="reporting_transport",
                help='Reporting transport',
                action=ReportingTransportAction, default='DirectStore')
        return cls._reporting_transport

    #: Set the path to the Bcfg2 repository
    repository = _repository_option

    #: Daemonize process, storing PID
    daemon = PathOption(
        '-D', '--daemon', help="Daemonize process, storing PID")

    #: Run interactively, prompting the user for each change
    interactive = BooleanOption(
        "-I", "--interactive",
        help='Run interactively, prompting the user for each change')

    #: Log to syslog
    syslog = BooleanOption(
        cf=('logging', 'syslog'), help="Log to syslog", default=True)

    #: Server location
    location = Option(
        '-S', '--server', cf=('components', 'bcfg2'),
        default='https://localhost:6789', metavar='<https://server:port>',
        help="Server location")

    #: Communication password
    password = Option(
        '-x', '--password', cf=('communication', 'password'),
        metavar='<password>', help="Communication Password")

    #: Path to SSL CA certificate
    ssl_ca = PathOption(
        cf=('communication', 'ca'), help='Path to SSL CA Cert')

    #: Communication protocol
    protocol = Option(
        cf=('communication', 'protocol'), default='xmlrpc/tlsv1',
        choices=['xmlrpc/ssl', 'xmlrpc/tlsv1'],
        help='Communication protocol to use.')

    #: Default Path paranoid setting
    default_paranoid = Option(
        cf=('mdata', 'paranoid'), dest="default_paranoid", default='true',
        choices=['true', 'false'], help='Default Path paranoid setting')

    #: Client timeout
    client_timeout = Option(
        "-t", "--timeout", type=float, default=90.0, dest="client_timeout",
        cf=('communication', 'timeout'),
        help='Set the client XML-RPC timeout')
