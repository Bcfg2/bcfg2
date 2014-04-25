""" Invoke an external command to verify file contents """

import os
import sys
import shlex
from Bcfg2.Utils import Executor
from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgVerifier, CfgVerificationError


class CfgExternalCommandVerifier(CfgVerifier):
    """ Invoke an external script to verify
    :ref:`server-plugins-generators-cfg` file contents """

    #: Handle :file:`:test` files
    __basenames__ = [':test']

    def __init__(self, name, specific):
        CfgVerifier.__init__(self, name, specific)
        self.cmd = []
        self.exc = Executor(timeout=30)
    __init__.__doc__ = CfgVerifier.__init__.__doc__

    def verify_entry(self, entry, metadata, data):
        try:
            result = self.exc.run(self.cmd, inputdata=data)
            if not result.success:
                raise CfgVerificationError(result.error)
        except OSError:
            raise CfgVerificationError(sys.exc_info()[1])
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
                raise PluginExecutionError("Cannot execute %s" % self.name)
        self.cmd.append(self.name)
    handle_event.__doc__ = CfgVerifier.handle_event.__doc__
