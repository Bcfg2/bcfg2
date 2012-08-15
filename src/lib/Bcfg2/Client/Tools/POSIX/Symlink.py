import os
import sys
from base import POSIXTool

class POSIXSymlink(POSIXTool):
    __req__ = ['name', 'to']

    def verify(self, entry, modlist):
        rv = True

        try:
            sloc = os.readlink(entry.get('name'))
            if sloc != entry.get('to'):
                entry.set('current_to', sloc)
                msg = ("Symlink %s points to %s, should be %s" %
                       (entry.get('name'), sloc, entry.get('to')))
                self.logger.debug("POSIX: " + msg)
                entry.set('qtext', "\n".join([entry.get('qtext', ''), msg]))
                rv = False
        except OSError:
            self.logger.debug("POSIX: %s %s does not exist" %
                              (entry.tag, entry.get("name")))
            entry.set('current_exists', 'false')
            return False

        return POSIXTool.verify(self, entry, modlist) and rv
        
    def install(self, entry):
        ondisk = self._exists(entry, remove=True)
        if ondisk:
            self.logger.info("POSIX: Symlink %s cleanup failed" %
                             entry.get('name'))
        try:
            os.symlink(entry.get('to'), entry.get('name'))
            rv = True
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("POSIX: Failed to create symlink %s to %s: %s" %
                              (entry.get('name'), entry.get('to'), err))
            rv = False
        return POSIXTool.install(self, entry) and rv

