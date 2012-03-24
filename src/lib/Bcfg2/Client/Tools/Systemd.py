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

    def get_svc_command(self, service, action):
        return "/bin/systemctl %s %s.service" % (action, service.get('name'))

    def VerifyService(self, entry, _):
        """Verify Service status for entry."""
        cmd = "/bin/systemctl status %s.service " % (entry.get('name'))
        raw = ''.join(self.cmd.run(cmd)[1])

        if raw.find('Loaded: error') >= 0:
            entry.set('current_status', 'off')
            status = False

        elif raw.find('Active: active') >= 0:
            entry.set('current_status', 'on')
            if entry.get('status') == 'off':
                status = False
            else:
                status = True

        else:
            entry.set('current_status', 'off')
            if entry.get('status') == 'on':
                status = False
            else:
                status = True

        return status

    def InstallService(self, entry):
        """Install Service entry."""
        # don't take any actions for mode = 'manual'
        if entry.get('mode', 'default') == 'manual':
            self.logger.info("Service %s mode set to manual. Skipping "
                             "installation." % (entry.get('name')))
            return True

        if entry.get('status') == 'on':
            pstatus = self.cmd.run(self.get_svc_command(entry, 'enable'))[0]
            pstatus = self.cmd.run(self.get_svc_command(entry, 'start'))[0]

        else:
            pstatus = self.cmd.run(self.get_svc_command(entry, 'stop'))[0]
            pstatus = self.cmd.run(self.get_svc_command(entry, 'disable'))[0]

        return not pstatus
