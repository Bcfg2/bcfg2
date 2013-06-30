"""Option parsing library for utilities."""

import copy
import getopt
import inspect
import os
import re
import shlex
import sys
import grp
import pwd
import Bcfg2.Client.Tools
from Bcfg2.Compat import ConfigParser
from Bcfg2.version import __version__


class OptionFailure(Exception):
    """ raised when malformed Option objects are instantiated """
    pass

DEFAULT_CONFIG_LOCATION = '/etc/bcfg2.conf'
DEFAULT_INSTALL_PREFIX = '/usr'


class DefaultConfigParser(ConfigParser.ConfigParser):
    """ A config parser that can be used to query options with default
    values in the event that the option is not found """

    def __init__(self, *args, **kwargs):
        """Make configuration options case sensitive"""
        ConfigParser.ConfigParser.__init__(self, *args, **kwargs)
        self.optionxform = str

    def get(self, section, option, **kwargs):
        """ convenience method for getting config items """
        default = None
        if 'default' in kwargs:
            default = kwargs['default']
            del kwargs['default']
        try:
            return ConfigParser.ConfigParser.get(self, section, option,
                                                 **kwargs)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            if default is not None:
                return default
            else:
                raise

    def getboolean(self, section, option, **kwargs):
        """ convenience method for getting boolean config items """
        default = None
        if 'default' in kwargs:
            default = kwargs['default']
            del kwargs['default']
        try:
            return ConfigParser.ConfigParser.getboolean(self, section,
                                                        option, **kwargs)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError,
                ValueError):
            if default is not None:
                return default
            else:
                raise


class Option(object):
    """ a single option, which might be read from the command line,
    environment, or config file """

    # pylint: disable=C0103,R0913
    def __init__(self, desc, default, cmd=None, odesc=False,
                 env=False, cf=False, cook=False, long_arg=False,
                 deprecated_cf=None):
        self.desc = desc
        self.default = default
        self.cmd = cmd
        self.long = long_arg
        if not self.long:
            if cmd and (cmd[0] != '-' or len(cmd) != 2):
                raise OptionFailure("Poorly formed command %s" % cmd)
        elif cmd and not cmd.startswith('--'):
            raise OptionFailure("Poorly formed command %s" % cmd)
        self.odesc = odesc
        self.env = env
        self.cf = cf
        self.deprecated_cf = deprecated_cf
        self.boolean = False
        if not odesc and not cook and isinstance(self.default, bool):
            self.boolean = True
        self.cook = cook
        self.value = None
    # pylint: enable=C0103,R0913

    def get_cooked_value(self, value):
        """ get the value of this option after performing any option
        munging specified in the 'cook' keyword argument to the
        constructor """
        if self.boolean:
            return True
        if self.cook:
            return self.cook(value)
        else:
            return value

    def __str__(self):
        rv = ["%s: " % self.__class__.__name__, self.desc]
        if self.cmd or self.cf:
            rv.append(" (")
        if self.cmd:
            if self.odesc:
                if self.long:
                    rv.append("%s=%s" % (self.cmd, self.odesc))
                else:
                    rv.append("%s %s" % (self.cmd, self.odesc))
            else:
                rv.append("%s" % self.cmd)

        if self.cf:
            if self.cmd:
                rv.append("; ")
            rv.append("[%s].%s" % self.cf)
        if self.cmd or self.cf:
            rv.append(")")
        if hasattr(self, "value"):
            rv.append(": %s" % self.value)
        return "".join(rv)

    def buildHelpMessage(self):
        """ build the help message for this option """
        vals = []
        if not self.cmd:
            return ''
        if self.odesc:
            if self.long:
                vals.append("%s=%s" % (self.cmd, self.odesc))
            else:
                vals.append("%s %s" % (self.cmd, self.odesc))
        else:
            vals.append(self.cmd)
        vals.append(self.desc)
        return "     %-28s %s\n" % tuple(vals)

    def buildGetopt(self):
        """ build a string suitable for describing this short option
        to getopt """
        gstr = ''
        if self.long:
            return gstr
        if self.cmd:
            gstr = self.cmd[1]
            if self.odesc:
                gstr += ':'
        return gstr

    def buildLongGetopt(self):
        """ build a string suitable for describing this long option to
        getopt """
        if self.odesc:
            return self.cmd[2:] + '='
        else:
            return self.cmd[2:]

    def parse(self, opts, rawopts, configparser=None):
        """ parse a single option. try parsing the data out of opts
        (the results of getopt), rawopts (the raw option string), the
        environment, and finally the config parser. either opts or
        rawopts should be provided, but not both """
        if self.cmd and opts:
            # Processing getopted data
            optinfo = [opt[1] for opt in opts if opt[0] == self.cmd]
            if optinfo:
                if optinfo[0]:
                    self.value = self.get_cooked_value(optinfo[0])
                else:
                    self.value = True
                return
        if self.cmd and self.cmd in rawopts:
            if self.odesc:
                data = rawopts[rawopts.index(self.cmd) + 1]
            else:
                data = True
            self.value = self.get_cooked_value(data)
            return
        # No command line option found
        if self.env and self.env in os.environ:
            self.value = self.get_cooked_value(os.environ[self.env])
            return
        if self.cf and configparser:
            try:
                self.value = self.get_cooked_value(configparser.get(*self.cf))
                return
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                pass
            if self.deprecated_cf:
                try:
                    self.value = self.get_cooked_value(
                        configparser.get(*self.deprecated_cf))
                    print("Warning: [%s] %s is deprecated, use [%s] %s instead"
                          % (self.deprecated_cf[0], self.deprecated_cf[1],
                             self.cf[0], self.cf[1]))
                    return
                except (ConfigParser.NoSectionError,
                        ConfigParser.NoOptionError):
                    pass

        # Default value not cooked
        self.value = self.default


class OptionSet(dict):
    """ a set of Option objects that interfaces with getopt and
    DefaultConfigParser to populate a dict of <option name>:<value>
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args)
        self.hm = self.buildHelpMessage()  # pylint: disable=C0103
        if 'configfile' in kwargs:
            self.cfile = kwargs['configfile']
        else:
            self.cfile = DEFAULT_CONFIG_LOCATION
        if 'quiet' in kwargs:
            self.quiet = kwargs['quiet']
        else:
            self.quiet = False
        self.cfp = DefaultConfigParser()
        if len(self.cfp.read(self.cfile)) == 0 and not self.quiet:
            # suppress warnings if called from bcfg2-admin init
            caller = inspect.stack()[-1][1].split('/')[-1]
            if caller == 'bcfg2-admin' and len(sys.argv) > 1:
                if sys.argv[1] == 'init':
                    return
            else:
                print("Warning! Unable to read specified configuration file: "
                      "%s" % self.cfile)

    def buildGetopt(self):
        """ build a short option description string suitable for use
        by getopt.getopt """
        return ''.join([opt.buildGetopt() for opt in list(self.values())])

    def buildLongGetopt(self):
        """ build a list of long options suitable for use by
        getopt.getopt """
        return [opt.buildLongGetopt() for opt in list(self.values())
                if opt.long]

    def buildHelpMessage(self):
        """ Build the help mesage for this option set, or use self.hm
        if it is set """
        if hasattr(self, 'hm'):
            return self.hm
        hlist = []  # list of _non-empty_ help messages
        for opt in list(self.values()):
            helpmsg = opt.buildHelpMessage()
            if helpmsg:
                hlist.append(helpmsg)
        return ''.join(hlist)

    def helpExit(self, msg='', code=1):
        """ print help and exit """
        if msg:
            print(msg)
        print("Usage:")
        print(self.buildHelpMessage())
        raise SystemExit(code)

    def versionExit(self, code=0):
        """ print the version of bcfg2 and exit """
        print("%s %s on Python %s" %
              (os.path.basename(sys.argv[0]),
               __version__,
               ".".join(str(v) for v in sys.version_info[0:3])))
        raise SystemExit(code)

    def parse(self, argv, do_getopt=True):
        '''Parse options from command line.'''
        if VERSION not in self.values():
            self['__version__'] = VERSION
        if do_getopt:
            try:
                opts, args = getopt.getopt(argv, self.buildGetopt(),
                                           self.buildLongGetopt())
            except getopt.GetoptError:
                err = sys.exc_info()[1]
                self.helpExit(err)
            if '-h' in argv:
                self.helpExit('', 0)
            if '--version' in argv:
                self.versionExit()
            self['args'] = args
        for key in list(self.keys()):
            if key == 'args':
                continue
            option = self[key]
            if do_getopt:
                option.parse(opts, [], configparser=self.cfp)
            else:
                option.parse([], argv, configparser=self.cfp)
            if hasattr(option, 'value'):
                val = option.value
                self[key] = val
        if "__version__" in self:
            del self['__version__']


def list_split(c_string):
    """ split an option string on commas, optionally surrounded by
    whitespace, returning a list """
    if c_string:
        return re.split(r'\s*,\s*', c_string)
    return []


def colon_split(c_string):
    """ split an option string on colons, returning a list """
    if c_string:
        return c_string.split(r':')
    return []


def dict_split(c_string):
    """ split an option string on commas, optionally surrounded by
    whitespace and split the resulting items again on equals signs,
    returning a dict """
    result = dict()
    if c_string:
        items = re.split(r'\s*,\s*', c_string)
        for item in items:
            if r'=' in item:
                key, value = item.split(r'=', 1)
                try:
                    result[key] = get_bool(value)
                except ValueError:
                    try:
                        result[key] = get_int(value)
                    except ValueError:
                        result[key] = value
            else:
                result[item] = True
    return result


def get_bool(val):
    """ given a string value of a boolean configuration option, return
    an actual bool (True or False) """
    # these values copied from ConfigParser.RawConfigParser.getboolean
    # with the addition of True and False
    truelist = ["1", "yes", "True", "true", "on"]
    falselist = ["0", "no", "False", "false", "off"]
    if val in truelist:
        return True
    elif val in falselist:
        return False
    else:
        raise ValueError("Not a boolean value", val)


def get_int(val):
    """ given a string value of an integer configuration option,
    return an actual int """
    return int(val)


def get_timeout(val):
    """ convert the timeout value into a float or None """
    if val is None:
        return val
    timeout = float(val)  # pass ValueError up the stack
    if timeout <= 0:
        return None
    return timeout


def get_size(value):
    """ Given a number of bytes in a human-readable format (e.g.,
    '512m', '2g'), get the absolute number of bytes as an integer """
    if value == -1:
        return value
    mat = re.match(r'(\d+)([KkMmGg])?', value)
    if not mat:
        raise ValueError("Not a valid size", value)
    rvalue = int(mat.group(1))
    mult = mat.group(2).lower()
    if mult == 'k':
        return rvalue * 1024
    elif mult == 'm':
        return rvalue * 1024 * 1024
    elif mult == 'g':
        return rvalue * 1024 * 1024 * 1024
    else:
        return rvalue


def get_gid(val):
    """ This takes a group name or gid and returns the corresponding
    gid. """
    try:
        return int(val)
    except ValueError:
        return int(grp.getgrnam(val)[2])


def get_uid(val):
    """ This takes a group name or gid and returns the corresponding
    gid. """
    try:
        return int(val)
    except ValueError:
        return int(pwd.getpwnam(val)[2])


# Options accepts keyword argument list with the following values:
#         default:    default value for the option
#         cmd:        command line switch
#         odesc:      option description
#         cf:         tuple containing section/option
#         cook:       method for parsing option
#         long_arg:   (True|False) specifies whether cmd is a long argument

# General options
CFILE = \
    Option('Specify configuration file',
           default=DEFAULT_CONFIG_LOCATION,
           cmd='-C',
           odesc='<conffile>',
           env="BCFG2_CONFIG")
LOCKFILE = \
    Option('Specify lockfile',
           default='/var/lock/bcfg2.run',
           odesc='<Path to lockfile>',
           cf=('components', 'lockfile'))
HELP = \
    Option('Print this usage message',
           default=False,
           cmd='-h')
VERSION = \
    Option('Print the version and exit',
           default=False,
           cmd='--version', long_arg=True)
DAEMON = \
    Option("Daemonize process, storing pid",
           default=None,
           cmd='-D',
           odesc='<pidfile>')
INSTALL_PREFIX = \
    Option('Installation location',
           default=DEFAULT_INSTALL_PREFIX,
           odesc='</path>',
           cf=('server', 'prefix'))
SENDMAIL_PATH = \
    Option('Path to sendmail',
           default='/usr/lib/sendmail',
           cf=('reports', 'sendmailpath'))
INTERACTIVE = \
    Option('Run interactively, prompting the user for each change',
           default=False,
           cmd='-I', )
ENCODING = \
    Option('Encoding of cfg files',
           default='UTF-8',
           cmd='-E',
           odesc='<encoding>',
           cf=('components', 'encoding'))
PARANOID_PATH = \
    Option('Specify path for paranoid file backups',
           default='/var/cache/bcfg2',
           odesc='<paranoid backup path>',
           cf=('paranoid', 'path'))
PARANOID_MAX_COPIES = \
    Option('Specify the number of paranoid copies you want',
           default=1,
           odesc='<max paranoid copies>',
           cf=('paranoid', 'max_copies'))
OMIT_LOCK_CHECK = \
    Option('Omit lock check',
           default=False,
           cmd='-O')
CORE_PROFILE = \
    Option('profile',
           default=False,
           cmd='-p')
SCHEMA_PATH = \
    Option('Path to XML Schema files',
           default='%s/share/bcfg2/schemas' % DEFAULT_INSTALL_PREFIX,
           cmd='--schema',
           odesc='<schema path>',
           cf=('lint', 'schema'),
           long_arg=True)
INTERPRETER = \
    Option("Python interpreter to use",
           default='best',
           cmd="--interpreter",
           odesc='<python|bpython|ipython|best>',
           cf=('bcfg2-info', 'interpreter'),
           long_arg=True)

# Metadata options (mdata section)
MDATA_OWNER = \
    Option('Default Path owner',
           default='root',
           odesc='owner permissions',
           cf=('mdata', 'owner'))
MDATA_GROUP = \
    Option('Default Path group',
           default='root',
           odesc='group permissions',
           cf=('mdata', 'group'))
MDATA_IMPORTANT = \
    Option('Default Path priority (importance)',
           default='False',
           odesc='Important entries are installed first',
           cf=('mdata', 'important'))
MDATA_MODE = \
    Option('Default mode for Path',
           default='644',
           odesc='octal file mode',
           cf=('mdata', 'mode'))
MDATA_SECONTEXT = \
    Option('Default SELinux context',
           default='__default__',
           odesc='SELinux context',
           cf=('mdata', 'secontext'))
MDATA_PARANOID = \
    Option('Default Path paranoid setting',
           default='true',
           odesc='Path paranoid setting',
           cf=('mdata', 'paranoid'))
MDATA_SENSITIVE = \
    Option('Default Path sensitive setting',
           default='false',
           odesc='Path sensitive setting',
           cf=('mdata', 'sensitive'))

# Server options
SERVER_REPOSITORY = \
    Option('Server repository path',
           default='/var/lib/bcfg2',
           cmd='-Q',
           odesc='<repository path>',
           cf=('server', 'repository'))
SERVER_PLUGINS = \
    Option('Server plugin list',
           # default server plugins
           default=['Bundler', 'Cfg', 'Metadata', 'Pkgmgr', 'Rules',
                    'SSHbase'],
           cf=('server', 'plugins'),
           cook=list_split)
SERVER_FILEMONITOR = \
    Option('Server file monitor',
           default='default',
           odesc='File monitoring driver',
           cf=('server', 'filemonitor'))
SERVER_FAM_IGNORE = \
    Option('File globs to ignore',
           default=['*~', '*#', '.#*', '*.swp', '*.swpx', '.*.swx',
                    'SCCS', '.svn', '4913', '.gitignore'],
           cf=('server', 'ignore_files'),
           cook=list_split)
SERVER_FAM_BLOCK = \
    Option('FAM blocks on startup until all events are processed',
           default=False,
           cook=get_bool,
           cf=('server', 'fam_blocking'))
SERVER_LISTEN_ALL = \
    Option('Listen on all interfaces',
           default=False,
           cmd='--listen-all',
           cf=('server', 'listen_all'),
           cook=get_bool,
           long_arg=True)
SERVER_LOCATION = \
    Option('Server Location',
           default='https://localhost:6789',
           cmd='-S',
           odesc='https://server:port',
           cf=('components', 'bcfg2'))
SERVER_KEY = \
    Option('Path to SSL key',
           default="/etc/pki/tls/private/bcfg2.key",
           cmd='--ssl-key',
           odesc='<ssl key>',
           cf=('communication', 'key'),
           long_arg=True)
SERVER_CERT = \
    Option('Path to SSL certificate',
           default="/etc/pki/tls/certs/bcfg2.crt",
           odesc='<ssl cert>',
           cf=('communication', 'certificate'))
SERVER_CA = \
    Option('Path to SSL CA Cert',
           default=None,
           odesc='<ca cert>',
           cf=('communication', 'ca'))
SERVER_PASSWORD = \
    Option('Communication Password',
           default=None,
           cmd='-x',
           odesc='<password>',
           cf=('communication', 'password'))
SERVER_PROTOCOL = \
    Option('Server Protocol',
           default='xmlrpc/ssl',
           cf=('communication', 'protocol'))
SERVER_BACKEND = \
    Option('Server Backend',
           default='best',
           cf=('server', 'backend'))
SERVER_DAEMON_USER = \
    Option('User to run the server daemon as',
           default=0,
           cf=('server', 'user'),
           cook=get_uid)
SERVER_DAEMON_GROUP = \
    Option('Group to run the server daemon as',
           default=0,
           cf=('server', 'group'),
           cook=get_gid)
SERVER_VCS_ROOT = \
    Option('Server VCS repository root',
           default=None,
           odesc='<VCS repository root>',
           cf=('server', 'vcs_root'))
SERVER_UMASK = \
    Option('Server umask',
           default='0077',
           odesc='<Server umask>',
           cf=('server', 'umask'))
SERVER_AUTHENTICATION = \
    Option('Default client authentication method',
           default='cert+password',
           odesc='{cert|bootstrap|cert+password}',
           cf=('communication', 'authentication'))
SERVER_CHILDREN = \
    Option('Spawn this number of children for the multiprocessing core. '
           'By default spawns children equivalent to the number of processors '
           'in the machine.',
           default=None,
           cmd='--children',
           odesc='<children>',
           cf=('server', 'children'),
           cook=get_int,
           long_arg=True)

# database options
DB_ENGINE = \
    Option('Database engine',
           default='sqlite3',
           cf=('database', 'engine'),
           deprecated_cf=('statistics', 'database_engine'))
DB_NAME = \
    Option('Database name',
           default=os.path.join(SERVER_REPOSITORY.default, "etc/bcfg2.sqlite"),
           cf=('database', 'name'),
           deprecated_cf=('statistics', 'database_name'))
DB_USER = \
    Option('Database username',
           default=None,
           cf=('database', 'user'),
           deprecated_cf=('statistics', 'database_user'))
DB_PASSWORD = \
    Option('Database password',
           default=None,
           cf=('database', 'password'),
           deprecated_cf=('statistics', 'database_password'))
DB_HOST = \
    Option('Database host',
           default='localhost',
           cf=('database', 'host'),
           deprecated_cf=('statistics', 'database_host'))
DB_PORT = \
    Option('Database port',
           default='',
           cf=('database', 'port'),
           deprecated_cf=('statistics', 'database_port'))

DB_OPTIONS = \
    Option('Database options',
           default=dict(),
           cf=('database', 'options'),
           cook=dict_split)

# Django options
WEB_CFILE = \
    Option('Web interface configuration file',
           default="/etc/bcfg2-web.conf",
           cmd='-W',
           odesc='<conffile>',
           cf=('reporting', 'config'),
           deprecated_cf=('statistics', 'web_prefix'),)
DJANGO_TIME_ZONE = \
    Option('Django timezone',
           default=None,
           cf=('reporting', 'time_zone'),
           deprecated_cf=('statistics', 'web_prefix'),)
DJANGO_DEBUG = \
    Option('Django debug',
           default=None,
           cf=('reporting', 'web_debug'),
           deprecated_cf=('statistics', 'web_prefix'),
           cook=get_bool,)
DJANGO_WEB_PREFIX = \
    Option('Web prefix',
           default=None,
           cf=('reporting', 'web_prefix'),
           deprecated_cf=('statistics', 'web_prefix'),)

# Reporting options
REPORTING_FILE_LIMIT = \
    Option('Reporting file size limit',
           default=get_size('1m'),
           cf=('reporting', 'file_limit'),
           cook=get_size,)

# Reporting options
REPORTING_TRANSPORT = \
    Option('Reporting transport',
           default='DirectStore',
           cf=('reporting', 'transport'),)

# Client options
CLIENT_KEY = \
    Option('Path to SSL key',
           default=None,
           cmd='--ssl-key',
           odesc='<ssl key>',
           cf=('communication', 'key'),
           long_arg=True)
CLIENT_CERT = \
    Option('Path to SSL certificate',
           default=None,
           cmd='--ssl-cert',
           odesc='<ssl cert>',
           cf=('communication', 'certificate'),
           long_arg=True)
CLIENT_CA = \
    Option('Path to SSL CA Cert',
           default=None,
           cmd='--ca-cert',
           odesc='<ca cert>',
           cf=('communication', 'ca'),
           long_arg=True)
CLIENT_SCNS = \
    Option('List of server commonNames',
           default=None,
           cmd='--ssl-cns',
           odesc='<CN1:CN2>',
           cf=('communication', 'serverCommonNames'),
           cook=list_split,
           long_arg=True)
CLIENT_PROFILE = \
    Option('Assert the given profile for the host',
           default=None,
           cmd='-p',
           odesc='<profile>',
           cf=('client', 'profile'))
CLIENT_RETRIES = \
    Option('The number of times to retry network communication',
           default='3',
           cmd='-R',
           odesc='<retry count>',
           cf=('communication', 'retries'))
CLIENT_RETRY_DELAY = \
    Option('The time in seconds to wait between retries',
           default='1',
           cmd='-y',
           odesc='<retry delay>',
           cf=('communication', 'retry_delay'))
CLIENT_DRYRUN = \
    Option('Do not actually change the system',
           default=False,
           cmd='-n')
CLIENT_EXTRA_DISPLAY = \
    Option('enable extra entry output',
           default=False,
           cmd='-e')
CLIENT_PARANOID = \
    Option('Make automatic backups of config files',
           default=False,
           cmd='-P',
           cf=('client', 'paranoid'),
           cook=get_bool)
CLIENT_DRIVERS = \
    Option('Specify tool driver set',
           default=Bcfg2.Client.Tools.default,
           cmd='-D',
           odesc='<driver1,driver2>',
           cf=('client', 'drivers'),
           cook=list_split)
CLIENT_CACHE = \
    Option('Store the configuration in a file',
           default=None,
           cmd='-c',
           odesc='<cache path>')
CLIENT_REMOVE = \
    Option('Force removal of additional configuration items',
           default=None,
           cmd='-r',
           odesc='<entry type|all>')
CLIENT_BUNDLE = \
    Option('Only configure the given bundle(s)',
           default=[],
           cmd='-b',
           odesc='<bundle:bundle>',
           cook=colon_split)
CLIENT_SKIPBUNDLE = \
    Option('Configure everything except the given bundle(s)',
           default=[],
           cmd='-B',
           odesc='<bundle:bundle>',
           cook=colon_split)
CLIENT_BUNDLEQUICK = \
    Option('Only verify/configure the given bundle(s)',
           default=False,
           cmd='-Q')
CLIENT_INDEP = \
    Option('Only configure independent entries, ignore bundles',
           default=False,
           cmd='-z')
CLIENT_SKIPINDEP = \
    Option('Do not configure independent entries',
           default=False,
           cmd='-Z')
CLIENT_KEVLAR = \
    Option('Run in kevlar (bulletproof) mode',
           default=False,
           cmd='-k', )
CLIENT_FILE = \
    Option('Configure from a file rather than querying the server',
           default=None,
           cmd='-f',
           odesc='<specification path>')
CLIENT_QUICK = \
    Option('Disable some checksum verification',
           default=False,
           cmd='-q')
CLIENT_USER = \
    Option('The user to provide for authentication',
           default='root',
           cmd='-u',
           odesc='<user>',
           cf=('communication', 'user'))
CLIENT_SERVICE_MODE = \
    Option('Set client service mode',
           default='default',
           cmd='-s',
           odesc='<default|disabled|build>')
CLIENT_TIMEOUT = \
    Option('Set the client XML-RPC timeout',
           default=90,
           cmd='-t',
           odesc='<timeout>',
           cf=('communication', 'timeout'))
CLIENT_DLIST = \
    Option('Run client in server decision list mode',
           default='none',
           cmd='-l',
           odesc='<whitelist|blacklist|none>',
           cf=('client', 'decision'))
CLIENT_DECISION_LIST = \
    Option('Decision List',
           default=False,
           cmd='--decision-list',
           odesc='<file>',
           long_arg=True)
CLIENT_EXIT_ON_PROBE_FAILURE = \
    Option("The client should exit if a probe fails",
           default=True,
           cmd='--exit-on-probe-failure',
           long_arg=True,
           cf=('client', 'exit_on_probe_failure'),
           cook=get_bool)
CLIENT_PROBE_TIMEOUT = \
    Option("Timeout when running client probes",
           default=None,
           cf=('client', 'probe_timeout'),
           cook=get_timeout)
CLIENT_COMMAND_TIMEOUT = \
    Option("Timeout when client runs other external commands (not probes)",
           default=None,
           cf=('client', 'command_timeout'),
           cook=get_timeout)

# bcfg2-test and bcfg2-lint options
TEST_NOSEOPTS = \
    Option('Options to pass to nosetests. Only honored with --children 0',
           default=[],
           cmd='--nose-options',
           odesc='<opts>',
           cf=('bcfg2_test', 'nose_options'),
           cook=shlex.split,
           long_arg=True)
TEST_IGNORE = \
    Option('Ignore these entries if they fail to build.',
           default=[],
           cmd='--ignore',
           odesc='<Type>:<name>,<Type>:<name>',
           cf=('bcfg2_test', 'ignore_entries'),
           cook=list_split,
           long_arg=True)
TEST_CHILDREN = \
    Option('Spawn this number of children for bcfg2-test (python 2.6+)',
           default=0,
           cmd='--children',
           odesc='<children>',
           cf=('bcfg2_test', 'children'),
           cook=get_int,
           long_arg=True)
TEST_XUNIT = \
    Option('Output an XUnit result file with --children',
           default=None,
           cmd='--xunit',
           odesc='<xunit file>',
           cf=('bcfg2_test', 'xunit'),
           long_arg=True)
LINT_CONFIG = \
    Option('Specify bcfg2-lint configuration file',
           default='/etc/bcfg2-lint.conf',
           cmd='--lint-config',
           odesc='<conffile>',
           long_arg=True)
LINT_PLUGINS = \
    Option('bcfg2-lint plugin list',
           default=None,  # default is Bcfg2.Server.Lint.__all__
           cf=('lint', 'plugins'),
           cook=list_split)
LINT_SHOW_ERRORS = \
    Option('Show error handling',
           default=False,
           cmd='--list-errors',
           long_arg=True)
LINT_FILES_ON_STDIN = \
    Option('Operate on a list of files supplied on stdin',
           default=False,
           cmd='--stdin',
           long_arg=True)

# individual client tool options
CLIENT_APT_TOOLS_INSTALL_PATH = \
    Option('Apt tools install path',
           default='/usr',
           cf=('APT', 'install_path'))
CLIENT_APT_TOOLS_VAR_PATH = \
    Option('Apt tools var path',
           default='/var',
           cf=('APT', 'var_path'))
CLIENT_SYSTEM_ETC_PATH = \
    Option('System etc path',
           default='/etc',
           cf=('APT', 'etc_path'))
CLIENT_PORTAGE_BINPKGONLY = \
    Option('Portage binary packages only',
           default=False,
           cf=('Portage', 'binpkgonly'),
           cook=get_bool)
CLIENT_RPM_INSTALLONLY = \
    Option('RPM install-only packages',
           default=['kernel', 'kernel-bigmem', 'kernel-enterprise',
                    'kernel-smp', 'kernel-modules', 'kernel-debug',
                    'kernel-unsupported', 'kernel-devel', 'kernel-source',
                    'kernel-default', 'kernel-largesmp-devel',
                    'kernel-largesmp', 'kernel-xen', 'gpg-pubkey'],
           cf=('RPM', 'installonlypackages'),
           deprecated_cf=('RPMng', 'installonlypackages'),
           cook=list_split)
CLIENT_RPM_PKG_CHECKS = \
    Option("Perform RPM package checks",
           default=True,
           cf=('RPM', 'pkg_checks'),
           deprecated_cf=('RPMng', 'pkg_checks'),
           cook=get_bool)
CLIENT_RPM_PKG_VERIFY = \
    Option("Perform RPM package verify",
           default=True,
           cf=('RPM', 'pkg_verify'),
           deprecated_cf=('RPMng', 'pkg_verify'),
           cook=get_bool)
CLIENT_RPM_INSTALLED_ACTION = \
    Option("RPM installed action",
           default="install",
           cf=('RPM', 'installed_action'),
           deprecated_cf=('RPMng', 'installed_action'))
CLIENT_RPM_ERASE_FLAGS = \
    Option("RPM erase flags",
           default=["allmatches"],
           cf=('RPM', 'erase_flags'),
           deprecated_cf=('RPMng', 'erase_flags'),
           cook=list_split)
CLIENT_RPM_VERSION_FAIL_ACTION = \
    Option("RPM version fail action",
           default="upgrade",
           cf=('RPM', 'version_fail_action'),
           deprecated_cf=('RPMng', 'version_fail_action'))
CLIENT_RPM_VERIFY_FAIL_ACTION = \
    Option("RPM verify fail action",
           default="reinstall",
           cf=('RPM', 'verify_fail_action'),
           deprecated_cf=('RPMng', 'verify_fail_action'))
CLIENT_RPM_VERIFY_FLAGS = \
    Option("RPM verify flags",
           default=[],
           cf=('RPM', 'verify_flags'),
           deprecated_cf=('RPMng', 'verify_flags'),
           cook=list_split)
CLIENT_YUM24_INSTALLONLY = \
    Option('YUM24 install-only packages',
           default=['kernel', 'kernel-bigmem', 'kernel-enterprise',
                    'kernel-smp', 'kernel-modules', 'kernel-debug',
                    'kernel-unsupported', 'kernel-devel', 'kernel-source',
                    'kernel-default', 'kernel-largesmp-devel',
                    'kernel-largesmp', 'kernel-xen', 'gpg-pubkey'],
           cf=('YUM24', 'installonlypackages'),
           cook=list_split)
CLIENT_YUM24_PKG_CHECKS = \
    Option("Perform YUM24 package checks",
           default=True,
           cf=('YUM24', 'pkg_checks'),
           cook=get_bool)
CLIENT_YUM24_PKG_VERIFY = \
    Option("Perform YUM24 package verify",
           default=True,
           cf=('YUM24', 'pkg_verify'),
           cook=get_bool)
CLIENT_YUM24_INSTALLED_ACTION = \
    Option("YUM24 installed action",
           default="install",
           cf=('YUM24', 'installed_action'))
CLIENT_YUM24_ERASE_FLAGS = \
    Option("YUM24 erase flags",
           default=["allmatches"],
           cf=('YUM24', 'erase_flags'),
           cook=list_split)
CLIENT_YUM24_VERSION_FAIL_ACTION = \
    Option("YUM24 version fail action",
           cf=('YUM24', 'version_fail_action'),
           default="upgrade")
CLIENT_YUM24_VERIFY_FAIL_ACTION = \
    Option("YUM24 verify fail action",
           default="reinstall",
           cf=('YUM24', 'verify_fail_action'))
CLIENT_YUM24_VERIFY_FLAGS = \
    Option("YUM24 verify flags",
           default=[],
           cf=('YUM24', 'verify_flags'),
           cook=list_split)
CLIENT_YUM24_AUTODEP = \
    Option("YUM24 autodependency processing",
           default=True,
           cf=('YUM24', 'autodep'),
           cook=get_bool)
CLIENT_YUM_PKG_CHECKS = \
    Option("Perform YUM package checks",
           default=True,
           cf=('YUM', 'pkg_checks'),
           deprecated_cf=('YUMng', 'pkg_checks'),
           cook=get_bool)
CLIENT_YUM_PKG_VERIFY = \
    Option("Perform YUM package verify",
           default=True,
           cf=('YUM', 'pkg_verify'),
           deprecated_cf=('YUMng', 'pkg_verify'),
           cook=get_bool)
CLIENT_YUM_INSTALLED_ACTION = \
    Option("YUM installed action",
           default="install",
           cf=('YUM', 'installed_action'),
           deprecated_cf=('YUMng', 'installed_action'))
CLIENT_YUM_VERSION_FAIL_ACTION = \
    Option("YUM version fail action",
           default="upgrade",
           cf=('YUM', 'version_fail_action'),
           deprecated_cf=('YUMng', 'version_fail_action'))
CLIENT_YUM_VERIFY_FAIL_ACTION = \
    Option("YUM verify fail action",
           default="reinstall",
           cf=('YUM', 'verify_fail_action'),
           deprecated_cf=('YUMng', 'verify_fail_action'))
CLIENT_YUM_VERIFY_FLAGS = \
    Option("YUM verify flags",
           default=[],
           cf=('YUM', 'verify_flags'),
           deprecated_cf=('YUMng', 'verify_flags'),
           cook=list_split)
CLIENT_POSIX_UID_WHITELIST = \
    Option("UID ranges the POSIXUsers tool will manage",
           default=[],
           cf=('POSIXUsers', 'uid_whitelist'),
           cook=list_split)
CLIENT_POSIX_GID_WHITELIST = \
    Option("GID ranges the POSIXUsers tool will manage",
           default=[],
           cf=('POSIXUsers', 'gid_whitelist'),
           cook=list_split)
CLIENT_POSIX_UID_BLACKLIST = \
    Option("UID ranges the POSIXUsers tool will not manage",
           default=[],
           cf=('POSIXUsers', 'uid_blacklist'),
           cook=list_split)
CLIENT_POSIX_GID_BLACKLIST = \
    Option("GID ranges the POSIXUsers tool will not manage",
           default=[],
           cf=('POSIXUsers', 'gid_blacklist'),
           cook=list_split)

# Logging options
LOGGING_FILE_PATH = \
    Option('Set path of file log',
           default=None,
           cmd='-o',
           odesc='<path>',
           cf=('logging', 'path'))
LOGGING_SYSLOG = \
    Option('Log to syslog',
           default=True,
           cook=get_bool,
           cf=('logging', 'syslog'))
DEBUG = \
    Option("Enable debugging output",
           default=False,
           cmd='-d',
           cook=get_bool,
           cf=('logging', 'debug'))
VERBOSE = \
    Option("Enable verbose output",
           default=False,
           cmd='-v',
           cook=get_bool,
           cf=('logging', 'verbose'))
LOG_PERFORMANCE = \
    Option("Periodically log performance statistics",
           default=False,
           cf=('logging', 'performance'))
PERFLOG_INTERVAL = \
    Option("Performance statistics logging interval in seconds",
           default=300.0,
           cook=get_timeout,
           cf=('logging', 'performance_interval'))

# Plugin-specific options
CFG_VALIDATION = \
    Option('Run validation on Cfg files',
           default=True,
           cmd='--cfg-validation',
           cf=('cfg', 'validation'),
           long_arg=True,
           cook=get_bool)

# bcfg2-crypt options
ENCRYPT = \
    Option('Encrypt the specified file',
           default=False,
           cmd='--encrypt',
           long_arg=True)
DECRYPT = \
    Option('Decrypt the specified file',
           default=False,
           cmd='--decrypt',
           long_arg=True)
CRYPT_STDOUT = \
    Option('Decrypt or encrypt the specified file to stdout',
           default=False,
           cmd='--stdout',
           long_arg=True)
CRYPT_PASSPHRASE = \
    Option('Encryption passphrase name',
           default=None,
           cmd='-p',
           odesc='<passphrase>')
CRYPT_XPATH = \
    Option('XPath expression to select elements to encrypt',
           default=None,
           cmd='--xpath',
           odesc='<xpath>',
           long_arg=True)
CRYPT_PROPERTIES = \
    Option('Encrypt the specified file as a Properties file',
           default=False,
           cmd="--properties",
           long_arg=True)
CRYPT_CFG = \
    Option('Encrypt the specified file as a Cfg file',
           default=False,
           cmd="--cfg",
           long_arg=True)
CRYPT_REMOVE = \
    Option('Remove the plaintext file after encrypting',
           default=False,
           cmd="--remove",
           long_arg=True)

# Option groups
CLI_COMMON_OPTIONS = dict(configfile=CFILE,
                          debug=DEBUG,
                          help=HELP,
                          version=VERSION,
                          verbose=VERBOSE,
                          encoding=ENCODING,
                          logging=LOGGING_FILE_PATH,
                          syslog=LOGGING_SYSLOG)

DAEMON_COMMON_OPTIONS = dict(daemon=DAEMON,
                             umask=SERVER_UMASK,
                             listen_all=SERVER_LISTEN_ALL,
                             daemon_uid=SERVER_DAEMON_USER,
                             daemon_gid=SERVER_DAEMON_GROUP)

SERVER_COMMON_OPTIONS = dict(repo=SERVER_REPOSITORY,
                             plugins=SERVER_PLUGINS,
                             password=SERVER_PASSWORD,
                             filemonitor=SERVER_FILEMONITOR,
                             ignore=SERVER_FAM_IGNORE,
                             fam_blocking=SERVER_FAM_BLOCK,
                             location=SERVER_LOCATION,
                             key=SERVER_KEY,
                             cert=SERVER_CERT,
                             ca=SERVER_CA,
                             protocol=SERVER_PROTOCOL,
                             web_configfile=WEB_CFILE,
                             backend=SERVER_BACKEND,
                             vcs_root=SERVER_VCS_ROOT,
                             authentication=SERVER_AUTHENTICATION,
                             perflog=LOG_PERFORMANCE,
                             perflog_interval=PERFLOG_INTERVAL,
                             children=SERVER_CHILDREN)

CRYPT_OPTIONS = dict(encrypt=ENCRYPT,
                     decrypt=DECRYPT,
                     crypt_stdout=CRYPT_STDOUT,
                     passphrase=CRYPT_PASSPHRASE,
                     xpath=CRYPT_XPATH,
                     properties=CRYPT_PROPERTIES,
                     cfg=CRYPT_CFG,
                     remove=CRYPT_REMOVE)

DRIVER_OPTIONS = \
    dict(apt_install_path=CLIENT_APT_TOOLS_INSTALL_PATH,
         apt_var_path=CLIENT_APT_TOOLS_VAR_PATH,
         apt_etc_path=CLIENT_SYSTEM_ETC_PATH,
         portage_binpkgonly=CLIENT_PORTAGE_BINPKGONLY,
         rpm_installonly=CLIENT_RPM_INSTALLONLY,
         rpm_pkg_checks=CLIENT_RPM_PKG_CHECKS,
         rpm_pkg_verify=CLIENT_RPM_PKG_VERIFY,
         rpm_installed_action=CLIENT_RPM_INSTALLED_ACTION,
         rpm_erase_flags=CLIENT_RPM_ERASE_FLAGS,
         rpm_version_fail_action=CLIENT_RPM_VERSION_FAIL_ACTION,
         rpm_verify_fail_action=CLIENT_RPM_VERIFY_FAIL_ACTION,
         rpm_verify_flags=CLIENT_RPM_VERIFY_FLAGS,
         yum24_installonly=CLIENT_YUM24_INSTALLONLY,
         yum24_pkg_checks=CLIENT_YUM24_PKG_CHECKS,
         yum24_pkg_verify=CLIENT_YUM24_PKG_VERIFY,
         yum24_installed_action=CLIENT_YUM24_INSTALLED_ACTION,
         yum24_erase_flags=CLIENT_YUM24_ERASE_FLAGS,
         yum24_version_fail_action=CLIENT_YUM24_VERSION_FAIL_ACTION,
         yum24_verify_fail_action=CLIENT_YUM24_VERIFY_FAIL_ACTION,
         yum24_verify_flags=CLIENT_YUM24_VERIFY_FLAGS,
         yum24_autodep=CLIENT_YUM24_AUTODEP,
         yum_pkg_checks=CLIENT_YUM_PKG_CHECKS,
         yum_pkg_verify=CLIENT_YUM_PKG_VERIFY,
         yum_installed_action=CLIENT_YUM_INSTALLED_ACTION,
         yum_version_fail_action=CLIENT_YUM_VERSION_FAIL_ACTION,
         yum_verify_fail_action=CLIENT_YUM_VERIFY_FAIL_ACTION,
         yum_verify_flags=CLIENT_YUM_VERIFY_FLAGS,
         posix_uid_whitelist=CLIENT_POSIX_UID_WHITELIST,
         posix_gid_whitelist=CLIENT_POSIX_UID_WHITELIST,
         posix_uid_blacklist=CLIENT_POSIX_UID_BLACKLIST,
         posix_gid_blacklist=CLIENT_POSIX_UID_BLACKLIST)

CLIENT_COMMON_OPTIONS = \
    dict(extra=CLIENT_EXTRA_DISPLAY,
         quick=CLIENT_QUICK,
         lockfile=LOCKFILE,
         drivers=CLIENT_DRIVERS,
         dryrun=CLIENT_DRYRUN,
         paranoid=CLIENT_PARANOID,
         ppath=PARANOID_PATH,
         max_copies=PARANOID_MAX_COPIES,
         bundle=CLIENT_BUNDLE,
         skipbundle=CLIENT_SKIPBUNDLE,
         bundle_quick=CLIENT_BUNDLEQUICK,
         indep=CLIENT_INDEP,
         skipindep=CLIENT_SKIPINDEP,
         file=CLIENT_FILE,
         interactive=INTERACTIVE,
         cache=CLIENT_CACHE,
         profile=CLIENT_PROFILE,
         remove=CLIENT_REMOVE,
         server=SERVER_LOCATION,
         user=CLIENT_USER,
         password=SERVER_PASSWORD,
         retries=CLIENT_RETRIES,
         retry_delay=CLIENT_RETRY_DELAY,
         kevlar=CLIENT_KEVLAR,
         omit_lock_check=OMIT_LOCK_CHECK,
         decision=CLIENT_DLIST,
         servicemode=CLIENT_SERVICE_MODE,
         key=CLIENT_KEY,
         certificate=CLIENT_CERT,
         ca=CLIENT_CA,
         serverCN=CLIENT_SCNS,
         timeout=CLIENT_TIMEOUT,
         decision_list=CLIENT_DECISION_LIST,
         probe_exit=CLIENT_EXIT_ON_PROBE_FAILURE,
         probe_timeout=CLIENT_PROBE_TIMEOUT,
         command_timeout=CLIENT_COMMAND_TIMEOUT)
CLIENT_COMMON_OPTIONS.update(DRIVER_OPTIONS)
CLIENT_COMMON_OPTIONS.update(CLI_COMMON_OPTIONS)

DATABASE_COMMON_OPTIONS = dict(web_configfile=WEB_CFILE,
                               configfile=CFILE,
                               db_engine=DB_ENGINE,
                               db_name=DB_NAME,
                               db_user=DB_USER,
                               db_password=DB_PASSWORD,
                               db_host=DB_HOST,
                               db_port=DB_PORT,
                               db_options=DB_OPTIONS,
                               time_zone=DJANGO_TIME_ZONE,
                               django_debug=DJANGO_DEBUG,
                               web_prefix=DJANGO_WEB_PREFIX)

REPORTING_COMMON_OPTIONS = dict(reporting_file_limit=REPORTING_FILE_LIMIT,
                                reporting_transport=REPORTING_TRANSPORT)

TEST_COMMON_OPTIONS = dict(noseopts=TEST_NOSEOPTS,
                           test_ignore=TEST_IGNORE,
                           children=TEST_CHILDREN,
                           xunit=TEST_XUNIT,
                           validate=CFG_VALIDATION)

INFO_COMMON_OPTIONS = dict(ppath=PARANOID_PATH,
                           max_copies=PARANOID_MAX_COPIES)
INFO_COMMON_OPTIONS.update(CLI_COMMON_OPTIONS)
INFO_COMMON_OPTIONS.update(SERVER_COMMON_OPTIONS)


class OptionParser(OptionSet):
    """
       OptionParser bootstraps option parsing,
       getting the value of the config file
    """
    def __init__(self, args, argv=None, quiet=False):
        if argv is None:
            argv = sys.argv[1:]
        # the bootstrap is always quiet, since it's running with a
        # default config file and so might produce warnings otherwise
        self.bootstrap = OptionSet([('configfile', CFILE)], quiet=True)
        self.bootstrap.parse(argv, do_getopt=False)
        OptionSet.__init__(self, args, configfile=self.bootstrap['configfile'],
                           quiet=quiet)
        self.optinfo = copy.copy(args)
        # these will be set by parse() and then used by reparse()
        self.argv = []
        self.do_getopt = True

    def reparse(self):
        """ parse the options again, taking any changes (e.g., to the
        config file) into account """
        for key, opt in self.optinfo.items():
            self[key] = opt
        if "args" not in self.optinfo:
            del self['args']
        self.parse(self.argv, self.do_getopt)

    def parse(self, argv, do_getopt=True):
        self.argv = argv
        self.do_getopt = do_getopt
        OptionSet.parse(self, self.argv, do_getopt=self.do_getopt)

    def add_option(self, name, opt):
        """ Add an option to the parser """
        self[name] = opt
        self.optinfo[name] = opt

    def update(self, optdict):
        dict.update(self, optdict)
        self.optinfo.update(optdict)
