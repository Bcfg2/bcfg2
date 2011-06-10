"""SMF support for Bcfg2"""
__revision__ = '$Revision$'

import glob
import os

import Bcfg2.Client.Tools


class SMF(Bcfg2.Client.Tools.SvcTool):
    """Support for Solaris SMF Services."""
    __handles__ = [('Service', 'smf')]
    __execs__ = ['/usr/sbin/svcadm', '/usr/bin/svcs']
    name = 'SMF'
    __req__ = {'Service': ['name', 'status']}
    __ireq__ = {'Service': ['name', 'status', 'FMRI']}

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
            name = self.cmd.run("/usr/bin/svcs -H -o FMRI %s 2>/dev/null" % \
                                entry.get('name'))[1]
            if name:
                entry.set('FMRI', name[0])
                return True
            else:
                self.logger.info('Failed to locate FMRI for service %s' % \
                                 entry.get('name'))
                return False
        return True

    def VerifyService(self, entry, _):
        """Verify SMF Service entry."""
        if not self.GetFMRI(entry):
            self.logger.error("smf service %s doesn't have FMRI set" % \
                              entry.get('name'))
            return False
        if entry.get('FMRI').startswith('lrc'):
            filename = entry.get('FMRI').split('/')[-1]
            # this is a legacy service
            gname = "/etc/rc*.d/%s" % filename
            files = glob.glob(gname.replace('_', '.'))
            if files:
                self.logger.debug("Matched %s with %s" % \
                                  (entry.get("FMRI"), ":".join(files)))
                return entry.get('status') == 'on'
            else:
                self.logger.debug("No service matching %s" % \
                                  (entry.get("FMRI")))
                return entry.get('status') == 'off'
        try:
            srvdata = self.cmd.run("/usr/bin/svcs -H -o STA %s" % \
                                   entry.get('FMRI'))[1][0].split()
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
        # don't take any actions for mode='manual'
        if entry.get('mode', 'default') == 'manual':
            self.logger.info("Service %s mode set to manual. Skipping "
                             "installation." % (entry.get('name')))
            return False
        self.logger.info("Installing Service %s" % (entry.get('name')))
        if entry.get('status') == 'off':
            if entry.get("FMRI").startswith('lrc'):
                try:
                    loc = entry.get("FMRI")[4:].replace('_', '.')
                    self.logger.debug("Renaming file %s to %s" % \
                                      (loc, loc.replace('/S', '/DISABLED.S')))
                    os.rename(loc, loc.replace('/S', '/DISABLED.S'))
                    return True
                except OSError:
                    self.logger.error("Failed to rename init script %s" % \
                                      (loc))
                    return False
            else:
                cmdrc = self.cmd.run("/usr/sbin/svcadm disable %s" % \
                                     (entry.get('FMRI')))[0]
        else:
            if entry.get('FMRI').startswith('lrc'):
                loc = entry.get("FMRI")[4:].replace('_', '.')
                try:
                    os.stat(loc.replace('/S', '/Disabled.'))
                    self.logger.debug("Renaming file %s to %s" % \
                                      (loc.replace('/S', '/DISABLED.S'), loc))
                    os.rename(loc.replace('/S', '/DISABLED.S'), loc)
                    cmdrc = 0
                except OSError:
                    self.logger.debug("Failed to rename %s to %s" % \
                                      (loc.replace('/S', '/DISABLED.S'), loc))
                    cmdrc = 1
            else:
                srvdata = self.cmd.run("/usr/bin/svcs -H -o STA %s" %
                                       entry.get('FMRI'))[1] [0].split()
                if srvdata[0] == 'MNT':
                    cmdarg = 'clear'
                else:
                    cmdarg = 'enable'
                cmdrc = self.cmd.run("/usr/sbin/svcadm %s -r %s" % \
                                     (cmdarg, entry.get('FMRI')))[0]
        return cmdrc == 0

    def Remove(self, svcs):
        """Remove Extra SMF entries."""
        # Extra service entry removal is nonsensical
        # Extra service entries should be reflected in config, even if disabled
        pass

    def FindExtra(self):
        """Find Extra SMF Services."""
        allsrv = [name for name, version in \
                  [srvc.split() for srvc in
                   self.cmd.run("/usr/bin/svcs -a -H -o FMRI,STATE")[1]]
                  if version != 'disabled']

        [allsrv.remove(svc.get('FMRI')) for svc in self.getSupportedEntries() \
         if svc.get("FMRI") in allsrv]
        return [Bcfg2.Client.XML.Element("Service", type='smf', name=name) \
                for name in allsrv]
