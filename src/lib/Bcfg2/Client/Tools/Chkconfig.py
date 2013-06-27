# This is the bcfg2 support for chkconfig

"""This is chkconfig support."""

import os

import Bcfg2.Client.Tools
import Bcfg2.Client.XML


class Chkconfig(Bcfg2.Client.Tools.SvcTool):
    """Chkconfig support for Bcfg2."""
    name = 'Chkconfig'
    __execs__ = ['/sbin/chkconfig']
    __handles__ = [('Service', 'chkconfig')]
    __req__ = {'Service': ['name', 'status']}
    os.environ['LC_ALL'] = 'C'

    def get_svc_command(self, service, action):
        return "/sbin/service %s %s" % (service.get('name'), action)

    def verify_bootstatus(self, entry, bootstatus):
        """Verify bootstatus for entry."""
        rv = self.cmd.run("/sbin/chkconfig --list %s " % entry.get('name'))
        if rv.success:
            srvdata = rv.stdout.splitlines()[0].split()
        else:
            # service not installed
            entry.set('current_bootstatus', 'service not installed')
            return False

        if len(srvdata) == 2:
            # This is an xinetd service
            if bootstatus == srvdata[1]:
                return True
            else:
                entry.set('current_bootstatus', srvdata[1])
                return False

        try:
            onlevels = [level.split(':')[0] for level in srvdata[1:]
                        if level.split(':')[1] == 'on']
        except IndexError:
            onlevels = []

        if bootstatus == 'on':
            current_bootstatus = (len(onlevels) > 0)
        else:
            current_bootstatus = (len(onlevels) == 0)
        return current_bootstatus

    def VerifyService(self, entry, _):
        """Verify Service status for entry."""
        entry.set('target_status', entry.get('status'))  # for reporting
        bootstatus = self.get_bootstatus(entry)
        if bootstatus is None:
            return True
        current_bootstatus = self.verify_bootstatus(entry, bootstatus)

        if entry.get('status') == 'ignore':
            # 'ignore' should verify
            current_svcstatus = True
            svcstatus = True
        else:
            svcstatus = self.check_service(entry)
            if entry.get('status') == 'on':
                if svcstatus:
                    current_svcstatus = True
                else:
                    current_svcstatus = False
            elif entry.get('status') == 'off':
                if svcstatus:
                    current_svcstatus = False
                else:
                    current_svcstatus = True

        if svcstatus:
            entry.set('current_status', 'on')
        else:
            entry.set('current_status', 'off')

        return current_bootstatus and current_svcstatus

    def InstallService(self, entry):
        """Install Service entry."""
        self.cmd.run("/sbin/chkconfig --add %s" % (entry.get('name')))
        self.logger.info("Installing Service %s" % (entry.get('name')))
        bootstatus = self.get_bootstatus(entry)
        if bootstatus is not None:
            if bootstatus == 'on':
                # make sure service is enabled on boot
                bootcmd = '/sbin/chkconfig %s %s --level 0123456' % \
                          (entry.get('name'), bootstatus)
            elif bootstatus == 'off':
                # make sure service is disabled on boot
                bootcmd = '/sbin/chkconfig %s %s' % (entry.get('name'),
                                                     bootstatus)
            bootcmdrv = self.cmd.run(bootcmd).success
            if self.setup['servicemode'] == 'disabled':
                # 'disabled' means we don't attempt to modify running svcs
                return bootcmdrv
            buildmode = self.setup['servicemode'] == 'build'
            if (entry.get('status') == 'on' and not buildmode) and \
               entry.get('current_status') == 'off':
                svccmdrv = self.start_service(entry)
            elif (entry.get('status') == 'off' or buildmode) and \
                    entry.get('current_status') == 'on':
                svccmdrv = self.stop_service(entry)
            else:
                svccmdrv = True  # ignore status attribute
            return bootcmdrv and svccmdrv
        else:
            # when bootstatus is 'None', status == 'ignore'
            return True

    def FindExtra(self):
        """Locate extra chkconfig Services."""
        allsrv = [line.split()[0]
                  for line in self.cmd.run("/sbin/chkconfig",
                                           "--list").stdout.splitlines()
                  if ":on" in line]
        self.logger.debug('Found active services:')
        self.logger.debug(allsrv)
        specified = [srv.get('name') for srv in self.getSupportedEntries()]
        return [Bcfg2.Client.XML.Element('Service', type='chkconfig',
                                         name=name)
                for name in allsrv if name not in specified]
