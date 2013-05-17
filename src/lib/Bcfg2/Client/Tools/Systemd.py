# This is the bcfg2 support for systemd

"""This is systemd support."""

import Bcfg2.Client.Tools
import Bcfg2.Client.XML


class Systemd(Bcfg2.Client.Tools.SvcTool):
    """Systemd support for Bcfg2."""
    name = 'Systemd'
    __execs__ = ['/bin/systemctl']
    __handles__ = [('Service', 'systemd')]
    __req__ = {'Service': ['name', 'status']}

    conflicts = ['Chkconfig']

    def get_svc_command(self, service, action):
        return "/bin/systemctl %s %s.service" % (action, service.get('name'))

    def VerifyService(self, entry, _):
        """Verify Service status for entry."""
        if entry.get('status') == 'ignore':
            return True

        cmd = "/bin/systemctl status %s.service " % (entry.get('name'))
        rv = self.cmd.run(cmd)

        if 'Loaded: error' in rv.stdout:
            entry.set('current_status', 'off')
            return False
        elif 'Active: active' in rv.stdout:
            entry.set('current_status', 'on')
            return entry.get('status') == 'on'
        else:
            entry.set('current_status', 'off')
            return entry.get('status') == 'off'

    def InstallService(self, entry):
        """Install Service entry."""
        if entry.get('status') == 'on':
            rv = self.cmd.run(self.get_svc_command(entry, 'enable')).success
            rv &= self.cmd.run(self.get_svc_command(entry, 'start')).success
        else:
            rv = self.cmd.run(self.get_svc_command(entry, 'stop')).success
            rv &= self.cmd.run(self.get_svc_command(entry, 'disable')).success

        return rv
