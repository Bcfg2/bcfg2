import sys

import Bcfg2.Options
import Bcfg2.Proxy
import Bcfg2.Server.Admin

# Compatibility import
from Bcfg2.Bcfg2Py3k import xmlrpclib


class Xcmd(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("XML-RPC Command Interface")
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin xcmd command\n")
    __usage__ = ("bcfg2-admin xcmd <command>")

    def __call__(self, args):
        optinfo = {
            'server': Bcfg2.Options.SERVER_LOCATION,
            'user': Bcfg2.Options.CLIENT_USER,
            'password': Bcfg2.Options.SERVER_PASSWORD,
            'key': Bcfg2.Options.SERVER_KEY,
            'certificate': Bcfg2.Options.CLIENT_CERT,
            'ca': Bcfg2.Options.CLIENT_CA,
            'timeout': Bcfg2.Options.CLIENT_TIMEOUT,
            }
        setup = Bcfg2.Options.OptionParser(optinfo)
        setup.parse(args)
        Bcfg2.Proxy.RetryMethod.max_retries = 1
        proxy = Bcfg2.Proxy.ComponentProxy(setup['server'],
                                           setup['user'],
                                           setup['password'],
                                           key=setup['key'],
                                           cert=setup['certificate'],
                                           ca=setup['ca'],
                                           timeout=setup['timeout'])
        if len(setup['args']) == 0:
            print("Usage: xcmd <xmlrpc method> <optional arguments>")
            return
        cmd = setup['args'][0]
        args = ()
        if len(setup['args']) > 1:
            args = tuple(setup['args'][1:])
        try:
            data = getattr(proxy, cmd)(*args)
        except xmlrpclib.Fault:
            flt = sys.exc_info()[1]
            if flt.faultCode == 7:
                print("Unknown method %s" % cmd)
                return
            elif flt.faultCode == 20:
                return
            else:
                raise
        if data != None:
            print(data)
