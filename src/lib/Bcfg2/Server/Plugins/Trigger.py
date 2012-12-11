""" Trigger is a plugin that calls external scripts (on the server) """

import os
import pipes
import Bcfg2.Server.Plugin
from subprocess import Popen, PIPE


class TriggerFile(Bcfg2.Server.Plugin.FileBacked):
    """ Representation of a trigger script file """

    def HandleEvent(self, event=None):
        return

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.name)


class Trigger(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.ClientRunHooks,
              Bcfg2.Server.Plugin.DirectoryBacked):
    """Trigger is a plugin that calls external scripts (on the server)."""
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.ClientRunHooks.__init__(self)
        Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data,
                                                     self.core.fam)

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
                proc = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
                err = proc.communicate()[1]
                rv = proc.wait()
                if rv != 0:
                    self.logger.error("Trigger: Error running %s (%s): %s" %
                                      (args[0], rv, err))
                elif err:
                    self.debug_log("Trigger: Error: %s" % err)
            os._exit(0)  # pylint: disable=W0212

    def end_client_run(self, metadata):
        args = [metadata.hostname, '-p', metadata.profile, '-g',
                ':'.join([g for g in metadata.groups])]
        for notifier in self.entries.keys():
            npath = os.path.join(self.data, notifier)
            self.async_run([npath] + args)
