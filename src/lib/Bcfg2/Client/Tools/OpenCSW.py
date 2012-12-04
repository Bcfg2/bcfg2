# This is the bcfg2 support for opencsw packages (pkgutil)
"""This provides Bcfg2 support for OpenCSW packages."""

import tempfile
import Bcfg2.Client.Tools.SYSV


class OpenCSW(Bcfg2.Client.Tools.SYSV.SYSV):
    """Support for OpenCSW packages."""
    pkgtype = 'opencsw'
    pkgtool = ("/opt/csw/bin/pkgutil -y -i %s", ("%s", ["bname"]))
    name = 'OpenCSW'
    __execs__ = ['/opt/csw/bin/pkgutil', "/usr/bin/pkginfo"]
    __handles__ = [('Package', 'opencsw')]
    __req__ = {'Package': ['name', 'version', 'bname']}

    def __init__(self, logger, setup, config):
        # dont use the sysv constructor
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)
        noaskfile = tempfile.NamedTemporaryFile()
        self.noaskname = noaskfile.name
        try:
            noaskfile.write(Bcfg2.Client.Tools.SYSV.noask)
        except:
            pass

    # VerifyPackage comes from Bcfg2.Client.Tools.SYSV
    # Install comes from Bcfg2.Client.Tools.PkgTool
    # Extra comes from Bcfg2.Client.Tools.Tool
    # Remove comes from Bcfg2.Client.Tools.SYSV
    def FindExtra(self):
        """Pass through to null FindExtra call."""
        return []
