'''launchd support for Bcfg2'''
__revision__ = '$Revision$'

import os
import Bcfg2.Client.Tools
import popen2

class launchd(Bcfg2.Client.Tools.Tool):
    '''Support for Mac OS X Launchd Services'''
    __handles__ = [('Service', 'launchd')]
    __execs__ = ['/bin/launchctl', '/usr/bin/defaults']
    name = 'launchd'
    __req__ = {'Service':['name', 'status']}

    '''
    currently requires the path to the plist to load/unload,
    and Name is acually a reverse-fqdn (or the label)
    '''
    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.Tool.__init__(self, logger, setup, config)

        '''Locate plist file that provides given reverse-fqdn name
        /Library/LaunchAgents          Per-user agents provided by the administrator.
        /Library/LaunchDaemons         System wide daemons provided by the administrator.
        /System/Library/LaunchAgents   Mac OS X Per-user agents.
        /System/Library/LaunchDaemons  Mac OS X System wide daemons.'''
        plistLocations = ["/Library/LaunchDaemons", "/System/Library/LaunchDaemons"]
        self.plistMapping = {}
        for directory in plistLocations:
            for daemon in os.listdir(directory):
                try:
                    if daemon.endswith(".plist"):
                        d = daemon[:-6]
                    else:
                        d = daemon
                    (stdout, _) = popen2.popen2('defaults read %s/%s Label' % (directory, d))
                    label = stdout.read().strip()
                    self.plistMapping[label] = "%s/%s" % (directory, daemon)
                except KeyError: #perhaps this could be more robust
                    pass

    def FindPlist(self, entry):
        return self.plistMapping.get(entry.get('name'), None)

    def os_version(self):
        version = ""
        try:
            vers = self.cmd.run('sw_vers')[1]
        except:
            return version

        for line in vers:
            if line.startswith("ProductVersion"):
                version = line.split()[-1]
        return version

    def VerifyService(self, entry, _):
        '''Verify Launchd Service Entry'''
        try:
            services = self.cmd.run("/bin/launchctl list")[1]
        except IndexError:#happens when no services are running (should be never)
            services = []
        # launchctl output changed in 10.5
        # It is now three columns, with the last column being the name of the # service
        version = self.os_version()
        if version.startswith('10.5') or version.startswith('10.6'):
            services = [s.split()[-1] for s in services]
        if entry.get('name') in services:#doesn't check if non-spawning services are Started
            return entry.get('status') == 'on'
        else:
            self.logger.debug("Didn't find service Loaded (launchd running under same user as bcfg)")
            return entry.get('status') == 'off'

        try: #Perhaps add the "-w" flag to load and unload to modify the file itself!
            self.cmd.run("/bin/launchctl load -w %s" % self.FindPlist(entry))
        except IndexError:
            return 'on'
        return False


    def InstallService(self, entry):
        '''Enable or Disable launchd Item'''
        name = entry.get('name')
        if entry.get('status') == 'on':
            self.logger.error("Installing service %s" % name)
            cmdrc = self.cmd.run("/bin/launchctl load -w %s" % self.FindPlist(entry))[0]
            cmdrc = self.cmd.run("/bin/launchctl start %s" % name)
        else:
            self.logger.error("Uninstalling service %s" % name)
            cmdrc = self.cmd.run("/bin/launchctl stop %s" % name)
            cmdrc = self.cmd.run("/bin/launchctl unload -w %s" % self.FindPlist(entry))[0]
        return cmdrc[0] == 0

    def Remove(self, svcs):
        '''Remove Extra launchd entries'''
        pass



    def FindExtra(self):
        '''Find Extra launchd Services'''
        try:
            allsrv =  self.cmd.run("/bin/launchctl list")[1]
        except IndexError:
            allsrv = []

        [allsrv.remove(svc) for svc in [entry.get("name") for entry
                                        in self.getSupportedEntries()] if svc in allsrv]
        return [Bcfg2.Client.XML.Element("Service", type='launchd', name=name, status='on') for name in allsrv]

    def BundleUpdated(self, bundle, states):
        '''Reload launchd plist'''
        for entry in [entry for entry in bundle if self.handlesEntry(entry)]:
            if not self.canInstall(entry):
                self.logger.error("Insufficient information to restart service %s" % (entry.get('name')))
            else:
                name = entry.get('name')
                if entry.get('status') == 'on' and self.FindPlist(entry):
                    self.logger.info("Reloading launchd  service %s" % name)
                    #stop?
                    self.cmd.run("/bin/launchctl stop %s" % name)
                    self.cmd.run("/bin/launchctl unload -w %s" % (self.FindPlist(entry)))#what if it disappeared? how do we stop services that are currently running but the plist disappeared?!
                    self.cmd.run("/bin/launchctl load -w %s" % (self.FindPlist(entry)))
                    self.cmd.run("/bin/launchctl start %s" % name)
                else:
                    #only if necessary....
                    self.cmd.run("/bin/launchctl stop %s" % name)
                    self.cmd.run("/bin/launchctl unload -w %s" % (self.FindPlist(entry)))

