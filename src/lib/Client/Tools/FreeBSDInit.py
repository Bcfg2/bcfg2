'''FreeBSD Init Support for Bcfg2'''
__revision__ = '$Rev$'

# TODO
# - hardcoded path to ports rc.d
# - doesn't know about /etc/rc.d/

import Bcfg2.Client.Tools

class FreeBSDInit(Bcfg2.Client.Tools.SvcTool):
    '''FreeBSD Service Support for Bcfg2'''
    name = 'FreeBSDInit'
    __handles__ = [('Service', 'freebsd')]
    __req__ = {'Service': ['name', 'status']}
    __svcrestart__ = 'restart'

    def VerifyService(self, entry, _):
        return True

    def BundleUpdated(self, bundle, states):
        '''The Bundle has been updated'''
        for entry in bundle:
            if self.handlesEntry(entry):
                command = "/usr/local/etc/rc.d/%s" % entry.get('name')
                if entry.get('status') == 'on' and not self.setup['build']:
                    self.logger.debug('Restarting service %s' % \
                                      entry.get('name'))
                    rc = self.cmd.run('%s %s' % (command, \
                        entry.get('reload', self.__svcrestart__)))[0]
                else:
                    self.logger.debug('Stopping service %s' % entry.get('name'))
                    rc = self.cmd.run('%s stop' %  command)[0]
                if rc:
                    self.logger.error("Failed to restart service %s" % \
                                     (entry.get('name')))

