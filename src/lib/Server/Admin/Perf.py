import Bcfg2.Options
import Bcfg2.Proxy
import Bcfg2.Server.Admin

import sys

class Perf(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Query server for performance data")
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin perf")
    __usage__ = ("bcfg2-admin perf")

    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)

    def __call__(self, args):
        output = [('Name', 'Min', 'Max', 'Mean')]
        optinfo = {
            'server': Bcfg2.Options.SERVER_LOCATION,
            'user': Bcfg2.Options.CLIENT_USER,
            'password': Bcfg2.Options.SERVER_PASSWORD,
            'key': Bcfg2.Options.SERVER_KEY,
            'certificate'     : Bcfg2.Options.CLIENT_CERT,
            'ca'              : Bcfg2.Options.CLIENT_CA
            }
        setup = Bcfg2.Options.OptionParser(optinfo)
        setup.parse(sys.argv[2:])
        proxy = Bcfg2.Proxy.ComponentProxy(setup['server'],
                                           setup['user'],
                                           setup['password'],
                                           key = setup['key'],
                                           cert = setup['certificate'],
                                           ca = setup['ca'])
        data = proxy.get_statistics()
        for key, value in data.iteritems():
            output.append((key, ) + tuple(["%.06f" % (item) for item in value]))
        self.print_table(output)

