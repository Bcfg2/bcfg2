"""launchd support for Bcfg2."""

import os
import Bcfg2.Client.Tools


class launchd(Bcfg2.Client.Tools.Tool):  # pylint: disable=C0103
    """Support for Mac OS X launchd services.  Currently requires the
    path to the plist to load/unload, and Name is acually a
    reverse-fqdn (or the label)."""
    __handles__ = [('Service', 'launchd')]
    __execs__ = ['/bin/launchctl', '/usr/bin/defaults']
    __req__ = {'Service': ['name', 'status']}

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.Tool.__init__(self, logger, setup, config)

        # Locate plist file that provides given reverse-fqdn name:
        #
        # * ``/Library/LaunchAgents``: Per-user agents provided by the
        #   administrator.
        # * ``/Library/LaunchDaemons``: System-wide daemons provided
        #   by the administrator.
        # * ``/System/Library/LaunchAgents``: Mac OS X per-user
        #   agents.
        # * ``/System/Library/LaunchDaemons``: Mac OS X system-wide
        #   daemons.
        plist_locations = ["/Library/LaunchDaemons",
                           "/System/Library/LaunchDaemons"]
        self.plist_mapping = {}
        for directory in plist_locations:
            for daemon in os.listdir(directory):
                if daemon.endswith(".plist"):
                    daemon = daemon[:-6]
                dpath = os.path.join(directory, daemon)
                rv = self.cmd.run(['defaults', 'read', dpath, 'Label'])
                if rv.success:
                    label = rv.stdout.splitlines()[0]
                    self.plist_mapping[label] = dpath
                else:
                    self.logger.warning("Could not get label from %s" % dpath)

    def FindPlist(self, entry):
        """ Find the location of the plist file for the given entry """
        return self.plist_mapping.get(entry.get('name'), None)

    def os_version(self):
        """ Determine the OS version """
        rv = self.cmd.run('sw_vers')
        if rv:
            for line in rv.stdout.splitlines():
                if line.startswith("ProductVersion"):
                    return line.split()[-1]
        else:
            return ''

    def VerifyService(self, entry, _):
        """Verify launchd service entry."""
        if entry.get('status') == 'ignore':
            return True

        try:
            services = self.cmd.run("/bin/launchctl list").stdout.splitlines()
        except IndexError:
            # happens when no services are running (should be never)
            services = []
        # launchctl output changed in 10.5
        # It is now three columns, with the last
        # column being the name of the # service
        if int(self.os_version().split('.')[1]) >= 5:
            services = [s.split()[-1] for s in services]
        if entry.get('name') in services:
            # doesn't check if non-spawning services are Started
            return entry.get('status') == 'on'
        else:
            self.logger.debug("Launchd: Didn't find service Loaded "
                              "(launchd running under same user as bcfg)")
            return entry.get('status') == 'off'

        try:
            # Perhaps add the "-w" flag to load and
            # unload to modify the file itself!
            self.cmd.run("/bin/launchctl load -w %s" % self.FindPlist(entry))
        except IndexError:
            return 'on'
        return False

    def InstallService(self, entry):
        """Enable or disable launchd item."""
        name = entry.get('name')
        if entry.get('status') == 'on':
            self.logger.error("Installing service %s" % name)
            self.cmd.run("/bin/launchctl load -w %s" % self.FindPlist(entry))
            return self.cmd.run("/bin/launchctl start %s" % name).success
        else:
            self.logger.error("Uninstalling service %s" % name)
            self.cmd.run("/bin/launchctl stop %s" % name)
            return self.cmd.run("/bin/launchctl unload -w %s" %
                                self.FindPlist(entry)).success

    def Remove(self, svcs):
        """Remove Extra launchd entries."""
        pass

    def FindExtra(self):
        """Find Extra launchd services."""
        try:
            allsrv = self.cmd.run("/bin/launchctl list").stdout.splitlines()
        except IndexError:
            allsrv = []

        for entry in self.getSupportedEntries():
            svc = entry.get("name")
            if svc in allsrv:
                allsrv.remove(svc)
        return [Bcfg2.Client.XML.Element("Service", type='launchd', name=name,
                                         status='on')
                for name in allsrv]

    def BundleUpdated(self, bundle, states):
        """Reload launchd plist."""
        for entry in [entry for entry in bundle if self.handlesEntry(entry)]:
            if not self.canInstall(entry):
                self.logger.error("Insufficient information to restart "
                                  "service %s" % entry.get('name'))
            else:
                name = entry.get('name')
                if entry.get('status') == 'on' and self.FindPlist(entry):
                    self.logger.info("Reloading launchd service %s" % name)
                    # stop?
                    self.cmd.run("/bin/launchctl stop %s" % name)
                    # what if it disappeared? how do we stop services
                    # that are currently running but the plist disappeared?!
                    self.cmd.run("/bin/launchctl unload -w %s" %
                                 (self.FindPlist(entry)))
                    self.cmd.run("/bin/launchctl load -w %s" %
                                 (self.FindPlist(entry)))
                    self.cmd.run("/bin/launchctl start %s" % name)
                else:
                    # only if necessary....
                    self.cmd.run("/bin/launchctl stop %s" % name)
                    self.cmd.run("/bin/launchctl unload -w %s" %
                                 (self.FindPlist(entry)))
