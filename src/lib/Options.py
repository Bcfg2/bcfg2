'''Option parsing library for utilities'''
__revision__ = '$Revision$'

import getopt, os, sys, ConfigParser
# (option, env, cfpath, default value, option desc, boolean, arg desc)
# ((option, arg desc, opt desc), env, cfpath, default, boolean)
bootstrap = {'configfile': (('-C', '<configfile>', 'Path to config file'), 
                             'BCFG2_CONF', False, '/etc/bcfg2.conf',  False)}

class OptionFailure(Exception):
    pass

class BasicOptionParser:
    '''Basic OptionParser takes input from command line arguments, environment variables, and defaults'''
    def __init__(self, name, optionspec, configfile=False, dogetopt=False):
        self.name = name
        self.dogetopt = dogetopt
        self.configfile = configfile
        self.optionspec = optionspec
        if dogetopt:
            self.shortopt = ''
            self.helpmsg = ''
            # longopts aren't yet supported
            self.longopt = []
            for option, info in optionspec.iteritems():
                (opt, argd, optd) = info[0]
                self.helpmsg += opt.ljust(3)
                if opt.count('-') == 1:
                    self.shortopt += opt[1]
                else:
                    print "unsupported option %s" % (opt)
                    continue
                if info[4]:
                    self.helpmsg += 24 * ' '
                else:
                    self.shortopt += ':'
                    self.helpmsg += "%-24s" % (argd)
                self.helpmsg += "%s\n" % (optd)

    def parse(self):
        '''Parse options'''
        ret = {}
        if self.dogetopt:
            try:
                opts, args = getopt.getopt(sys.argv[1:], self.shortopt, self.longopt)
            except getopt.GetoptError, err:
                print "%s Usage:" % (self.name)
                print err
                print self.helpmsg
                raise OptionFailure, err
            if '-h' in sys.argv:
                print "%s Usage:" % (self.name)
                print self.helpmsg
                raise SystemExit, 1
        if self.configfile:
            cf = ConfigParser.ConfigParser()
            cf.read(self.configfile)
        for key, (option, envvar, cfpath, default, boolean) in self.optionspec.iteritems():
            if self.dogetopt:
                optinfo = [opt[1] for opt in opts if opt[0] == option[0]]
                if optinfo:
                    if boolean:
                        ret[key] = True
                    else:
                        ret[key] = optinfo[0]
                    continue
            if option[0] in sys.argv:
                if boolean:
                    ret[key] = True
                else:
                    ret[key] = sys.argv[sys.argv.index(option[0]) + 1]
                continue
            elif envvar and os.environ.has_key(envvar):
                ret[key] = os.environ[envvar]
                continue
            elif self.configfile and cfpath:
                try:
                    value = apply(cf.get, cfpath)
                    ret[key] = value
                    continue
                except:
                    pass
            else:
                ret[key] = default
                continue
        return ret
    
class OptionParser(BasicOptionParser):
    '''OptionParser bootstraps option parsing, getting the value of the config file'''
    def __init__(self, name, ospec):
        # first find the cf file
        cfpath = BasicOptionParser('bootstrap', bootstrap).parse()['configfile']
        BasicOptionParser.__init__(self, name, ospec, cfpath, dogetopt=True)
