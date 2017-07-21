"""WinService support for Bcfg2."""

import subprocess

import Bcfg2.Client.Tools
import Bcfg2.Client.XML


class WinService(Bcfg2.Client.Tools.SvcTool):
    """WinService service support for Bcfg2."""
    name = 'WinService'
    __handles__ = [('Service', 'windows')]
    __req__ = {'Service': ['name', 'status']}

    def get_svc_command(self, service, action):
        return "powershell.exe %s-Service %s" % (action, service.get('name'))

    def VerifyService(self, entry, _):
        """Verify Service status for entry"""

        if entry.get('status') == 'ignore':
            return True

        try:
            output = self.cmd.run('powershell.exe (Get-Service %s).Status' %
                                  (entry.get('name')),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  close_fds=False).stdout.splitlines()[0]
        except IndexError:
            self.logger.error("Service %s not an Windows service" %
                              entry.get('name'))
            return False

        if output is None:
            # service does not exist
            entry.set('current_status', 'off')
            status = False
        elif output.lower() == 'running':
            # service is running
            entry.set('current_status', 'on')
            if entry.get('status') == 'off':
                status = False
            else:
                status = True
        else:
            # service is not running
            entry.set('current_status', 'off')
            if entry.get('status') == 'on':
                status = False
            else:
                status = True

        return status

    def InstallService(self, entry):
        """Install Service for entry."""
        if entry.get('status') == 'on':
            cmd = "start"
        elif entry.get('status') == 'off':
            cmd = "stop"
        return self.cmd.run(self.get_svc_command(entry, cmd),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            close_fds=False).success

    def restart_service(self, service):
        """Restart a service.

        :param service: The service entry to modify
        :type service: lxml.etree._Element
        :returns: Bcfg2.Utils.ExecutorResult - The return value from
                  :class:`Bcfg2.Utils.Executor.run`
        """
        self.logger.debug('Restarting service %s' % service.get('name'))
        restart_target = service.get('target', 'restart')
        return self.cmd.run(self.get_svc_command(service, restart_target),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            close_fds=False)

    def FindExtra(self):
        """Locate extra Windows services."""
        list = self.cmd.run("powershell.exe "
                "\"Get-WMIObject win32_service -Filter "
                "\\\"StartMode = 'auto'\\\""
                " | Format-Table Name -HideTableHeaders\"",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=False).stdout.splitlines()
        return [Bcfg2.Client.XML.Element('Service', name=name, type='windows')
                for name in list]
