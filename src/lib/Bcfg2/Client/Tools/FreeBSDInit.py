"""FreeBSD Init Support for Bcfg2."""
__revision__ = '$Rev$'

# TODO
# - hardcoded path to ports rc.d
# - doesn't know about /etc/rc.d/

import os
import Bcfg2.Client.Tools


class FreeBSDInit(Bcfg2.Client.Tools.SvcTool):
    """FreeBSD service support for Bcfg2."""
    name = 'FreeBSDInit'
    __handles__ = [('Service', 'freebsd')]
    __req__ = {'Service': ['name', 'status']}

    def __init__(self, logger, cfg, setup):
        Bcfg2.Client.Tools.Tool.__init__(self, logger, cfg, setup)
        if os.uname()[0] != 'FreeBSD':
            raise Bcfg2.Client.Tools.ToolInstantiationError

    def VerifyService(self, entry, _):
        return True

    def get_svc_command(self, service, action):
        return "/usr/local/etc/rc.d/%s %s" % (service.get('name'), action)
