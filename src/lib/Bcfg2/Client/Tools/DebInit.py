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

    def get_svc_command(self, service, action):
        return '/usr/sbin/invoke-rc.d %s %s' % (service.get('name'), action)

    def verify_bootstatus(self, entry, bootstatus):
        """Verify bootstatus for entry."""
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
        if bootstatus == 'off':
            if files:
                entry.set('current_bootstatus', 'on')
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
            entry.set('current_bootstatus', 'off')
            return False

    def VerifyService(self, entry, _):
        """Verify Service status for entry."""
        entry.set('target_status', entry.get('status'))  # for reporting
        bootstatus = self.get_bootstatus(entry)
        if bootstatus is None:
            return True
        current_bootstatus = self.verify_bootstatus(entry, bootstatus)

        if entry.get('status') == 'ignore':
            # 'ignore' should verify
            current_svcstatus = True
            svcstatus = True
        else:
            svcstatus = self.check_service(entry)
            if entry.get('status') == 'on':
                if svcstatus:
                    current_svcstatus = True
                else:
                    current_svcstatus = False
            elif entry.get('status') == 'off':
                if svcstatus:
                    current_svcstatus = False
                else:
                    current_svcstatus = True

        if svcstatus:
            entry.set('current_status', 'on')
        else:
            entry.set('current_status', 'off')

        return current_bootstatus and current_svcstatus

    def InstallService(self, entry):
        """Install Service entry."""
        self.logger.info("Installing Service %s" % (entry.get('name')))
        bootstatus = entry.get('bootstatus')

        # check if init script exists
        try:
            os.stat('/etc/init.d/%s' % entry.get('name'))
        except OSError:
            self.logger.debug("Init script for service %s does not exist" %
                              entry.get('name'))
            return False

        if bootstatus is not None:
            seqcmdrv = True
            if bootstatus == 'on':
                # make sure service is enabled on boot
                bootcmd = '/usr/sbin/update-rc.d %s defaults' % \
                          entry.get('name')
                if entry.get('sequence'):
                    seqcmd = '/usr/sbin/update-rc.d -f %s remove' % \
                             entry.get('name')
                    seqcmdrv = self.cmd.run(seqcmd)
                    start_sequence = int(entry.get('sequence'))
                    kill_sequence = 100 - start_sequence
                    bootcmd = '%s %d %d' % (bootcmd, start_sequence,
                                            kill_sequence)
            elif bootstatus == 'off':
                # make sure service is disabled on boot
                bootcmd = '/usr/sbin/update-rc.d -f %s remove' % \
                          entry.get('name')
            bootcmdrv = self.cmd.run(bootcmd)
            if self.setup['servicemode'] == 'disabled':
                # 'disabled' means we don't attempt to modify running svcs
                return bootcmdrv and seqcmdrv
            buildmode = self.setup['servicemode'] == 'build'
            if (entry.get('status') == 'on' and not buildmode) and \
               entry.get('current_status') == 'off':
                svccmdrv = self.start_service(entry)
            elif (entry.get('status') == 'off' or buildmode) and \
                    entry.get('current_status') == 'on':
                svccmdrv = self.stop_service(entry)
            else:
                svccmdrv = True  # ignore status attribute
            return bootcmdrv and svccmdrv and seqcmdrv
        else:
            # when bootstatus is 'None', status == 'ignore'
            return True

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
