"""Option parsing library for utilities."""

import re
import os
import sys
import copy
import shlex
import getopt
import Bcfg2.Client.Tools
# Compatibility imports
from Bcfg2.Bcfg2Py3k import ConfigParser


def bool_cook(x):
    if x:
        return True
    else:
        return False


class OptionFailure(Exception):
    pass

DEFAULT_CONFIG_LOCATION = '/etc/bcfg2.conf'
DEFAULT_INSTALL_PREFIX = '/usr'


class DefaultConfigParser(ConfigParser.ConfigParser):
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
    def get_cooked_value(self, value):
        if self.boolean:
            return True
        if self.cook:
            return self.cook(value)
        else:
            return value

    def __init__(self, desc, default, cmd=False, odesc=False,
                 env=False, cf=False, cook=False, long_arg=False):
        self.desc = desc
        self.default = default
        self.cmd = cmd
        self.long = long_arg
        if not self.long:
            if cmd and (cmd[0] != '-' or len(cmd) != 2):
                raise OptionFailure("Poorly formed command %s" % cmd)
        else:
            if cmd and (not cmd.startswith('--')):
                raise OptionFailure("Poorly formed command %s" % cmd)
        self.odesc = odesc
        self.env = env
        self.cf = cf
        self.boolean = False
        if not odesc and not cook:
            self.boolean = True
        self.cook = cook

    def buildHelpMessage(self):
        msg = ''
        if self.cmd:
            if not self.long:
                msg = self.cmd.ljust(3)
            else:
                msg = self.cmd
            if self.odesc:
                if self.long:
                    msg = "%-28s" % ("%s=%s" % (self.cmd, self.odesc))
                else:
                    msg += '%-25s' % (self.odesc)
            else:
                msg += '%-25s' % ('')
            msg += "%s\n" % self.desc
        return msg

    def buildGetopt(self):
        gstr = ''
        if self.long:
            return gstr
        if self.cmd:
            gstr = self.cmd[1]
            if self.odesc:
                gstr += ':'
        return gstr

    def buildLongGetopt(self):
        if self.odesc:
            return self.cmd[2:] + '='
        else:
            return self.cmd[2:]

    def parse(self, opts, rawopts, configparser=None):
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
            data = rawopts[rawopts.index(self.cmd) + 1]
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
        # Default value not cooked
        self.value = self.default


class OptionSet(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args)
        self.hm = self.buildHelpMessage()
        if 'configfile' in kwargs:
            self.cfile = kwargs['configfile']
        else:
            self.cfile = DEFAULT_CONFIG_LOCATION
        self.cfp = DefaultConfigParser()
        if (len(self.cfp.read(self.cfile)) == 0 and
            ('quiet' not in kwargs or not kwargs['quiet'])):
            print("Warning! Unable to read specified configuration file: %s" %
                  self.cfile)

    def buildGetopt(self):
        return ''.join([opt.buildGetopt() for opt in list(self.values())])

    def buildLongGetopt(self):
        return [opt.buildLongGetopt() for opt in list(self.values())
                if opt.long]

    def buildHelpMessage(self):
        if hasattr(self, 'hm'):
            return self.hm
        hlist = []  # list of _non-empty_ help messages
        for opt in list(self.values()):
            hm = opt.buildHelpMessage()
            if hm != '':
                hlist.append(hm)
        return '     '.join(hlist)

    def helpExit(self, msg='', code=1):
        if msg:
            print(msg)
        print("Usage:\n     %s" % self.buildHelpMessage())
        raise SystemExit(code)

    def parse(self, argv, do_getopt=True):
        '''Parse options from command line.'''
        if do_getopt:
            try:
                opts, args = getopt.getopt(argv, self.buildGetopt(),
                                           self.buildLongGetopt())
            except getopt.GetoptError:
                err = sys.exc_info()[1]
                self.helpExit(err)
            if '-h' in argv:
                self.helpExit('', 0)
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


def list_split(c_string):
    if c_string:
        return re.split("\s*,\s*", c_string)
    return []


def colon_split(c_string):
    if c_string:
        return c_string.split(':')
    return []


def get_bool(s):
    # these values copied from ConfigParser.RawConfigParser.getboolean
    # with the addition of True and False
    truelist = ["1", "yes", "True", "true", "on"]
    falselist = ["0", "no", "False", "false", "off"]
    if s in truelist:
        return True
    elif s in falselist:
        return False
    else:
        raise ValueError

"""
Options:

    Accepts keyword argument list with the following values:

        default:    default value for the option
        cmd:        command line switch
        odesc:      option description
        cf:         tuple containing section/option
        cook:       method for parsing option
        long_arg:   (True|False) specifies whether cmd is a long argument
"""
# General options
CFILE = \
    Option('Specify configuration file',
           default=DEFAULT_CONFIG_LOCATION,
           cmd='-C',
           odesc='<conffile>')
LOCKFILE = \
    Option('Specify lockfile',
           default='/var/lock/bcfg2.run',
           odesc='<Path to lockfile>',
           cf=('components', 'lockfile'))
HELP = \
    Option('Print this usage message',
           default=False,
           cmd='-h')
DEBUG = \
    Option("Enable debugging output",
           default=False,
           cmd='-d')
VERBOSE = \
    Option("Enable verbose output",
           default=False,
           cmd='-v')
DAEMON = \
    Option("Daemonize process, storing pid",
           default=False,
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
           cmd='-p', )
SCHEMA_PATH = \
    Option('Path to XML Schema files',
           default='%s/share/bcfg2/schemas' % DEFAULT_INSTALL_PREFIX,
           cmd='--schema',
           odesc='<schema path>',
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
MDATA_PERMS = \
    Option('Default Path permissions',
           default='644',
           odesc='octal permissions',
           cf=('mdata', 'perms'))
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
           default=[
                    'Bundler',
                    'Cfg',
                    'Metadata',
                    'Pkgmgr',
                    'Rules',
                    'SSHbase',
                   ],
           cf=('server', 'plugins'),
           cook=list_split)
SERVER_MCONNECT = \
    Option('Server Metadata Connector list',
           default=['Probes'],
           cf=('server', 'connectors'),
           cook=list_split)
SERVER_FILEMONITOR = \
    Option('Server file monitor',
           default='default',
           odesc='File monitoring driver',
           cf=('server', 'filemonitor'))
SERVER_FAM_IGNORE = \
    Option('File globs to ignore',
           default=[
                    '*~',
                    '*#',
                    '.#*',
                    '*.swp',
                    '.*.swx',
                    'SCCS',
                    '.svn',
                    '4913',
                    '.gitignore',
                   ],
           cf=('server', 'ignore_files'),
           cook=list_split)
SERVER_LISTEN_ALL = \
    Option('Listen on all interfaces',
           default=False,
           cmd='--listen-all',
           odesc='True|False',
           cf=('server', 'listen_all'),
           cook=get_bool,
           long_arg=True)
SERVER_LOCATION = \
    Option('Server Location',
           default='https://localhost:6789',
           cmd='-S',
           odesc='https://server:port',
           cf=('components', 'bcfg2'))
SERVER_STATIC = \
    Option('Server runs on static port',
           default=False,
           cf=('components', 'bcfg2'),
           cook=bool_cook)
SERVER_KEY = \
    Option('Path to SSL key',
           default=False,
           cmd='--ssl-key',
           odesc='<ssl key>',
           cf=('communication', 'key'),
           long_arg=True)
SERVER_CERT = \
    Option('Path to SSL certificate',
           default='/etc/bcfg2.key',
           odesc='<ssl cert>',
           cf=('communication', 'certificate'))
SERVER_CA = \
    Option('Path to SSL CA Cert',
           default=None,
           odesc='<ca cert>',
           cf=('communication', 'ca'))
SERVER_PASSWORD = \
    Option('Communication Password',
           default=False,
           cmd='-x',
           odesc='<password>',
           cf=('communication', 'password'))
SERVER_PROTOCOL = \
    Option('Server Protocol',
           default='xmlrpc/ssl',
           cf=('communication', 'procotol'))

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
           default=False,
           cmd='-p',
           odesc='<profile>')
CLIENT_RETRIES = \
    Option('The number of times to retry network communication',
           default='3',
           cmd='-R',
           odesc='<retry count>',
           cf=('communication', 'retries'))
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
           default=False,
           cmd='-c',
           odesc='<cache path>')
CLIENT_REMOVE = \
    Option('Force removal of additional configuration items',
           default=False,
           cmd='-r',
           odesc='<entry type|all>')
CLIENT_BUNDLE = \
    Option('Only configure the given bundle(s)',
           default=[],
           cmd='-b',
           odesc='<bundle:bundle>',
           cook=colon_split)
CLIENT_BUNDLEQUICK = \
    Option('only verify/configure the given bundle(s)',
           default=False,
           cmd='-Q')
CLIENT_INDEP = \
    Option('Only configure independent entries, ignore bundles',
           default=False,
           cmd='-z')
CLIENT_KEVLAR = \
    Option('Run in kevlar (bulletproof) mode',
           default=False,
           cmd='-k', )
CLIENT_FILE = \
    Option('Configure from a file rather than querying the server',
           default=False,
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

# bcfg2-test and bcfg2-lint options
TEST_NOSEOPTS = \
    Option('Options to pass to nosetests',
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
LINT_CONFIG = \
    Option('Specify bcfg2-lint configuration file',
           default='/etc/bcfg2-lint.conf',
           cmd='--lint-config',
           odesc='<conffile>',
           long_arg=True)
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

# APT client tool options
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

# Logging options
LOGGING_FILE_PATH = \
    Option('Set path of file log',
           default=None,
           cmd='-o',
           odesc='<path>',
           cf=('logging', 'path'))

# Plugin-specific options
CFG_VALIDATION = \
    Option('Run validation on Cfg files',
           default=True,
           cmd='--cfg-validation',
           cf=('cfg', 'validation'),
           long_arg=True, cook=get_bool)


# Option groups
CLI_COMMON_OPTIONS = dict(configfile=CFILE,
                          debug=DEBUG,
                          help=HELP,
                          verbose=VERBOSE,
                          encoding=ENCODING,
                          logging=LOGGING_FILE_PATH)

DAEMON_COMMON_OPTIONS = dict(daemon=DAEMON,
                             listen_all=SERVER_LISTEN_ALL)

SERVER_COMMON_OPTIONS = dict(repo=SERVER_REPOSITORY,
                             plugins=SERVER_PLUGINS,
                             password=SERVER_PASSWORD,
                             filemonitor=SERVER_FILEMONITOR,
                             ignore=SERVER_FAM_IGNORE,
                             location=SERVER_LOCATION,
                             static=SERVER_STATIC,
                             key=SERVER_KEY,
                             cert=SERVER_CERT,
                             ca=SERVER_CA,
                             protocol=SERVER_PROTOCOL)


class OptionParser(OptionSet):
    """
       OptionParser bootstraps option parsing,
       getting the value of the config file
    """
    def __init__(self, args):
        self.Bootstrap = OptionSet([('configfile', CFILE)], quiet=True)
        self.Bootstrap.parse(sys.argv[1:], do_getopt=False)
        OptionSet.__init__(self, args, configfile=self.Bootstrap['configfile'])
        self.optinfo = copy.copy(args)

    def HandleEvent(self, event):
        if 'configfile' not in self or not isinstance(self['configfile'], str):
            # we haven't parsed options yet, or CFILE wasn't included
            # in the options
            return
        if event.filename != self['configfile']:
            print("Got event for unknown file: %s" % event.filename)
            return
        if event.code2str() == 'deleted':
            return
        self.reparse()

    def reparse(self):
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
        self[name] = opt
        self.optinfo[name] = opt

    def update(self, optdict):
        dict.update(self, optdict)
        self.optinfo.update(optdict)
