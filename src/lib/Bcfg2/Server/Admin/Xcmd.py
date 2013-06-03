""" XML-RPC Command Interface for bcfg2-admin"""

import sys
import Bcfg2.Options
import Bcfg2.Proxy
import Bcfg2.Server.Admin


class Xcmd(Bcfg2.Server.Admin.Mode):
    """ XML-RPC Command Interface """
    __usage__ = "<command>"

    def __call__(self, args):
        optinfo = {
            'server': Bcfg2.Options.SERVER_LOCATION,
            'user': Bcfg2.Options.CLIENT_USER,
            'password': Bcfg2.Options.SERVER_PASSWORD,
            'key': Bcfg2.Options.SERVER_KEY,
            'certificate': Bcfg2.Options.CLIENT_CERT,
            'ca': Bcfg2.Options.CLIENT_CA,
            'timeout': Bcfg2.Options.CLIENT_TIMEOUT}
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
            self.errExit("Usage: xcmd <xmlrpc method> <optional arguments>")
        cmd = setup['args'][0]
        args = ()
        if len(setup['args']) > 1:
            args = tuple(setup['args'][1:])
        try:
            data = getattr(proxy, cmd)(*args)
        except Bcfg2.Proxy.ProxyError:
            self.errExit("Proxy Error: %s" % sys.exc_info()[1])

        if data is not None:
            print(data)
