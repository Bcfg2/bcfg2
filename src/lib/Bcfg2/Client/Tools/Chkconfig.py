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

    def VerifyService(self, entry, _):
        """Verify Service status for entry."""
        if entry.get('status') == 'ignore':
            return True

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

        pstatus = self.check_service(entry)
        if entry.get('status') == 'on':
            status = (len(onlevels) > 0 and pstatus)
        else:
            status = (len(onlevels) == 0 and not pstatus)

        if not status:
            if entry.get('status') == 'on':
                entry.set('current_status', 'off')
            else:
                entry.set('current_status', 'on')
        return status

    def InstallService(self, entry):
        """Install Service entry."""
        rcmd = "/sbin/chkconfig %s %s"
        self.cmd.run("/sbin/chkconfig --add %s" % (entry.attrib['name']))
        self.logger.info("Installing Service %s" % (entry.get('name')))
        rv = True
        if entry.get('status') == 'off':
            rv &= self.cmd.run((rcmd + " --level 0123456") %
                               (entry.get('name'),
                                entry.get('status')))[0] == 0
            if entry.get("current_status") == "on":
                rv &= self.stop_service(entry)
        else:
            rv &= self.cmd.run(rcmd % (entry.get('name'),
                                       entry.get('status')))[0] == 0
            if entry.get("current_status") == "off":
                rv &= (self.start_service(entry) == 0)
        return rv

    def FindExtra(self):
        """Locate extra chkconfig Services."""
        allsrv = [line.split()[0]
                  for line in self.cmd.run("/sbin/chkconfig "
                                           "--list 2>/dev/null|grep :on")[1]]
        self.logger.debug('Found active services:')
        self.logger.debug(allsrv)
        specified = [srv.get('name') for srv in self.getSupportedEntries()]
        return [Bcfg2.Client.XML.Element('Service',
                                         type='chkconfig',
                                         name=name) \
                for name in allsrv if name not in specified]
