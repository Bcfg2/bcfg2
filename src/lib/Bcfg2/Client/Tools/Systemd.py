# This is the bcfg2 support for systemd

"""This is systemd support."""

import glob
import os
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

    def VerifyService(self, entry, _):
        """Verify Service status for entry."""
        entry.set('target_status', entry.get('status'))  # for reporting

        bootstatus = self.get_bootstatus(entry)
        if bootstatus is None:
            # bootstatus is unspecified and status is ignore
            return True

        if self.cmd.run(self.get_svc_command(entry, 'is-enabled')):
            current_bootstatus = 'on'
        else:
            current_bootstatus = 'off'

        if entry.get('status') == 'ignore':
            return current_bootstatus == bootstatus

        cmd = self.get_svc_command(entry, 'show') + ' -p ActiveState'
        rv = self.cmd.run(cmd)
        if rv.stdout.strip() in ('ActiveState=active',
                                 'ActiveState=activating',
                                 'ActiveState=reloading'):
            current_status = 'on'
        else:
            current_status = 'off'
        entry.set('current_status', current_status)
        return (entry.get('status') == current_status and
                bootstatus == current_bootstatus)

    def InstallService(self, entry):
        """Install Service entry."""
        self.logger.info("Installing Service %s" % (entry.get('name')))
        bootstatus = self.get_bootstatus(entry)
        if bootstatus is None:
            # bootstatus is unspecified and status is ignore
            return True

        # Enable or disable the service
        if bootstatus == 'on':
            cmd = self.get_svc_command(entry, 'enable')
        else:
            cmd = self.get_svc_command(entry, 'disable')
        if not self.cmd.run(cmd).success:
            # Return failure immediately and do not start/stop the service.
            return False

        # Start or stop the service, depending on the current service_mode
        cmd = None
        if Bcfg2.Options.setup.service_mode == 'disabled':
            # 'disabled' means we don't attempt to modify running svcs
            pass
        elif Bcfg2.Options.setup.service_mode == 'build':
            # 'build' means we attempt to stop all services started
            if entry.get('current_status') == 'on':
                cmd = self.get_svc_command(entry, 'stop')
        else:
            if entry.get('status') == 'on':
                cmd = self.get_svc_command(entry, 'start')
            elif entry.get('status') == 'off':
                cmd = self.get_svc_command(entry, 'stop')

        if cmd:
            return self.cmd.run(cmd).success
        else:
            return True

    def FindExtra(self):
        """Find Extra Systemd Service entries."""
        specified = [self.get_svc_name(entry)
                     for entry in self.getSupportedEntries()]
        extra = set()
        for fname in glob.glob("/etc/systemd/system/*.wants/*"):
            name = os.path.basename(fname)
            if name not in specified:
                extra.add(name)
        return [Bcfg2.Client.XML.Element('Service', name=name, type='systemd')
                for name in list(extra)]
