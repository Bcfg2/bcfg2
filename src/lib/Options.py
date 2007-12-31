'''Option parsing library for utilities'''
__revision__ = '$Revision$'

import getopt, os, socket, sys, ConfigParser

def bool_cook(x):
    if x:
        return True
    else:
        return False

class OptionFailure(Exception):
    pass

class Option(object):
    cfpath = '/etc/bcfg2.conf'
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
                 env=False, cf=False, cook=False):
        self.desc = desc
        self.default = default
        self.cmd = cmd
        if cmd and (cmd[0] != '-' or len(cmd) != 2):
            raise OptionFailure("Poorly formed command %s" % cmd)
        self.odesc = odesc
        self.env = env
        self.cf = cf
        self.cook = cook

    def buildHelpMessage(self):
        msg = ''
        if self.cmd:
            msg = self.cmd.ljust(3)
            if self.odesc:
                msg += ':%-24s' % (self.odesc)
            msg += "%s\n" % self.desc
        return msg

    def buildGetopt(self):
        gstr = ''
        if self.cmd:
            gstr = self.cmd[1]
            if self.odesc:
                gstr += ':'
        return gstr

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
                opts, args = getopt.getopt(argv, self.buildGetopt(), [])
            except getopt.GetoptError, err:
                self.helpExit(err)
            if '-h' in argv:
                self.helpExit('', 0)
        for key in self.keys():
            option = self[key]
            if do_getopt:
                option.parse(opts, [])
            else:
                option.parse([], argv)
            if hasattr(option, '_value'):
                val = option.value
                self[key] = val

list_split = lambda x:x.replace(' ','').split(',')

CFILE = Option('Specify configuration file', '/etc/bcfg2.conf', cmd='-C',
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
                         default=(socket.gethostname(), 0), cmd='-S',
                         odesc='https://server:port')
SERVER_STATIC = Option('Server runs on static port', cf=('components', 'bcfg2'),
                       default='', cook=bool_cook)
SERVER_KEY = Option('Path to SSL key', cf=('communication', 'key'),
                       default=False)
SERVER_PASSWORD = Option('Communication Password', cmd='-x',
                         cf=('communication', 'password'), default=False)
INSTALL_PREFIX = Option('Installation location', cf=('server', 'prefix'),
                       default='/usr')
SERVER_PROTOCOL = Option('Server Protocol', cf=('communication', 'procotol'),
                         default='xmlrpc/ssl')
SENDMAIL_PATH = Option('Path to sendmail', cf=('reports', 'sendmailpath'),
                         default='/usr/lib/sendmail')

class OptionParser(OptionSet):
    '''OptionParser bootstraps option parsing, getting the value of the config file'''
    def __init__(self, args):
        self.Bootstrap = OptionSet([('configfile', CFILE)])
        self.Bootstrap.parse(sys.argv[1:], do_getopt=False)
        if self.Bootstrap['configfile'] != Option.cfpath:
            Option.cfpath = self.Bootstrap['configfile']
            Option.__cfp = False
        OptionSet.__init__(self, args)
