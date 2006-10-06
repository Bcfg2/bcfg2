'''SMF support for Bcfg2'''
__revision__ = '$Revision$'

import glob, os
import Bcfg2.Client.Tools

class SMF(Bcfg2.Client.Tools.Tool):
    '''Support for Solaris SMF Services'''
    __handles__ = [('Service', 'smf')]
    __execs__ = ['/usr/sbin/svcadm', '/usr/bin/svcs']
    __name__ = 'SMF'
    __req__ = {'Service':['name', 'status']}
    __ireq__ = {'Service': ['name', 'status', 'FMRI']}

    def GetFMRI(self, entry):
        '''Perform FMRI resolution for service'''
        if not entry.attrib.has_key('FMRI'):
            name = self.cmd.run("/usr/bin/svcs -H -o FMRI %s 2>/dev/null" % \
                                entry.get('name'))[1]
            if name:
                entry.set('FMRI', name[0])
                return True
            else:
                self.logger.info('Failed to locate FMRI for service %s' % entry.get('name'))
                return False
    
    def VerifyService(self, entry, _):
        '''Verify SMF Service Entry'''
        if not self.GetFMRI(entry):
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
                self.logger.debug("No service matching %s" % (entry.get("FMRI")))
                return entry.get('status') == 'off'
        try:
            srvdata = self.cmd.run("/usr/bin/svcs -H -o STA %s" % entry.attrib['name'])[1][0].split()
        except IndexError:
            # Ocurrs when no lines are returned (service not installed)
            return False

        if entry.get('status') == 'on':
            return srvdata[0] == 'ON'
        else:
            return srvdata[0] in ['OFF', 'UN', 'MNT', 'DIS', 'DGD']

    def InstallService(self, entry):
        '''Install SMF Service Entry'''
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
                    self.logger.error("Failed to rename init script %s" % (loc))
                    return False
            else:
                cmdrc = self.cmd.run("/usr/sbin/svcadm disable %s" % \
                                     (entry.get('FMRI')))[0]
        else:
            if entry.get('FMRI').startswith('lrc'):
                loc = entry.get("FMRI")[4:].replace('_', ',')
                try:
                    os.stat(loc.replace('/S', '/Disabled.'))
                    self.logger.debug("Renaming file %s to %s" % \
                                      (loc.replace('/S', '/DISABLED.S'), loc))
                    os.rename(loc.replace('/S', '/DISABLED.S'), loc)
                    cmdrc = 0
                except OSError:
                    self.logger.debug("Failed to rename %s to %s" \
                                      % (loc.replace('/S', '/DISABLED.S'), loc))
                    cmdrc = 1
            else:
                cmdrc = self.cmd.run("/usr/sbin/svcadm enable -r %s" % \
                                     (entry.get('FMRI')))[0]
        return cmdrc == 0

    def Remove(self, svcs):
        '''Remove Extra SMF entries'''
        pass

    def FindExtra(self):
        '''Find Extra SMF Services'''
        allsrv = [name for name, version in \
                  [ srvc.strip().split() for srvc in
                    self.cmd.run("/usr/bin/svcs -a -H -o FMRI,STATE")[1] ]
                  if version != 'disabled']

        for svc in self.getSupportedEntries():
            name = self.cmd.run("/usr/bin/svcs -H -o FMRI %s 2>/dev/null" % \
                                svc.get('name'))[1]
            if name:
                svc.set('FMRI', name[0])
                if name in allsrv:
                    allsrv.remove(name)
            else:
                self.logger.info("Failed to locate FMRI for service %s" % svc.get('name'))
                
        return [Bcfg2.Client.XML.Element("Service", type='smf', name=name) for name in allsrv]

    def BundleUpdated(self, bundle):
        '''Restart smf services'''
        for entry in [entry for entry in bundle if self.handlesEntry(entry)]:
            if not self.canInstall(entry):
                self.logger.error("Insufficient information to restart service %s" % (entry.get('name')))
            else:
                if entry.get('status') == 'on':
                    self.logger.info("Restarting smf service %s" % (entry.get("FMRI")))
                    self.cmd.run("svcadm restart %s" % (entry.get("FMRI")))
                else:
                    self.cmd.run("svcadm disable %s" % (entry.get("FMRI")))

