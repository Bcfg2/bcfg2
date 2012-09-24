""" Handle <Path type='nonexistent' ...> entries """

import os
import sys
import shutil
from Bcfg2.Client.Tools.POSIX.base import POSIXTool


class POSIXNonexistent(POSIXTool):
    """ Handle <Path type='nonexistent' ...> entries """
    __req__ = ['name']

    def verify(self, entry, _):
        if os.path.lexists(entry.get('name')):
            self.logger.debug("POSIX: %s exists but should not" %
                              entry.get("name"))
            return False
        return True

    def install(self, entry):
        ename = entry.get('name')
        if entry.get('recursive', '').lower() == 'true':
            # ensure that configuration spec is consistent first
            for struct in self.config.getchildren():
                for entry in struct.getchildren():
                    if (entry.tag == 'Path' and
                        entry.get('type') != 'nonexistent' and
                        entry.get('name').startswith(ename)):
                        self.logger.error('POSIX: Not removing %s. One or '
                                          'more files in this directory are '
                                          'specified in your configuration.' %
                                          ename)
                        return False
            remove = shutil.rmtree
        elif os.path.isdir(ename):
            remove = os.rmdir
        else:
            remove = os.remove
        try:
            remove(ename)
            return True
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error('POSIX: Failed to remove %s: %s' % (ename, err))
            return False
