"""Debian Init Support for Bcfg2"""

import glob
import os
import re
import Bcfg2.Client.Tools

# Debian squeeze and beyond uses a dependecy based boot sequence
DEBIAN_OLD_STYLE_BOOT_SEQUENCE = ('etch', '4.0', 'lenny')


class DebInit(Bcfg2.Client.Tools.SvcTool):
    """Debian Service Support for Bcfg2."""
    name = 'DebInit'
    __execs__ = ['/usr/sbin/update-rc.d', '/usr/sbin/invoke-rc.d']
    __handles__ = [('Service', 'deb')]
    __req__ = {'Service': ['name', 'status']}
    svcre = \
        re.compile(r'/etc/.*/(?P<action>[SK])(?P<sequence>\d+)(?P<name>\S+)')

    # implement entry (Verify|Install) ops
    def VerifyService(self, entry, _):
        """Verify Service status for entry."""

        if entry.get('status') == 'ignore':
            return True

        rawfiles = glob.glob("/etc/rc*.d/[SK]*%s" % (entry.get('name')))
        files = []

        try:
            deb_version = open('/etc/debian_version').read().split('/', 1)[0]
        except IOError:
            deb_version = 'unknown'

        if entry.get('sequence'):
            if (deb_version in DEBIAN_OLD_STYLE_BOOT_SEQUENCE or
                deb_version.startswith('5') or
                os.path.exists('/etc/init.d/.legacy-bootordering')):
                start_sequence = int(entry.get('sequence'))
                kill_sequence = 100 - start_sequence
            else:
                start_sequence = None
                self.logger.warning("Your debian version boot sequence is "
                                    "dependency based \"sequence\" attribute "
                                    "will be ignored.")
        else:
            start_sequence = None

        for filename in rawfiles:
            match = self.svcre.match(filename)
            if not match:
                self.logger.error("Failed to match file: %s" % filename)
                continue
            if match.group('name') == entry.get('name'):
                files.append(filename)
        if entry.get('status') == 'off':
            if files:
                entry.set('current_status', 'on')
                return False
            else:
                return True
        elif files:
            if start_sequence:
                for filename in files:
                    match = self.svcre.match(filename)
                    file_sequence = int(match.group('sequence'))
                    if ((match.group('action') == 'S' and
                         file_sequence != start_sequence) or
                        (match.group('action') == 'K' and
                         file_sequence != kill_sequence)):
                        return False
            return True
        else:
            entry.set('current_status', 'off')
            return False

    def InstallService(self, entry):
        """Install Service for entry."""
        self.logger.info("Installing Service %s" % (entry.get('name')))
        try:
            os.stat('/etc/init.d/%s' % entry.get('name'))
        except OSError:
            self.logger.debug("Init script for service %s does not exist" %
                              entry.get('name'))
            return False

        if entry.get('status') == 'off':
            self.cmd.run("/usr/sbin/invoke-rc.d %s stop" % (entry.get('name')))
            return self.cmd.run("/usr/sbin/update-rc.d -f %s remove" %
                                entry.get('name')).success
        else:
            command = "/usr/sbin/update-rc.d %s defaults" % (entry.get('name'))
            if entry.get('sequence'):
                if not self.cmd.run("/usr/sbin/update-rc.d -f %s remove" %
                                    entry.get('name')).success:
                    return False
                start_sequence = int(entry.get('sequence'))
                kill_sequence = 100 - start_sequence
                command = "%s %d %d" % (command, start_sequence, kill_sequence)
            return self.cmd.run(command).success

    def FindExtra(self):
        """Find Extra Debian Service entries."""
        specified = [entry.get('name') for entry in self.getSupportedEntries()]
        extra = set()
        for fname in glob.glob("/etc/rc[12345].d/S*"):
            name = self.svcre.match(fname).group('name')
            if name not in specified:
                extra.add(name)
        return [Bcfg2.Client.XML.Element('Service', name=name, type='deb')
                for name in list(extra)]

    def Remove(self, _):
        """Remove extra service entries."""
        # Extra service removal is nonsensical
        # Extra services need to be reflected in the config
        return

    def get_svc_command(self, service, action):
        return '/usr/sbin/invoke-rc.d %s %s' % (service.get('name'), action)
