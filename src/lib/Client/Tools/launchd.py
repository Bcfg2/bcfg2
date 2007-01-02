'''launchd support for Bcfg2'''
__revision__ = '$Revision: 2596 $'

import glob, os
import Bcfg2.Client.Tools

class LaunchD(Bcfg2.Client.Tools.Tool):
    '''Support for Mac OS X Launchd Services'''
    __handles__ = [('Service', 'launchd')]
    __execs__ = ['/bin/launchctl', '/usr/bin/defaults']
    __name__ = 'LaunchD'
    __req__ = {'Service':['name', 'status', 'plist']}

    #currently requires the path to the plist to load/unload, and Name is acually a reverse-fqdn (or the label)
    
    def VerifyService(self, entry, _):
        '''Verify Launchd Service Entry'''
        
        try:
            services = self.cmd.run("/bin/launchctl list")
        except IndexError:#happens when no services are running (should be never)
            services = []
        if entry.get('name') in services:#doesn't check if non-spawning services are Started
            return entry.get('status') == 'on'
        else:
            self.logger.debug("Didn't find service Loaded (LaunchD running under same user as bcfg)")
            return entry.get('status') == 'off'

        try: #Perhaps add the "-w" flag to load and unload to modify the file itself!
            self.cmd.run("/bin/launchtl load %s" % entry.get('plist'))
        except IndexError:
            return "on"
        return "off"


    def InstallService(self, entry):
        '''Install SMF Service Entry'''
        pass

    def Remove(self, svcs):
        '''Remove Extra SMF entries'''
        pass

    def FindExtra(self):
        '''Find Extra LaunchD Services'''
        allsrv =  self.cmd.run("/bin/launchctl list")

        [allsrv.remove(svc) for svc in self.getSupportedEntries() if svc in allsrv]
        return [Bcfg2.Client.XML.Element("Service", type='launchd', name=name) \
                for name in allsrv]

    def BundleUpdated(self, bundle):
        '''Reload LaunchD plist'''
        for entry in [entry for entry in bundle if self.handlesEntry(entry)]:
            if not self.canInstall(entry):
                self.logger.error("Insufficient information to restart service %s" % (entry.get('name')))
            else:
                if entry.get('status') == 'on':
                    #may need to start/stop as well!
                    self.logger.info("Reloading LaunchD  service %s" % (entry.get("name")))
                    #stop?
                    self.cmd.run("/bin/launchctl unload %s" % (entry.get("plist")))#what if it disappeared? how do we stop services that are currently running but the plist disappeared?!
                    self.cmd.run("/bin/launchctl load %s" % (entry.get("plist")))
                    #start?
                else:
                    #may need to stop as well!
                    self.cmd.run("/bin/launchctl unload %s" % (entry.get("plist")))

