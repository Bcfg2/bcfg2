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
        pass

