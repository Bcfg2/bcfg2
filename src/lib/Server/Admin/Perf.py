import sys

import Bcfg2.Options
import Bcfg2.Proxy
import Bcfg2.Server.Admin


class Perf(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Query server for performance data")
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin perf\n")
    __usage__ = ("bcfg2-admin perf")

    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)

    def __call__(self, args):
        output = [('Name', 'Min', 'Max', 'Mean', 'Count')]
        optinfo = {
            'ca': Bcfg2.Options.CLIENT_CA,
            'certificate': Bcfg2.Options.CLIENT_CERT,
            'key': Bcfg2.Options.SERVER_KEY,
            'password': Bcfg2.Options.SERVER_PASSWORD,
            'server': Bcfg2.Options.SERVER_LOCATION,
            'user': Bcfg2.Options.CLIENT_USER,
            'timeout': Bcfg2.Options.CLIENT_TIMEOUT,
            }
        setup = Bcfg2.Options.OptionParser(optinfo)
        setup.parse(sys.argv[2:])
        proxy = Bcfg2.Proxy.ComponentProxy(setup['server'],
                                           setup['user'],
                                           setup['password'],
                                           key=setup['key'],
                                           cert=setup['certificate'],
                                           ca=setup['ca'],
                                           timeout=setup['timeout'])
        data = proxy.get_statistics()
        for key, value in list(data.items()):
            data = tuple(["%.06f" % (item) for item in value[:-1]] + [value[-1]])
            output.append((key, ) + data)
        self.print_table(output)
