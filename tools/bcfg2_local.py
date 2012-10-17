#!/usr/bin/env python
""" This tool performs a full Bcfg2 run entirely against a local
repository, i.e., without a server.  It starts up a local instance of
the server core, then uses that to get probes, run them, and so on."""

import sys
import socket
import Bcfg2.Options
from Bcfg2.Client.Client import Client
from Bcfg2.Server.Core import BaseCore


class LocalCore(BaseCore):
    """ Local server core similar to the one started by bcfg2-info """

    def __init__(self, setup):
        saved = (setup['syslog'], setup['logging'])
        setup['syslog'] = False
        setup['logging'] = None
        Bcfg2.Server.Core.BaseCore.__init__(self, setup=setup)
        setup['syslog'], setup['logging'] = saved
        self.fam.handle_events_in_interval(4)

    def _daemonize(self):
        pass

    def _run(self):
        pass

    def _block(self):
        pass


class LocalProxy(object):
    """ A local proxy (as opposed to XML-RPC) that proxies from the
    Client object to the LocalCore object, adding a client address
    pair to the argument list of each proxied call """

    def __init__(self, core):
        self.core = core
        self.hostname = socket.gethostname()
        self.ipaddr = socket.gethostbyname(self.hostname)

    def __getattr__(self, attr):
        if hasattr(self.core, attr):
            func = getattr(self.core, attr)
            if func.exposed:
                def inner(*args, **kwargs):
                    args = ((self.ipaddr, self.hostname), ) + args
                    return func(*args, **kwargs)
                return inner
        raise AttributeError(attr)


class LocalClient(Client):
    """ A version of the Client class that uses LocalProxy instead of
    an XML-RPC proxy to make its calls """

    def __init__(self, setup, proxy):
        Client.__init__(self, setup)
        self._proxy = proxy


def main():
    optinfo = Bcfg2.Options.CLIENT_COMMON_OPTIONS
    optinfo.update(Bcfg2.Options.SERVER_COMMON_OPTIONS)
    setup = Bcfg2.Options.OptionParser(optinfo)
    setup.parse(sys.argv[1:])

    core = LocalCore(setup)
    try:
        LocalClient(setup, LocalProxy(core)).run()
    finally:
        core.shutdown()

if __name__ == '__main__':
    sys.exit(main())
