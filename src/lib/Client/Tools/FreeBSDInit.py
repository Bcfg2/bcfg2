'''FreeBSD Init Support for Bcfg2'''
__revision__ = '$Rev$'

# TODO
# - hardcoded path to ports rc.d
# - doesn't know about /etc/rc.d/

import Bcfg2.Client.Tools

class FreeBSDInit(Bcfg2.Client.Tools.SvcTool):
    '''FreeBSD Service Support for Bcfg2'''
    name = 'FreeBSDInit'
    __handles__ = [('Service', 'freebsd')]
    __req__ = {'Service': ['name', 'status']}

    def VerifyService(self, entry, _):
        return True

    def get_svc_command(self, service, action):
        return "/usr/local/etc/rc.d/%s %s" % (service.get('name'), action)
