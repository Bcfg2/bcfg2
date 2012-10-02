""" Invoke an external command to verify file contents """

import os
import sys
import shlex
import logging
import Bcfg2.Server.Plugin
from subprocess import Popen, PIPE
from Bcfg2.Server.Plugins.Cfg import CfgVerifier, CfgVerificationError

LOGGER = logging.getLogger(__name__)


class CfgExternalCommandVerifier(CfgVerifier):
    """ Invoke an external script to verify
    :ref:`server-plugins-generators-cfg` file contents """

    #: Handle :file:`:test` files
    __basenames__ = [':test']

    def __init__(self, name, specific, encoding):
        CfgVerifier.__init__(self, name, specific, encoding)
        self.cmd = []
    __init__.__doc__ = CfgVerifier.__init__.__doc__

    def verify_entry(self, entry, metadata, data):
        try:
            proc = Popen(self.cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            err = proc.communicate(input=data)[1]
            rv = proc.wait()
            if rv != 0:
                raise CfgVerificationError(err)
        except:
            err = sys.exc_info()[1]
            raise CfgVerificationError("Error running external command "
                                       "verifier: %s" % err)
    verify_entry.__doc__ = CfgVerifier.verify_entry.__doc__

    def handle_event(self, event):
        CfgVerifier.handle_event(self, event)
        if not self.data:
            return
        self.cmd = []
        if not os.access(self.name, os.X_OK):
            bangpath = self.data.splitlines()[0].strip()
            if bangpath.startswith("#!"):
                self.cmd.extend(shlex.split(bangpath[2:].strip()))
            else:
                msg = "%s: Cannot execute %s" % (self.__class__.__name__,
                                                 self.name)
                LOGGER.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        self.cmd.append(self.name)
    handle_event.__doc__ = CfgVerifier.handle_event.__doc__
