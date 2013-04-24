"""SMF support for Bcfg2"""

import glob
import os

import Bcfg2.Client.Tools


class SMF(Bcfg2.Client.Tools.SvcTool):
    """Support for Solaris SMF Services."""
    __handles__ = [('Service', 'smf')]
    __execs__ = ['/usr/sbin/svcadm', '/usr/bin/svcs']
    __req__ = {'Service': ['name', 'status', 'FMRI']}

    def get_svc_command(self, service, action):
        if service.get('type') == 'lrc':
            return Bcfg2.Client.Tools.SvcTool.get_svc_command(self,
                                                              service, action)
        if action == 'stop':
            return "/usr/sbin/svcadm disable %s" % (service.get('FMRI'))
        elif action == 'restart':
            return "/usr/sbin/svcadm restart %s" % (service.get('FMRI'))
        elif action == 'start':
            return "/usr/sbin/svcadm enable %s" % (service.get('FMRI'))

    def GetFMRI(self, entry):
        """Perform FMRI resolution for service."""
        if not 'FMRI' in entry.attrib:
            rv = self.cmd.run(["/usr/bin/svcs", "-H", "-o", "FMRI",
                               entry.get('name')])
            if rv.success:
                entry.set('FMRI', rv.stdout.splitlines()[0])
            else:
                self.logger.info('Failed to locate FMRI for service %s' %
                                 entry.get('name'))
            return rv.success
        return True

    def VerifyService(self, entry, _):
        """Verify SMF Service entry."""
        if not self.GetFMRI(entry):
            self.logger.error("smf service %s doesn't have FMRI set" %
                              entry.get('name'))
            return False
        if entry.get('FMRI').startswith('lrc'):
            filename = entry.get('FMRI').split('/')[-1]
            # this is a legacy service
            gname = "/etc/rc*.d/%s" % filename
            files = glob.glob(gname.replace('_', '.'))
            if files:
                self.logger.debug("Matched %s with %s" %
                                  (entry.get("FMRI"), ":".join(files)))
                return entry.get('status') == 'on'
            else:
                self.logger.debug("No service matching %s" %
                                  entry.get("FMRI"))
                return entry.get('status') == 'off'
        try:
            srvdata = \
                self.cmd.run("/usr/bin/svcs -H -o STA %s" %
                             entry.get('FMRI')).stdout.splitlines()[0].split()
        except IndexError:
            # Occurs when no lines are returned (service not installed)
            return False

        entry.set('current_status', srvdata[0])
        if entry.get('status') == 'on':
            return srvdata[0] == 'ON'
        else:
            return srvdata[0] in ['OFF', 'UN', 'MNT', 'DIS', 'DGD']

    def InstallService(self, entry):
        """Install SMF Service entry."""
        self.logger.info("Installing Service %s" % (entry.get('name')))
        if entry.get('status') == 'off':
            if entry.get("FMRI").startswith('lrc'):
                try:
                    loc = entry.get("FMRI")[4:].replace('_', '.')
                    self.logger.debug("Renaming file %s to %s" %
                                      (loc, loc.replace('/S', '/DISABLED.S')))
                    os.rename(loc, loc.replace('/S', '/DISABLED.S'))
                    return True
                except OSError:
                    self.logger.error("Failed to rename init script %s" % loc)
                    return False
            else:
                return self.cmd.run("/usr/sbin/svcadm disable %s" %
                                    entry.get('FMRI')).success
        elif entry.get('FMRI').startswith('lrc'):
            loc = entry.get("FMRI")[4:].replace('_', '.')
            try:
                os.stat(loc.replace('/S', '/Disabled.'))
                self.logger.debug("Renaming file %s to %s" %
                                  (loc.replace('/S', '/DISABLED.S'), loc))
                os.rename(loc.replace('/S', '/DISABLED.S'), loc)
                return True
            except OSError:
                self.logger.debug("Failed to rename %s to %s" %
                                  (loc.replace('/S', '/DISABLED.S'), loc))
                return False
        else:
            srvdata = \
                self.cmd.run("/usr/bin/svcs -H -o STA %s" %
                             entry.get('FMRI'))[1].splitlines()[0].split()
            if srvdata[0] == 'MNT':
                cmdarg = 'clear'
            else:
                cmdarg = 'enable'
            return self.cmd.run("/usr/sbin/svcadm %s -r %s" %
                                (cmdarg, entry.get('FMRI'))).success

    def Remove(self, svcs):
        """Remove Extra SMF entries."""
        # Extra service entry removal is nonsensical
        # Extra service entries should be reflected in config, even if disabled
        pass

    def FindExtra(self):
        """Find Extra SMF Services."""
        allsrv = []
        for srvc in self.cmd.run(["/usr/bin/svcs", "-a", "-H",
                                  "-o", "FMRI,STATE"]).stdout.splitlines():
            name, version = srvc.split()
            if version != 'disabled':
                allsrv.append(name)

        for svc in self.getSupportedEntries():
            if svc.get("FMRI") in allsrv:
                allsrv.remove(svc.get('FMRI'))
        return [Bcfg2.Client.XML.Element("Service", type='smf', name=name)
                for name in allsrv]
