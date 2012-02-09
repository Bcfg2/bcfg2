import sys
from metargs import Option

import Bcfg2.Options
import Bcfg2.Proxy
import Bcfg2.Server.Admin

# Compatibility import
from Bcfg2.Bcfg2Py3k import xmlrpclib


class Xcmd(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("XML-RPC Command Interface")
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin xcmd command\n")
    __usage__ = ("bcfg2-admin xcmd <command>")

    def __init__(self):
        Bcfg2.Server.Admin.Mode.__init__(self)
        Bcfg2.Options.add_options(
            Bcfg2.Options.SERVER_LOCATION,
            Bcfg2.Options.CLIENT_USER,
            Bcfg2.Options.SERVER_PASSWORD,
            Bcfg2.Options.SERVER_KEY,
            Bcfg2.Options.CLIENT_CERT,
            Bcfg2.Options.CLIENT_CA,
            Bcfg2.Options.CLIENT_TIMEOUT,
            Option('command'),
            Option('args', nargs='*'),
        )

    def __call__(self, args):
        Bcfg2.Proxy.RetryMethod.max_retries = 1
        
        proxy = Bcfg2.Proxy.ComponentProxy(args.server_location,
                                           args.user,
                                           args.password,
                                           key=args.ssl_key,
                                           cert=args.ssl_cert,
                                           ca=args.ca_cert,
                                           timeout=args.timeout)
        try:
            data = getattr(proxy, args.command)(*args.args)
        except xmlrpclib.Fault:
            flt = sys.exc_info()[1]
            if flt.faultCode == 7:
                print("Unknown method %s" % args.command)
                return
            elif flt.faultCode == 20:
                return
            else:
                raise
        except Bcfg2.Proxy.ProxyError, err:
            print("Proxy Error: %s" % err)
            return

        if data != None:
            print(data)
