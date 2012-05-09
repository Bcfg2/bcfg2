import os
import shlex
import logging
import Bcfg2.Server.Plugin
from subprocess import Popen, PIPE
from Bcfg2.Server.Plugins.Cfg import CfgVerifier, CfgVerificationError

logger = logging.getLogger(__name__)

class CfgExternalCommandVerifier(CfgVerifier):
    __basenames__ = [':test']

    def verify_entry(self, entry, metadata, data):
        proc = Popen(self.cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        err = proc.communicate(input=data)[1]
        rv = proc.wait()
        if rv != 0:
            raise CfgVerificationError(err)

    def handle_event(self, event):
        if event.code2str() == 'deleted':
            return
        self.cmd = []
        if not os.access(self.name, os.X_OK):
            bangpath = open(self.name).readline().strip()
            if bangpath.startswith("#!"):
                self.cmd.extend(shlex.split(bangpath[2:].strip()))
            else:
                msg = "Cannot execute %s" % self.name
                logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        self.cmd.append(self.name)
    
