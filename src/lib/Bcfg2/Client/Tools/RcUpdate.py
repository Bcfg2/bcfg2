"""This is rc-update support."""

import os
import Bcfg2.Client.Tools
import Bcfg2.Client.XML


class RcUpdate(Bcfg2.Client.Tools.SvcTool):
    """RcUpdate support for Bcfg2."""
    name = 'RcUpdate'
    __execs__ = ['/sbin/rc-update', '/bin/rc-status']
    __handles__ = [('Service', 'rc-update')]
    __req__ = {'Service': ['name', 'status']}

    def VerifyService(self, entry, _):
        """
        Verify Service status for entry.
        Assumes we run in the "default" runlevel.

        """
        if entry.get('status') == 'ignore':
            return True

        # check if service is enabled
        result = self.cmd.run(["/sbin/rc-update", "show", "default"])
        is_enabled = entry.get("name") in result.stdout

        # check if init script exists
        try:
            os.stat('/etc/init.d/%s' % entry.get('name'))
        except OSError:
            self.logger.debug('Init script for service %s does not exist' %
                              entry.get('name'))
            return False

        # check if service is enabled
        result = self.cmd.run(self.get_svc_command(entry, "status"))
        is_running = "started" in result.stdout

        if entry.get('status') == 'on' and not (is_enabled and is_running):
            entry.set('current_status', 'off')
            return False

        elif entry.get('status') == 'off' and (is_enabled or is_running):
            entry.set('current_status', 'on')
            return False

        return True

    def InstallService(self, entry):
        """
        Install Service entry

        """
        self.logger.info('Installing Service %s' % entry.get('name'))
        if entry.get('status') == 'on':
            if entry.get('current_status') == 'off':
                self.start_service(entry)
            # make sure it's enabled
            cmd = '/sbin/rc-update add %s default'
            return self.cmd.run(cmd % entry.get('name')).success
        elif entry.get('status') == 'off':
            if entry.get('current_status') == 'on':
                self.stop_service(entry)
            # make sure it's disabled
            cmd = '/sbin/rc-update del %s default'
            return self.cmd.run(cmd % entry.get('name')).success

        return False

    def FindExtra(self):
        """Locate extra rc-update services."""
        allsrv = [line.split()[0]
                  for line in self.cmd.run(['/bin/rc-status',
                                            '-s']).stdout.splitlines()
                  if 'started' in line]
        self.logger.debug('Found active services:')
        self.logger.debug(allsrv)
        specified = [srv.get('name') for srv in self.getSupportedEntries()]
        return [Bcfg2.Client.XML.Element('Service', type='rc-update',
                                         name=name)
                for name in allsrv if name not in specified]
