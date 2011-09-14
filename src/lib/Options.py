"""Option parsing library for utilities."""
__revision__ = '$Revision$'

import getopt
import os
import sys
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

DEFAULT_CONFIG_LOCATION = '/etc/bcfg2.conf' #/etc/bcfg2.conf
DEFAULT_INSTALL_PREFIX = '/usr' #/usr

class Option(object):
    cfpath = DEFAULT_CONFIG_LOCATION
    __cfp = False

    def getCFP(self):
        if not self.__cfp:
            self.__cfp = ConfigParser.ConfigParser()
            self.__cfp.readfp(open(self.cfpath))
        return self.__cfp
    cfp = property(getCFP)

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
            return self.cmd[2:]+'='
        else:
            return self.cmd[2:]

    def parse(self, opts, rawopts):
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
        if self.cf:
            try:
                self.value = self.get_cooked_value(self.cfp.get(*self.cf))
                return
            except:
                pass
        # Default value not cooked
        self.value = self.default

class OptionSet(dict):
    def __init__(self, *args):
        dict.__init__(self, *args)
        self.hm = self.buildHelpMessage()

    def buildGetopt(self):
        return ''.join([opt.buildGetopt() for opt in list(self.values())])

    def buildLongGetopt(self):
        return [opt.buildLongGetopt() for opt in list(self.values()) if opt.long]

    def buildHelpMessage(self):
        if hasattr(self, 'hm'):
            return self.hm
        return '     '.join([opt.buildHelpMessage() for opt in list(self.values())])

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
                option.parse(opts, [])
            else:
                option.parse([], argv)
            if hasattr(option, 'value'):
                val = option.value
                self[key] = val

list_split = lambda x:x.replace(' ','').split(',')
flist_split = lambda x:list_split(x.replace(':', '').lower())

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

# General options
CFILE = Option('Specify configuration file', DEFAULT_CONFIG_LOCATION, cmd='-C',
               odesc='<conffile>')
LOCKFILE = Option('Specify lockfile',
           "/var/lock/bcfg2.run",
           cf=('components', 'lockfile'),
           odesc='<Path to lockfile>')
HELP = Option('Print this usage message', False, cmd='-h')
DEBUG = Option("Enable debugging output", False, cmd='-d')
VERBOSE = Option("Enable verbose output", False, cmd='-v')
DAEMON = Option("Daemonize process, storing pid", False,
                cmd='-D', odesc="<pidfile>")
INSTALL_PREFIX = Option('Installation location', cf=('server', 'prefix'),
                        default=DEFAULT_INSTALL_PREFIX, odesc='</path>')
SENDMAIL_PATH = Option('Path to sendmail', cf=('reports', 'sendmailpath'),
                       default='/usr/lib/sendmail')
INTERACTIVE = Option('Run interactively, prompting the user for each change',
                     default=False,
                     cmd='-I', )
ENCODING = Option('Encoding of cfg files',
                  default='UTF-8',
                  cmd='-E',
                  odesc='<encoding>',
                  cf=('components', 'encoding'))
PARANOID_PATH = Option('Specify path for paranoid file backups',
                       default='/var/cache/bcfg2', cf=('paranoid', 'path'),
                       odesc='<paranoid backup path>')
PARANOID_MAX_COPIES = Option('Specify the number of paranoid copies you want',
                             default=1, cf=('paranoid', 'max_copies'),
                             odesc='<max paranoid copies>')
OMIT_LOCK_CHECK = Option('Omit lock check', default=False, cmd='-O')
CORE_PROFILE = Option('profile',
                      default=False, cmd='-p', )
FILES_ON_STDIN = Option('Operate on a list of files supplied on stdin',
                        cmd='--stdin', default=False, long_arg=True)
SCHEMA_PATH = Option('Path to XML Schema files', cmd='--schema',
                     odesc='<schema path>',
                     default="%s/share/bcfg2/schemas" % DEFAULT_INSTALL_PREFIX,
                     long_arg=True)
REQUIRE_SCHEMA = Option("Require property files to have matching schema files",
                        cmd="--require-schema", default=False, long_arg=True)

# Metadata options
MDATA_OWNER = Option('Default Path owner',
                     default='root', cf=('mdata', 'owner'),
                     odesc='owner permissions')
MDATA_GROUP = Option('Default Path group',
                     default='root', cf=('mdata', 'group'),
                     odesc='group permissions')
MDATA_IMPORTANT = Option('Default Path priority (importance)',
                     default='False', cf=('mdata', 'important'),
                     odesc='Important entries are installed first')
MDATA_PERMS = Option('Default Path permissions',
                     '644', cf=('mdata', 'perms'),
                     odesc='octal permissions')
MDATA_PARANOID = Option('Default Path paranoid setting',
                     'false', cf=('mdata', 'paranoid'),
                     odesc='Path paranoid setting')
MDATA_SENSITIVE = Option('Default Path sensitive setting',
                     'false', cf=('mdata', 'sensitive'),
                     odesc='Path sensitive setting')

# Server options
SERVER_REPOSITORY = Option('Server repository path', '/var/lib/bcfg2',
                           cf=('server', 'repository'), cmd='-Q',
                           odesc='<repository path>')
SERVER_PLUGINS = Option('Server plugin list', cf=('server', 'plugins'),
                        # default server plugins
                        default=[
                                 'Bundler',
                                 'Cfg',
                                 'Metadata',
                                 'Pkgmgr',
                                 'Rules',
                                 'SSHbase',
                                ],
                        cook=list_split)
SERVER_MCONNECT = Option('Server Metadata Connector list', cook=list_split,
                         cf=('server', 'connectors'), default=['Probes'], )
SERVER_FILEMONITOR = Option('Server file monitor', cf=('server', 'filemonitor'),
                            default='default', odesc='File monitoring driver')
SERVER_LISTEN_ALL = Option('Listen on all interfaces',
                           cf=('server', 'listen_all'),
                           cmd='--listen-all',
                           default=False,
                           long_arg=True,
                           cook=get_bool,
                           odesc='True|False')
SERVER_LOCATION = Option('Server Location', cf=('components', 'bcfg2'),
                         default='https://localhost:6789', cmd='-S',
                         odesc='https://server:port')
SERVER_STATIC = Option('Server runs on static port', cf=('components', 'bcfg2'),
                       default=False, cook=bool_cook)
SERVER_KEY = Option('Path to SSL key', cf=('communication', 'key'),
                    default=False, cmd='--ssl-key', odesc='<ssl key>',
                    long_arg=True)
SERVER_CERT = Option('Path to SSL certificate', default='/etc/bcfg2.key',
                     cf=('communication', 'certificate'), odesc='<ssl cert>')
SERVER_CA = Option('Path to SSL CA Cert', default=None,
                   cf=('communication', 'ca'), odesc='<ca cert>')
SERVER_PASSWORD = Option('Communication Password', cmd='-x', odesc='<password>',
                         cf=('communication', 'password'), default=False)
SERVER_PROTOCOL = Option('Server Protocol', cf=('communication', 'procotol'),
                         default='xmlrpc/ssl')
# Client options
CLIENT_KEY = Option('Path to SSL key', cf=('communication', 'key'),
                    default=None, cmd="--ssl-key", odesc='<ssl key>',
                    long_arg=True)
CLIENT_CERT = Option('Path to SSL certificate', default=None, cmd="--ssl-cert",
                     cf=('communication', 'certificate'), odesc='<ssl cert>',
                     long_arg=True)
CLIENT_CA = Option('Path to SSL CA Cert', default=None, cmd="--ca-cert",
                   cf=('communication', 'ca'), odesc='<ca cert>',
                   long_arg=True)
CLIENT_SCNS = Option('List of server commonNames', default=None, cmd="--ssl-cns",
                     cf=('communication', 'serverCommonNames'),
                     odesc='<commonName1:commonName2>', cook=list_split,
                     long_arg=True)
CLIENT_PROFILE = Option('Assert the given profile for the host',
                        default=False, cmd='-p', odesc="<profile>")
CLIENT_RETRIES = Option('The number of times to retry network communication',
                        default='3', cmd='-R', cf=('communication', 'retries'),
                        odesc="<retry count>")
CLIENT_DRYRUN = Option('Do not actually change the system',
                       default=False, cmd='-n', )
CLIENT_EXTRA_DISPLAY = Option('enable extra entry output',
                              default=False, cmd='-e', )
CLIENT_PARANOID = Option('Make automatic backups of config files',
                         default=False,
                         cmd='-P',
                         cook=get_bool,
                         cf=('client', 'paranoid'))
CLIENT_DRIVERS = Option('Specify tool driver set', cmd='-D',
                        cf=('client', 'drivers'),
                        odesc="<driver1,driver2>", cook=list_split,
                        default=Bcfg2.Client.Tools.default)
CLIENT_CACHE = Option('Store the configuration in a file',
                      default=False, cmd='-c', odesc="<cache path>")
CLIENT_REMOVE = Option('Force removal of additional configuration items',
                       default=False, cmd='-r', odesc="<entry type|all>")
CLIENT_BUNDLE = Option('Only configure the given bundle(s)', default=[],
                       cmd='-b', odesc='<bundle:bundle>', cook=colon_split)
CLIENT_BUNDLEQUICK = Option('only verify/configure the given bundle(s)', default=False,
                       cmd='-Q')
CLIENT_INDEP = Option('Only configure independent entries, ignore bundles', default=False,
                       cmd='-z')
CLIENT_KEVLAR = Option('Run in kevlar (bulletproof) mode', default=False,
                       cmd='-k', )
CLIENT_DLIST = Option('Run client in server decision list mode', default='none',
                      cf=('client', 'decision'),
                      cmd='-l', odesc='<whitelist|blacklist|none>')
CLIENT_FILE = Option('Configure from a file rather than querying the server',
                     default=False, cmd='-f', odesc='<specification path>')
CLIENT_QUICK = Option('Disable some checksum verification', default=False,
                      cmd='-q', )
CLIENT_USER = Option('The user to provide for authentication', default='root',
                     cmd='-u', cf=('communication', 'user'), odesc='<user>')
CLIENT_SERVICE_MODE = Option('Set client service mode', default='default',
                             cmd='-s', odesc='<default|disabled|build>')
CLIENT_TIMEOUT = Option('Set the client XML-RPC timeout', default=90,
                        cmd='-t', cf=('communication', 'timeout'),
                        odesc='<timeout>')
                     
# APT client tool options
CLIENT_APT_TOOLS_INSTALL_PATH = Option('Apt tools install path',
                                       cf=('APT', 'install_path'),
                                       default='/usr')
CLIENT_APT_TOOLS_VAR_PATH = Option('Apt tools var path',
                                   cf=('APT', 'var_path'), default='/var')
CLIENT_SYSTEM_ETC_PATH = Option('System etc path', cf=('APT', 'etc_path'),
                         default='/etc')

# Logging options
LOGGING_FILE_PATH = Option('Set path of file log', default=None,
                           cmd='-o', odesc='<path>', cf=('logging', 'path'))

class OptionParser(OptionSet):
    """
       OptionParser bootstraps option parsing,
       getting the value of the config file
    """
    def __init__(self, args):
        self.Bootstrap = OptionSet([('configfile', CFILE)])
        self.Bootstrap.parse(sys.argv[1:], do_getopt=False)
        if self.Bootstrap['configfile'] != Option.cfpath:
            Option.cfpath = self.Bootstrap['configfile']
            Option.__cfp = False
        OptionSet.__init__(self, args)
