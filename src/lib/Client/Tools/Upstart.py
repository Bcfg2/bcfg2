'''Upstart support for Bcfg2'''
__revision__ = '$Revision$'

import glob
import re

import Bcfg2.Client.Tools
import Bcfg2.Client.XML


class Upstart(Bcfg2.Client.Tools.SvcTool):
    '''Upstart service support for Bcfg2'''
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
        '''Verify Service status for entry

           Verifying whether or not the service is enabled can be done
           at the file level with upstart using the contents of
           /etc/init/servicename.conf. All we need to do is make sure
           the service is running when it should be.
        '''
        try:
            output = self.cmd.run('/usr/sbin/service %s status' % \
                                  entry.get('name'))[1][0]
        except IndexError:
            self.logger.error("Service %s not an Upstart service" % \
                              entry.get('name'))
            return False
        try:
            running = output.split(' ')[1].split('/')[1].startswith('running')
            if running:
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
        except IndexError:
            # service does not exist
            entry.set('current_status', 'off')
            status = False

        return status

    def InstallService(self, entry):
        '''Install Service for entry'''
        if entry.get('mode', 'default') == 'supervised':
            pstatus, pout = self.cmd.run('/usr/sbin/service %s status' % \
                                         entry.get('name'))
            if pstatus:
                self.cmd.run('/usr/sbin/service %s start' % (entry.get('name')))
        return True

    def FindExtra(self):
        '''Locate extra Upstart services'''
        specified = [entry.get('name') for entry in self.getSupportedEntries()]
        extra = []
        for name in [self.svcre.match(fname).group('name') for fname in
                     glob.glob("/etc/init/*.conf") \
                     if self.svcre.match(fname).group('name') not in specified]:
            extra.append(name)
        return [Bcfg2.Client.XML.Element('Service', type='upstart', name=name) \
                for name in extra]
