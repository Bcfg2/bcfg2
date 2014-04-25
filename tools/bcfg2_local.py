#!/usr/bin/env python
""" This tool performs a full Bcfg2 run entirely against a local
repository, i.e., without a server.  It starts up a local instance of
the server core, then uses that to get probes, run them, and so on."""

import sys
import socket
import Bcfg2.Options
from Bcfg2.Client import Client
from Bcfg2.Server.Core import Core


class LocalCore(Core):
    """ Local server core similar to the one started by bcfg2-info """

    def __init__(self):
        #saved = (setup['syslog'], setup['logging'])
        #setup['syslog'] = False
        #setup['logging'] = None
        Bcfg2.Server.Core.BaseCore.__init__(self)
        #setup['syslog'], setup['logging'] = saved
        self.load_plugins()
        self.block_for_fam_events(handle_events=True)

    def _daemonize(self):
        return True

    def _run(self):
        return True

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
                    # the port portion of the addresspair tuple isn't
                    # actually used, so it's safe to hardcode 6789
                    # here.
                    args = ((self.ipaddr, 6789), ) + args
                    return func(*args, **kwargs)
                return inner
        raise AttributeError(attr)


class LocalClient(Client):
    """ A version of the Client class that uses LocalProxy instead of
    an XML-RPC proxy to make its calls """

    def __init__(self, proxy):
        Client.__init__(self)
        self._proxy = proxy


def main():
    parser = Bcfg2.Options.Parser(
        description="Run a Bcfg2 client against a local repository without a "
        "server",
        conflict_handler="resolve",
        components=[LocalCore, LocalProxy, LocalClient])
    parser.parse()

    core = LocalCore()
    try:
        LocalClient(LocalProxy(core)).run()
    finally:
        core.shutdown()

if __name__ == '__main__':
    sys.exit(main())
