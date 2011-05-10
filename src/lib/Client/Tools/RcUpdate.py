"""This is rc-update support."""
__revision__ = '$Revision$'

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
        # check if service is enabled
        cmd = '/sbin/rc-update show default | grep %s'
        rc = self.cmd.run(cmd % entry.get('name'))[0]
        is_enabled = (rc == 0)

        if entry.get('mode', 'default') == 'supervised':
            # check if init script exists
            try:
                os.stat('/etc/init.d/%s' % entry.get('name'))
            except OSError:
                self.logger.debug('Init script for service %s does not exist' %
                                  entry.get('name'))
                return False

            # check if service is enabled
            cmd = '/etc/init.d/%s status | grep started'
            rc = self.cmd.run(cmd % entry.attrib['name'])[0]
            is_running = (rc == 0)
        else:
            # we don't care
            is_running = is_enabled

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
        In supervised mode we also take care it's (not) running.

        """
        # don't take any actions for mode='manual'
        if entry.get('mode', 'default') == 'manual':
            self.logger.info("Service %s mode set to manual. Skipping "
                             "installation." % (entry.get('name')))
            return False
        self.logger.info('Installing Service %s' % entry.get('name'))
        if entry.get('status') == 'on':
            # make sure it's running if in supervised mode
            if entry.get('mode', 'default') == 'supervised' \
               and entry.get('current_status') == 'off':
                self.start_service(entry)
            # make sure it's enabled
            cmd = '/sbin/rc-update add %s default'
            rc = self.cmd.run(cmd % entry.get('name'))[0]
            return (rc == 0)

        elif entry.get('status') == 'off':
            # make sure it's not running if in supervised mode
            if entry.get('mode', 'default') == 'supervised' \
               and entry.get('current_status') == 'on':
                self.stop_service(entry)
            # make sure it's disabled
            cmd = '/sbin/rc-update del %s default'
            rc = self.cmd.run(cmd % entry.get('name'))[0]
            return (rc == 0)

        return False

    def FindExtra(self):
        """Locate extra rc-update services."""
        cmd = '/bin/rc-status -s | grep started'
        allsrv = [line.split()[0] for line in self.cmd.run(cmd)[1]]
        self.logger.debug('Found active services:')
        self.logger.debug(allsrv)
        specified = [srv.get('name') for srv in self.getSupportedEntries()]
        return [Bcfg2.Client.XML.Element('Service',
                                         type='rc-update',
                                         name=name) \
                for name in allsrv if name not in specified]
