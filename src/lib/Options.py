"""Option parsing library for utilities."""
__revision__ = '$Revision$'

import os.path
import Bcfg2.Client.Tools
# Compatibility imports
from Bcfg2.metargs import Option, ConfigBackedArgumentParser
import argparse

def add_option(opt):
    _GLOBAL_PARSER.append_option(opt)

def add_options(*opts):
    _GLOBAL_PARSER.extend_options(opts)

def bootstrap():
    return _GLOBAL_PARSER.bootstrap_parse()

def args():
    return _GLOBAL_PARSER.parse_args()

def known_args():
    return _GLOBAL_PARSER.parse_known_args()

def add_configs(*cfgs):
    _GLOBAL_PARSER.additional_configs.extend(cfgs)

def set_help(description, epilog=None):
    _GLOBAL_PARSER.parser_kwargs['description'] = description
    _GLOBAL_PARSER.parser_kwargs['epilog'] = epilog

_GLOBAL_PARSER = ConfigBackedArgumentParser('/etc/bcfg2.conf')

DEFAULT_INSTALL_PREFIX='/usr'

LOCKFILE = Option('components:lockfile', default="/var/lock/bcfg2.run",
    help='Specify lockfile')

DEBUG = Option("-d", "--debug", action='store_true',
    help="Enable debugging output")

VERBOSE = Option("-v", "--verbose", action='store_true',
    help="Enable verbose output")

DAEMON = Option("-D", "--daemonize", metavar='PIDFILE',
    help="Daemonize process, storing pid")

INSTALL_PREFIX = Option('server:prefix', default=DEFAULT_INSTALL_PREFIX,
    help='Installation location')

SENDMAIL_PATH = Option('reports:sendmailpath', default='/usr/lib/sendmail',
    help='Path to sendmail')

INTERACTIVE = Option('-I', '--interactive', action='store_true',
    help='Run interactively, prompting the user for each change')

ENCODING = Option('-E', '--encoding', 'components:encoding',
    help='Encoding of cfg files', default='UTF-8',)

PARANOID_PATH = Option('paranoid:path', default='/var/cache/bcfg2',
    help='Specify path for paranoid file backups')

PARANOID_MAX_COPIES = Option('paranoid:max_copies', default=1, type=int,
    help='Specify the number of paranoid copies you want')

OMIT_LOCK_CHECK = Option('-O', '--omit-lock-check', action='store_true',
    help='Omit lock check')

CORE_PROFILE = Option('-p', '--profile', action='store_true',
    help='Enable runtime profiling')

FILES_ON_STDIN = Option('--stdin', action='store_true',
    help='Operate on a list of files supplied on stdin')

SCHEMA_PATH = Option('--schema', default="%s/share/bcfg2/schemas" % DEFAULT_INSTALL_PREFIX,
    help='Path to XML Schema files')

REQUIRE_SCHEMA = Option('--require-schema', action='store_true',
    help="Require property files to have matching schema files")

# Metadata options
MDATA_OWNER = Option('mdata:owner', help='Default Path owner', default='root')
MDATA_GROUP = Option('mdata:group', help='Default Path group', default='root')
MDATA_IMPORTANT = Option('mdata:important', help='Default Path priority (importance)',
    default='false')
MDATA_PERMS = Option('mdata:perms', help='Default Path permissions', default='644')
MDATA_PARANOID = Option('mdata:paranoid', help='Default Path paranoid setting',
    default='false')
MDATA_SENSITIVE = Option('mdata:sensitive', help='Default Path sensitive setting',
    default='false')

# Server options
SERVER_REPOSITORY = Option('-Q', '--repository-path', 'server:repository',
    type=os.path.abspath,
    help='Server repository path', default='/var/lib/bcfg2')
SERVER_PLUGINS = Option('server:plugins', help='Server plugin list',
    default=['Bundler', 'Cfg', 'Metadata', 'Pkgmgr', 'Rules', 'SSHbase'],
    nargs='*')
SERVER_MCONNECT = Option('server:connectors', help='Server Metadata Connector list',
    default=['Probes'], nargs='*')
SERVER_FILEMONITOR = Option('server:filemonitor', help='Server file monitor',
    default='default')
SERVER_ENABLE_FILEMONITOR = Option('server:enable_filemonitor', help='Enable filemonitoring', action='store_true')
SERVER_LISTEN_ALL = Option('server:listen_all', '--listen-all',
    help='Listen on all interfaces', action='store_true')
SERVER_LOCATION = Option('components:bcfg2', '-S', '--server-location',
    help='Server Location', default='https://localhost:6789')
SERVER_STATIC = Option('components:static_port', action='store_true',
    help='Server runs on static port')
SERVER_KEY = Option('communication:key', '--ssl-key', 
    help='Path to SSL key')
SERVER_CERT = Option('communication:certificate', '--ssl-cert',
    help='Path to SSL certificate', default='/etc/bcfg2.key')
SERVER_CA = Option('communication:ca', '--ca-cert',
    help='Path to SSL CA Cert', default=None)
SERVER_PASSWORD = Option('communication:password', '-x', '--password',
    help='Communication Password')
SERVER_PROTOCOL = Option('communication:protocol', help='Server Protocol',
    default='xmlrpc/ssl')

# Client options
CLIENT_KEY = SERVER_KEY
CLIENT_CERT = SERVER_CERT
CLIENT_CA = SERVER_CA
CLIENT_SCNS = Option('communication:serverCommonNames', '--ssl-cns',
    help='List of server commonNames', cfg_split_char=':', nargs=2)
CLIENT_PROFILE = CORE_PROFILE
CLIENT_RETRIES = Option('communication:retries', '-R', '--retries',
    help='The number of times to retry network communication', default=3,
    type=int)
CLIENT_DRYRUN = Option('-n', '--dryrun', action='store_true',
    help='Do not actually change the system')
CLIENT_EXTRA_DISPLAY = Option('-e', '--extra-display', action='store_true',
    help='enable extra entry output')
CLIENT_PARANOID = Option('client:paranoid', '-P', '--paranoid',
    action='store_true', help='Make automatic backups of config files')
CLIENT_DRIVERS = Option('client:drivers', '-D', '--drivers',
    help='Specify tool driver set', nargs='*', default=Bcfg2.Client.Tools.default)
CLIENT_CACHE = Option('--cache', help='Store the configuration in a file',
    type=argparse.FileType('w'))
CLIENT_REMOVE = Option('-r', '--remove-extra', help='Force removal of additional configuration items', choices=['all', 'Packages', 'packages', 'Services', 'services'])
CLIENT_BUNDLE = Option('-b', '--bundles', help='Only configure the given bundle(s)', default=[],
    nargs='*')
CLIENT_BUNDLEQUICK = Option('-Q', '--quick-bundles', default=[], nargs='*',
    help='only verify/configure the given bundle(s)')
CLIENT_INDEP = Option('-z', '--ignore-bundles', action='store_true',
    help='Only configure independent entries, ignore bundles')
CLIENT_KEVLAR = Option('-k', '--bulletproof', action='store_true',
    help='Run in kevlar (bulletproof) mode')
CLIENT_DLIST = Option('client:decision', '-l', '--decision-list',
    choices=['whitelist', 'blacklist', 'none'], dest='decision',
    help='Run client in server decision list mode')
CLIENT_FILE = Option('-f', '--from-file', help='Configure from a file rather than querying the server', type=argparse.FileType('r'))
CLIENT_QUICK = Option('-q', '--disable-checksum', action='store_true',
    help='Disable some checksum verification')
CLIENT_USER = Option('communication:user', '-u', '--user', default='root',
    help='The user to provide for authentication')
CLIENT_SERVICE_MODE = Option('-s', '--service-mode', choices=['default', 'disabled', 'build'],
    help='Set client service mode', default='default')
CLIENT_TIMEOUT = Option('communication:timeout', '-t', '--timeout',
    help='Set the client XML-RPC timeout', default=90, type=int)

# APT client tool options
CLIENT_APT_TOOLS_INSTALL_PATH = Option('APT:install_path',
    help='Apt tools install path', default='/usr')
CLIENT_APT_TOOLS_VAR_PATH = Option('APT:var_path',
    help='Apt tools var path', default='/var')
CLIENT_SYSTEM_ETC_PATH = Option('APT:etc_path',
    help='System etc path', default='/etc')

# Logging options
LOGGING_FILE_PATH = Option('logging:path', '-o', '--log-path', help='Set path of file log')
