""" Handle <Path type='nonexistent' ...> entries """

import os
import sys
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
        recursive = entry.get('recursive', '').lower() == 'true'
        if recursive:
            # ensure that configuration spec is consistent first
            for struct in self.config.getchildren():
                for el in struct.getchildren():
                    if (el.tag == 'Path' and
                        el.get('type') != 'nonexistent' and
                        el.get('name').startswith(ename)):
                        self.logger.error('POSIX: Not removing %s. One or '
                                          'more files in this directory are '
                                          'specified in your configuration.' %
                                          ename)
                        return False
        try:
            self._remove(entry, recursive=recursive)
            return True
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error('POSIX: Failed to remove %s: %s' % (ename, err))
            return False
