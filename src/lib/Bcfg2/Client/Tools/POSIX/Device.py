""" Handle <Path type='nonexistent' ...> entries """

import os
import sys
from Bcfg2.Client.Tools.POSIX.base import POSIXTool, device_map


class POSIXDevice(POSIXTool):
    """ Handle <Path type='nonexistent' ...> entries """
    __req__ = ['name', 'dev_type', 'mode', 'owner', 'group']

    def fully_specified(self, entry):
        if entry.get('dev_type') in ['block', 'char']:
            # check if major/minor are properly specified
            if (entry.get('major') is None or
                entry.get('minor') is None):
                return False
        return True

    def verify(self, entry, modlist):
        """Verify device entry."""
        ondisk = self._exists(entry)
        if not ondisk:
            return False

        # attempt to verify device properties as specified in config
        rv = True
        dev_type = entry.get('dev_type')
        if dev_type in ['block', 'char']:
            major = int(entry.get('major'))
            minor = int(entry.get('minor'))
            if major != os.major(ondisk.st_rdev):
                msg = ("Major number for device %s is incorrect. "
                       "Current major is %s but should be %s" %
                       (entry.get("name"), os.major(ondisk.st_rdev), major))
                self.logger.debug('POSIX: ' + msg)
                entry.set('qtext', entry.get('qtext', '') + "\n" + msg)
                rv = False

            if minor != os.minor(ondisk.st_rdev):
                msg = ("Minor number for device %s is incorrect. "
                       "Current minor is %s but should be %s" %
                       (entry.get("name"), os.minor(ondisk.st_rdev), minor))
                self.logger.debug('POSIX: ' + msg)
                entry.set('qtext', entry.get('qtext', '') + "\n" + msg)
                rv = False
        return POSIXTool.verify(self, entry, modlist) and rv

    def install(self, entry):
        if not self._exists(entry, remove=True):
            try:
                dev_type = entry.get('dev_type')
                mode = device_map[dev_type] | int(entry.get('mode'), 8)
                if dev_type in ['block', 'char']:
                    major = int(entry.get('major'))
                    minor = int(entry.get('minor'))
                    device = os.makedev(major, minor)
                    os.mknod(entry.get('name'), mode, device)
                else:
                    os.mknod(entry.get('name'), mode)
            except (KeyError, OSError, ValueError):
                err = sys.exc_info()[1]
                self.logger.error('POSIX: Failed to install %s: %s' %
                                  (entry.get('name'), err))
                return False
        return POSIXTool.install(self, entry)
