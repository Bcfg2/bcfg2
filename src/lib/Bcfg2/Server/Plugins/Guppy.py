"""Debugging plugin to trace memory leaks within the bcfg2-server process.

By default the remote debugger is started when this plugin is enabled.
The debugger can be shutoff in a running process using "bcfg2-admin
xcmd Guppy.Disable" and reenabled using "bcfg2-admin xcmd
Guppy.Enable".

To attach the console run:

python -c "from guppy import hpy;hpy().monitor()"

For example:

# python -c "from guppy import hpy;hpy().monitor()"
<Monitor>
*** Connection 1 opened ***
<Monitor> lc
CID PID   ARGV
  1 25063 ['/usr/sbin/bcfg2-server', '-D', '/var/run/bcfg2-server.pid']
<Monitor> sc 1
Remote connection 1. To return to Monitor, type <Ctrl-C> or .<RETURN>
<Annex> int
Remote interactive console. To return to Annex, type '-'.
>>> hp.heap()
...
"""
import Bcfg2.Server.Plugin
from guppy.heapy import Remote


class Guppy(Bcfg2.Server.Plugin.Plugin):
    """Guppy is a debugging plugin to help trace memory leaks."""
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __rmi__ = Bcfg2.Server.Plugin.Plugin.__rmi__ + ['Enable', 'Disable']
    __child_rmi__ = __rmi__[:]

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        self.Enable()

    @staticmethod
    def Enable():
        """Enable remote debugging."""
        Remote.on()

    @staticmethod
    def Disable():
        """Disable remote debugging."""
        Remote.off()
