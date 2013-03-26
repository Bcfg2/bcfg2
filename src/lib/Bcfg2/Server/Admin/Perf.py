""" Get performance data from server """

import sys
import Bcfg2.Options
import Bcfg2.Proxy
import Bcfg2.Server.Admin


class Perf(Bcfg2.Server.Admin.Mode):
    """ Get performance data from server """

    def __call__(self, args):
        output = [('Name', 'Min', 'Max', 'Mean', 'Count')]
        optinfo = {
            'ca': Bcfg2.Options.CLIENT_CA,
            'certificate': Bcfg2.Options.CLIENT_CERT,
            'key': Bcfg2.Options.SERVER_KEY,
            'password': Bcfg2.Options.SERVER_PASSWORD,
            'server': Bcfg2.Options.SERVER_LOCATION,
            'user': Bcfg2.Options.CLIENT_USER,
            'timeout': Bcfg2.Options.CLIENT_TIMEOUT}
        setup = Bcfg2.Options.OptionParser(optinfo)
        setup.parse(sys.argv[1:])
        proxy = Bcfg2.Proxy.ComponentProxy(setup['server'],
                                           setup['user'],
                                           setup['password'],
                                           key=setup['key'],
                                           cert=setup['certificate'],
                                           ca=setup['ca'],
                                           timeout=setup['timeout'])
        data = proxy.get_statistics()
        for key in sorted(data.keys()):
            output.append(
                (key, ) +
                tuple(["%.06f" % item
                       for item in data[key][:-1]] + [data[key][-1]]))
        self.print_table(output)
