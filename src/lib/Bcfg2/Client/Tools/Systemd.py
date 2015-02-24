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

    def get_svc_name(self, service):
        """Append .service to name if name doesn't specify a unit type."""
        svc = service.get('name')
        if svc.endswith(('.service', '.socket', '.device', '.mount',
                         '.automount', '.swap', '.target', '.path',
                         '.timer', '.snapshot', '.slice', '.scope')):
            return svc
        else:
            return '%s.service' % svc

    def get_svc_command(self, service, action):
        return "/bin/systemctl %s %s" % (action, self.get_svc_name(service))

    def verify_bootstatus(self, entry, bootstatus):
        """Verify bootstatus for entry."""
        cmd = self.get_svc_command(entry, 'is-enabled')
        rv = self.cmd.run(cmd)

        if rv.stdout.strip() == 'enabled':
            return bootstatus == 'on'
        else:
            return bootstatus == 'off'

    def VerifyService(self, entry, _):
        """Verify Service status for entry."""
        entry.set('target_status', entry.get('status'))  # for reporting

        bootstatus = self.get_bootstatus(entry)
        if bootstatus is None:
            # bootstatus is unspecified and status is ignore
            return True

        current_bootstatus = self.verify_bootstatus(entry, bootstatus)
        if entry.get('status') == 'ignore':
            return current_bootstatus

        cmd = self.get_svc_command(entry, 'show') + ' -p ActiveState'
        rv = self.cmd.run(cmd)
        if rv.stdout.strip() in ('ActiveState=active', 'ActiveState=activating',
                                 'ActiveState=reloading'):
            entry.set('current_status', 'on')
            return entry.get('status') == 'on' and current_bootstatus
        else:
            entry.set('current_status', 'off')
            return entry.get('status') == 'off' and current_bootstatus

    def InstallService(self, entry):
        """Install Service entry."""
        self.logger.info("Installing Service %s" % (entry.get('name')))
        bootstatus = self.get_bootstatus(entry)
        if bootstatus is None:
            # bootstatus is unspecified and status is ignore
            return True

        if bootstatus == 'on':
            rv = self.cmd.run(self.get_svc_command(entry, 'enable')).success
        else:
            rv = self.cmd.run(self.get_svc_command(entry, 'disable')).success

        if Bcfg2.Options.setup.servicemode == 'disabled':
            # 'disabled' means we don't attempt to modify running svcs
            return rv
        elif Bcfg2.Options.setup.servicemode == 'build':
            # 'build' means we attempt to stop all services started
            if entry.get('current_status') == 'on':
                rv &= self.cmd.run(self.get_svc_command(entry, 'stop')).success
        else:
            if entry.get('status') == 'on':
                rv &= self.cmd.run(self.get_svc_command(entry, 'start')).success
            else:
                rv &= self.cmd.run(self.get_svc_command(entry, 'stop')).success

        return rv
