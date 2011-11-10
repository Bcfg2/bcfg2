# This is the bcfg2 support for chkconfig
# $Id$

"""This is chkconfig support."""
__revision__ = '$Revision$'

import os

import Bcfg2.Client.Tools
import Bcfg2.Client.XML


class Chkconfig(Bcfg2.Client.Tools.SvcTool):
    """Chkconfig support for Bcfg2."""
    name = 'Chkconfig'
    __execs__ = ['/sbin/chkconfig']
    __handles__ = [('Service', 'chkconfig')]
    __req__ = {'Service': ['name', 'status']}
    os.environ['LANG'] = 'C'

    def get_svc_command(self, service, action):
        return "/sbin/service %s %s" % (service.get('name'), action)

    def VerifyService(self, entry, _):
        """Verify Service status for entry."""
        try:
            cmd = "/sbin/chkconfig --list %s " % (entry.get('name'))
            raw = self.cmd.run(cmd)[1]
            patterns = ["error reading information", "unknown service"]
            srvdata = [line.split() for line in raw for pattern in patterns \
                       if pattern not in line][0]
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            entry.set('current_status', 'off')
            return False
        if len(srvdata) == 2:
            # This is an xinetd service
            if entry.get('status') == srvdata[1]:
                return True
            else:
                entry.set('current_status', srvdata[1])
                return False

        try:
            onlevels = [level.split(':')[0] for level in srvdata[1:] \
                        if level.split(':')[1] == 'on']
        except IndexError:
            onlevels = []

        if entry.get('status') == 'on':
            status = (len(onlevels) > 0)
            command = 'start'
        else:
            status = (len(onlevels) == 0)
            command = 'stop'

        if entry.get('mode', 'default') == 'supervised':
            # turn on or off the service in supervised mode
            pstatus = self.cmd.run('/sbin/service %s status' % \
                                   entry.get('name'))[0]
            needs_modification = ((command == 'start' and pstatus) or \
                                  (command == 'stop' and not pstatus))
            if (not self.setup.get('dryrun') and
                self.setup['servicemode'] != 'disabled' and
                needs_modification):
                self.cmd.run(self.get_svc_command(entry, command))
                # service was modified, so it failed
                pstatus = False

            # chkconfig/init.d service
            if entry.get('status') == 'on':
                status = status and not pstatus

        if not status:
            if entry.get('status') == 'on':
                entry.set('current_status', 'off')
            else:
                entry.set('current_status', 'on')
        return status

    def InstallService(self, entry):
        """Install Service entry."""
        # don't take any actions for mode='manual'
        if entry.get('mode', 'default') == 'manual':
            self.logger.info("Service %s mode set to manual. Skipping "
                             "installation." % (entry.get('name')))
            return False
        rcmd = "/sbin/chkconfig %s %s"
        self.cmd.run("/sbin/chkconfig --add %s" % (entry.attrib['name']))
        self.logger.info("Installing Service %s" % (entry.get('name')))
        pass1 = True
        if entry.get('status') == 'off':
            rc = self.cmd.run(rcmd % (entry.get('name'),
                                      entry.get('status')) + \
                 " --level 0123456")[0]
            pass1 = rc == 0
        rc = self.cmd.run(rcmd % (entry.get('name'), entry.get('status')))[0]
        return pass1 and rc == 0

    def FindExtra(self):
        """Locate extra chkconfig Services."""
        allsrv = [line.split()[0] for line in \
                  self.cmd.run("/sbin/chkconfig --list 2>/dev/null|grep :on")[1]]
        self.logger.debug('Found active services:')
        self.logger.debug(allsrv)
        specified = [srv.get('name') for srv in self.getSupportedEntries()]
        return [Bcfg2.Client.XML.Element('Service',
                                         type='chkconfig',
                                         name=name) \
                for name in allsrv if name not in specified]
