import Bcfg2.Proxy
import Bcfg2.Server.Admin
from Bcfg2 import Options


class Perf(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Query server for performance data")
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin perf\n")
    __usage__ = ("bcfg2-admin perf")

    def __init__(self):
        Options.add_options(
            Options.CLIENT_CA,
            Options.CLIENT_CERT,
            Options.SERVER_KEY,
            Options.SERVER_PASSWORD,
            Options.SERVER_LOCATION,
            Options.CLIENT_USER,
            Options.CLIENT_TIMEOUT,
        )
        Bcfg2.Server.Admin.Mode.__init__(self)
        Options.set_help(self.__shorthelp__)

    def __call__(self, args):
        output = [('Name', 'Min', 'Max', 'Mean', 'Count')]
        proxy = Bcfg2.Proxy.ComponentProxy(args.server_location,
                                           args.user,
                                           args.password,
                                           key=args.ssl_key,
                                           cert=args.ssl_cert,
                                           ca=args.ca_cert,
                                           timeout=args.timeout)
        data = proxy.get_statistics()
        for key, value in list(data.items()):
            data = tuple(["%.06f" % (item) for item in value[:-1]] + [value[-1]])
            output.append((key, ) + data)
        self.print_table(output)
