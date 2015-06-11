"""FreeBSD Init Support for Bcfg2."""

import os
import re
import Bcfg2.Options
import Bcfg2.Client.Tools


class FreeBSDInit(Bcfg2.Client.Tools.SvcTool):
    """FreeBSD service support for Bcfg2."""
    name = 'FreeBSDInit'
    __execs__ = ['/usr/sbin/service', '/usr/sbin/sysrc']
    __handles__ = [('Service', 'freebsd')]
    __req__ = {'Service': ['name', 'status']}
    rcvar_re = re.compile(r'^(?P<var>[a-z_]+_enable)="[A-Z]+"$')

    def get_svc_command(self, service, action):
        return '/usr/sbin/service %s %s' % (service.get('name'), action)

    def verify_bootstatus(self, entry, bootstatus):
        """Verify bootstatus for entry."""
        cmd = self.get_svc_command(entry, 'enabled')
        current_bootstatus = bool(self.cmd.run(cmd))

        if bootstatus == 'off':
            if current_bootstatus:
                entry.set('current_bootstatus', 'on')
                return False
            return True
        elif not current_bootstatus:
            entry.set('current_bootstatus', 'off')
            return False
        return True

    def check_service(self, entry):
        # use 'onestatus' to enable status reporting for disabled services
        cmd = self.get_svc_command(entry, 'onestatus')
        return bool(self.cmd.run(cmd))

    def stop_service(self, service):
        # use 'onestop' to enable stopping of disabled services
        self.logger.debug('Stopping service %s' % service.get('name'))
        return self.cmd.run(self.get_svc_command(service, 'onestop'))

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
        self.logger.info("Installing Service %s" % (entry.get('name')))
        bootstatus = self.get_bootstatus(entry)

        # check if service exists
        all_services_cmd = '/usr/sbin/service -l'
        all_services = self.cmd.run(all_services_cmd).stdout.splitlines()
        if entry.get('name') not in all_services:
            self.logger.debug("Service %s does not exist" % entry.get('name'))
            return False

        # get rcvar for service
        vars = set()
        rcvar_cmd = self.get_svc_command(entry, 'rcvar')
        for line in self.cmd.run(rcvar_cmd).stdout.splitlines():
            match = self.rcvar_re.match(line)
            if match:
                vars.add(match.group('var'))

        if bootstatus is not None:
            bootcmdrv = True
            sysrcstatus = None
            if bootstatus == 'on':
                sysrcstatus = 'YES'
            elif bootstatus == 'off':
                sysrcstatus = 'NO'
            if sysrcstatus is not None:
                for var in vars:
                    if not self.cmd.run('/usr/sbin/sysrc %s="%s"' % (var, sysrcstatus)):
                        bootcmdrv = False
                        break

            if  Bcfg2.Options.setup.service_mode == 'disabled':
                # 'disabled' means we don't attempt to modify running svcs
                return bootcmdrv
            buildmode = Bcfg2.Options.setup.service_mode == 'build'
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
        """Find Extra FreeBSD Service entries."""
        specified = [entry.get('name') for entry in self.getSupportedEntries()]
        extra = set()
        for path in self.cmd.run("/usr/sbin/service -e").stdout.splitlines():
            name = os.path.basename(path)
            if name not in specified:
                extra.add(name)
        return [Bcfg2.Client.XML.Element('Service', name=name, type='freebsd')
                for name in list(extra)]

    def Remove(self, _):
        """Remove extra service entries."""
        # Extra service removal is nonsensical
        # Extra services need to be reflected in the config
        return
