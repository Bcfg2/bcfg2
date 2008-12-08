'''This is rc-update support'''
__revision__ = '$Revision$'

import Bcfg2.Client.Tools, Bcfg2.Client.XML, commands, os

class RcUpdate(Bcfg2.Client.Tools.SvcTool):
    '''RcUpdate support for Bcfg2'''
    name = 'RcUpdate'
    __execs__ = ['/sbin/rc-update', '/bin/rc-status']
    __handles__ = [('Service', 'rc-update')]
    __req__ = {'Service': ['name', 'status']}

    def VerifyService(self, entry, _):
        '''
        Verify Service status for entry.
        Assumes we run in the "default" runlevel.
        '''
        # mrj - i think this should be:
        # rc = self.cmd.run('/bin/rc-status | \
        #                    grep %s | \
        #                    grep started"' % entry.attrib['name'])
        #
        # ...but as i can't figure out a way to
        #    test that right now, i'll do the one 
        #    that works in python's interactive interpreter.
        rc = commands.getoutput('/bin/rc-status | grep %s | grep started' % \
                                entry.get('name'))
        status = len(rc) > 0

        if not status:
            # service is off
            if entry.get('status') == 'on':
                # we want it on, it's not
                entry.set('current_status', 'off')
            else:
                # we want it off, it's not
                entry.set('current_status', 'on')
        return status

    def InstallService(self, entry):
        '''Install Service entry'''
        self.logger.info("Installing Service %s" % (entry.get('name')))
        try:
            os.stat('/etc/init.d/%s' % entry.get('name'))
        except OSError:
            self.logger.debug("Init script for service %s does not exist" %
                              entry.get('name'))
            return False

        if entry.get('status') == 'off':
            self.cmd.run("/etc/init.d/%s stop" % (entry.get('name')))
            cmdrc = self.cmd.run("/sbin/rc-update del %s default" %
                                (entry.get('name')))
        else:
            cmdrc = self.cmd.run("/sbin/rc-update add %s default" %
                                 entry.get('name'))[0]
        return cmdrc == 0

    def FindExtra(self):
        '''Locate extra rc-update Services'''
        allsrv = [line.split()[0] for line in \
                  self.cmd.run("/bin/rc-status | grep started")[1]]
        self.logger.debug('Found active services:')
        self.logger.debug(allsrv)
        specified = [srv.get('name') for srv in self.getSupportedEntries()]
        return [Bcfg2.Client.XML.Element('Service', type='rc-update', name=name) \
                for name in allsrv if name not in specified]

