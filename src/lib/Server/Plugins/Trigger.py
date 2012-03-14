import os
import Bcfg2.Server.Plugin


def async_run(prog, args):
    pid = os.fork()
    if pid:
        os.waitpid(pid, 0)
    else:
        dpid = os.fork()
        if not dpid:
            os.system(" ".join([prog] + args))
        os._exit(0)


class Trigger(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Statistics):
    """Trigger is a plugin that calls external scripts (on the server)."""
    name = 'Trigger'
    __version__ = '$Id'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Statistics.__init__(self)
        try:
            os.stat(self.data)
        except:
            self.logger.error("Trigger: spool directory %s does not exist; "
                              "unloading" % self.data)
            raise Bcfg2.Server.Plugin.PluginInitError

    def process_statistics(self, metadata, _):
        args = [metadata.hostname, '-p', metadata.profile, '-g',
                ':'.join([g for g in metadata.groups])]
        for notifier in os.listdir(self.data):
            if ((notifier[-1] == '~') or
                (notifier[:2] == '.#') or
                (notifier[-4:] == '.swp') or
                (notifier in ['SCCS', '.svn', '4913'])):
                continue
            npath = self.data + '/' + notifier
            self.logger.debug("Running %s %s" % (npath, " ".join(args)))
            async_run(npath, args)
