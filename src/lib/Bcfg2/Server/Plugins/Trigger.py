""" Trigger is a plugin that calls external scripts (on the server) """

import os
import pipes
import Bcfg2.Server.Plugin
from Bcfg2.Utils import Executor


class TriggerFile(Bcfg2.Server.Plugin.FileBacked):
    """ Representation of a trigger script file """
    def HandleEvent(self, event=None):
        return


class Trigger(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.ClientRunHooks,
              Bcfg2.Server.Plugin.DirectoryBacked):
    """Trigger is a plugin that calls external scripts (on the server)."""
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.ClientRunHooks.__init__(self)
        Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data)
        self.cmd = Executor()

    def async_run(self, args):
        """ Run the trigger script asynchronously in a forked process
        """
        pid = os.fork()
        if pid:
            os.waitpid(pid, 0)
        else:
            dpid = os.fork()
            if not dpid:
                self.debug_log("Running %s" % " ".join(pipes.quote(a)
                                                       for a in args))
                result = self.cmd.run(args)
                if not result.success:
                    self.logger.error("Trigger: Error running %s: %s" %
                                      (args[0], result.error))
                elif result.stderr:
                    self.debug_log("Trigger: Error: %s" % result.stderr)
            os._exit(0)  # pylint: disable=W0212

    def end_client_run(self, metadata):
        args = [metadata.hostname, '-p', metadata.profile, '-g',
                ':'.join([g for g in metadata.groups])]
        for notifier in self.entries:
            npath = os.path.join(self.data, notifier)
            self.async_run([npath] + args)
