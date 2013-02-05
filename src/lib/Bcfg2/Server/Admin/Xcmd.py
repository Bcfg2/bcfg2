""" XML-RPC Command Interface for bcfg2-admin"""

import sys
import Bcfg2.Options
import Bcfg2.Client.Proxy
import Bcfg2.Server.Admin
from Bcfg2.Compat import xmlrpclib


class Xcmd(Bcfg2.Server.Admin.Mode):
    """ XML-RPC Command Interface """
    __usage__ = "<command>"

    def __call__(self, args):
        setup = Bcfg2.Options.get_option_parser()
        setup.add_options(dict(ca=Bcfg2.Options.CLIENT_CA,
                               certificate=Bcfg2.Options.CLIENT_CERT,
                               key=Bcfg2.Options.SERVER_KEY,
                               password=Bcfg2.Options.SERVER_PASSWORD,
                               server=Bcfg2.Options.SERVER_LOCATION,
                               user=Bcfg2.Options.CLIENT_USER,
                               timeout=Bcfg2.Options.CLIENT_TIMEOUT))
        opts = sys.argv[1:]
        opts.remove(self.__class__.__name__.lower())
        setup.reparse(argv=opts)
        Bcfg2.Client.Proxy.RetryMethod.max_retries = 1
        proxy = Bcfg2.Client.Proxy.ComponentProxy(setup['server'],
                                                  setup['user'],
                                                  setup['password'],
                                                  key=setup['key'],
                                                  cert=setup['certificate'],
                                                  ca=setup['ca'],
                                                  timeout=setup['timeout'])
        if len(setup['args']) == 0:
            print("Usage: xcmd <xmlrpc method> <optional arguments>")
            return
        cmd = args[0]
        try:
            data = getattr(proxy, cmd)(*setup['args'])
        except xmlrpclib.Fault:
            flt = sys.exc_info()[1]
            if flt.faultCode == 7:
                print("Unknown method %s" % cmd)
                return
            elif flt.faultCode == 20:
                return
            else:
                raise
        except Bcfg2.Client.Proxy.ProxyError:
            err = sys.exc_info()[1]
            print("Proxy Error: %s" % err)
            return

        if data != None:
            print(data)
