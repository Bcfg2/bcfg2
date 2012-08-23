import os
import sys
try:
    from base import POSIXTool
except ImportError:
    # py3k, incompatible syntax with py2.4
    exec("from .base import POSIXTool")

class POSIXHardlink(POSIXTool):
    __req__ = ['name', 'to']

    def verify(self, entry, modlist):
        rv = True

        try:
            if not os.path.samefile(entry.get('name'), entry.get('to')):
                msg = "Hardlink %s is incorrect" % entry.get('name')
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
            self.logger.info("POSIX: Hardlink %s cleanup failed" %
                             entry.get('name'))
        try:
            os.link(entry.get('to'), entry.get('name'))
            rv = True
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("POSIX: Failed to create hardlink %s to %s: %s" %
                              (entry.get('name'), entry.get('to'), err))
            rv = False
        return POSIXTool.install(self, entry) and rv

