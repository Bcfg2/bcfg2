"""Upstart support for Bcfg2."""

import glob
import re

import Bcfg2.Client.Tools
import Bcfg2.Client.XML


class Upstart(Bcfg2.Client.Tools.SvcTool):
    """Upstart service support for Bcfg2."""
    name = 'Upstart'
    __execs__ = ['/lib/init/upstart-job',
                 '/sbin/initctl',
                 '/usr/sbin/service']
    __handles__ = [('Service', 'upstart')]
    __req__ = {'Service': ['name', 'status']}
    svcre = re.compile("/etc/init/(?P<name>.*).conf")

    def get_svc_command(self, service, action):
        return "/usr/sbin/service %s %s" % (service.get('name'), action)

    def VerifyService(self, entry, _):
        """Verify Service status for entry

           Verifying whether or not the service is enabled can be done
           at the file level with upstart using the contents of
           /etc/init/servicename.conf. All we need to do is make sure
           the service is running when it should be.
        """

        if entry.get('status') == 'ignore':
            return True

        if entry.get('parameters'):
            params = entry.get('parameters')
        else:
            params = ''

        try:
            output = self.cmd.run('/usr/sbin/service %s status %s' %
                                  (entry.get('name'),
                                   params)).stdout.splitlines()[0]
        except IndexError:
            self.logger.error("Service %s not an Upstart service" %
                              entry.get('name'))
            return False

        match = re.compile(r'%s( \(.*\))? (start|stop)/(running|waiting)' %
                           entry.get('name')).match(output)
        if match is None:
            # service does not exist
            entry.set('current_status', 'off')
            status = False
        elif match.group(3) == 'running':
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
        return self.cmd.run(self.get_svc_command(entry, cmd)).success

    def FindExtra(self):
        """Locate extra Upstart services."""
        specified = [entry.get('name') for entry in self.getSupportedEntries()]
        extra = []
        for fname in glob.glob("/etc/init/*.conf"):
            if self.svcre.match(fname).group('name') not in specified:
                extra.append(self.svcre.match(fname).group('name'))
        return [Bcfg2.Client.XML.Element('Service', type='upstart', name=name)
                for name in extra]
