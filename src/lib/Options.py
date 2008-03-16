'''Option parsing library for utilities'''
__revision__ = '$Revision$'

import getopt, os, socket, sys, ConfigParser, Bcfg2.Client.Tools

def bool_cook(x):
    if x:
        return True
    else:
        return False

class OptionFailure(Exception):
    pass

DEFAULT_CONFIG_LOCATION = '/etc/bcfg2.conf'

class Option(object):
    cfpath = DEFAULT_CONFIG_LOCATION
    __cfp = False
    def getCFP(self):
        if not self.__cfp:
            self.__cfp = ConfigParser.ConfigParser()
            self.__cfp.readfp(open(self.cfpath))
        return self.__cfp
    cfp = property(getCFP)

    def getValue(self):
        if self.cook:
            return self.cook(self._value)
        else:
            return self._value
    value = property(getValue)
    
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
        if not odesc and not cook:
            self.cook = bool_cook
        else:
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
                    msg = "%-27s" % ("%s=%s" % (self.cmd, self.odesc))
                else:
                    msg += '%-24s' % (self.odesc)
            else:
                msg += '%-24s' % ('')
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
            # processing getopted data
            optinfo = [opt[1] for opt in opts if opt[0] == self.cmd]
            if optinfo:
                if optinfo[0]:
                    self._value = optinfo[0]
                else:
                    self._value = True
                return
        if self.cmd and self.cmd in rawopts:
            self._value = rawopts[rawopts.index(self.cmd) + 1]
            return
        # no command line option found
        if self.env and self.env in os.environ:
            self._value = os.environ[self.env]
            return
        if self.cf:
            try:
                self._value = self.cfp.get(*self.cf)
                return
            except:
                pass
        self._value = self.default

class OptionSet(dict):
    def buildGetopt(self):
        return ''.join([opt.buildGetopt() for opt in self.values()])

    def buildLongGetopt(self):
        return [opt.buildLongGetopt() for opt in self.values() if opt.long]

    def buildHelpMessage(self):
        return ''.join([opt.buildHelpMessage() for opt in self.values()])

    def helpExit(self, msg='', code=1):
        if msg:
            print msg
        print "Usage:"
        print self.buildHelpMessage()
        raise SystemExit(code)

    def parse(self, argv, do_getopt=True):
        '''Parse options'''
        ret = {}
        if do_getopt:
            try:
                opts, args = getopt.getopt(argv, self.buildGetopt(),
                                           self.buildLongGetopt())
            except getopt.GetoptError, err:
                self.helpExit(err)
            if '-h' in argv:
                self.helpExit('', 0)
            self['args'] = args
        for key in self.keys():
            if key == 'args':
                continue
            option = self[key]
            if do_getopt:
                option.parse(opts, [])
            else:
                option.parse([], argv)
            if hasattr(option, '_value'):
                val = option.value
                self[key] = val

list_split = lambda x:x.replace(' ','').split(',')
def colon_split(c_string):
    if c_string:
        return c_string.split(':')
    return []

CFILE = Option('Specify configuration file', DEFAULT_CONFIG_LOCATION, cmd='-C',
               odesc='<conffile>')
HELP = Option('Print this usage message', False, cmd='-h')
DEBUG = Option("Enable debugging output", False, cmd='-d')
VERBOSE = Option("Enable verbose output", False, cmd='-v')
DAEMON = Option("Daemonize process, storing pid", False,
                cmd='-D', odesc="<pidfile>")

SERVER_REPOSITORY = Option('Server repository path', '/var/lib/bcfg2',
                           cf=('server', 'repository'), cmd='-Q',
                           odesc='<repository path>' )
SERVER_SVN = Option('Server svn support', False, cf=('server', 'svn'))
SERVER_GENERATORS = Option('Server generator list', cf=('server', 'generators'),
                           default='SSHbase,Cfg,Pkgmgr,Rules', cook=list_split)
SERVER_STRUCTURES = Option('Server structure list', cf=('server', 'structures'),
                           default='Bundler,Base', cook=list_split)

SERVER_LOCATION = Option('Server Location', cf=('components', 'bcfg2'),
                         default='https://localhost:6789', cmd='-S',
                         odesc='https://server:port')
SERVER_STATIC = Option('Server runs on static port', cf=('components', 'bcfg2'),
                       default='', cook=bool_cook)
SERVER_KEY = Option('Path to SSL key', cf=('communication', 'key'),
                       default=False, cmd='-K', odesc='<ssl key file>')
SERVER_PASSWORD = Option('Communication Password', cmd='-x', odesc='<password>',
                         cf=('communication', 'password'), default=False)
INSTALL_PREFIX = Option('Installation location', cf=('server', 'prefix'),
                       default='/usr', odesc='</path>')
SERVER_PROTOCOL = Option('Server Protocol', cf=('communication', 'procotol'),
                         default='xmlrpc/ssl')
SENDMAIL_PATH = Option('Path to sendmail', cf=('reports', 'sendmailpath'),
                         default='/usr/lib/sendmail')

CLIENT_PROFILE = Option('assert the given profile for the host',
                        default=False, cmd='-p', odesc="<profile>")
CLIENT_RETRIES = Option('the number of times to retry network communication',
                        default='3', cmd='-R', cf=('communication', 'retries'),
                        odesc="<retry count>")
CLIENT_DRYRUN = Option('do not actually change the system',
                       default=False, cmd='-n', )
CLIENT_EXTRA_DISPLAY = Option('enable extra entry output',
                              default=False, cmd='-e', )
CLIENT_PARANOID = Option('make automatic backups of config files',
                         default=False, cmd='-P', )
CLIENT_AGENT = Option('run in agent (continuous) mode, wait for reconfigure command from server', default=False, cmd='-A', )
CLIENT_DRIVERS = Option('Specify tool driver set', cmd='-D',
                        cf=('client', 'drivers'),
                        odesc="<driver1,driver2>", cook=list_split,
                        default=','.join(Bcfg2.Client.Tools.default))
CLIENT_CACHE = Option('store the configuration in a file',
                      default=False, cmd='-c', odesc="<cache path>")
CLIENT_REMOVE = Option('force removal of additional configuration items',
                       default=False, cmd='-r', odesc="<entry type|all>")
CLIENT_BUNDLE = Option('only configure the given bundle', default='',
                       cmd='-b', odesc='<bundle>', cook=colon_split)
CLIENT_KEVLAR = Option('run in kevlar (bulletproof) mode', default=False,
                       cmd='-k', )
CLIENT_BUILD = Option('run in build mode', default=False, cmd='-B', )
CLIENT_FILE = Option('configure from a file rather than querying the server',
                     default=False, cmd='-f', odesc='<specification path>')
SERVER_FINGERPRINT = Option('Server Fingerprint', default=False, cmd='-F',
                            cf=('communication', 'fingerprint'),
                            odesc='<fingerprint>')
CLIENT_QUICK = Option('disable some checksum verification', default=False,
                      cmd='-q', )
CLIENT_BACKGROUND = Option('Daemonize the agent', default=False, cmd='-i', )
CLIENT_PORT = Option('the port on which to bind for agent mode', default='6789',
                     cmd='-g', cf=('communication', 'agent-port'),
                     odesc='<agent port>')
CLIENT_USER = Option('the user to provide for authentication', default='root',
                     cmd='-u', cf=('communication', 'user'), odesc='<user>')
INTERACTIVE = Option('prompt the user for each change', default=False,
                     cmd='-I', )

AGENT_PORT = Option('Agent port', default=6789, cmd='-p', odesc='<port>',
                    cf=('communication', 'agent-port'))
AGENT_HOST = Option('Remote host', default=False, cmd='-H', odesc='<hostname>')

class OptionParser(OptionSet):
    '''OptionParser bootstraps option parsing, getting the value of the config file'''
    def __init__(self, args):
        self.Bootstrap = OptionSet([('configfile', CFILE)])
        self.Bootstrap.parse(sys.argv[1:], do_getopt=False)
        if self.Bootstrap['configfile'] != Option.cfpath:
            Option.cfpath = self.Bootstrap['configfile']
            Option.__cfp = False
        OptionSet.__init__(self, args)
