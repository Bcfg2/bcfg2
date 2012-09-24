""" Handle <Path type="symlink" ...> entries """

import os
from Bcfg2.Client.Tools.POSIX.base import POSIXLinkTool


class POSIXSymlink(POSIXLinkTool):
    """ Handle <Path type="symlink" ...> entries """
    __linktype__ = "symlink"

    def _verify(self, entry):
        sloc = os.readlink(entry.get('name'))
        if sloc != entry.get('to'):
            entry.set('current_to', sloc)
            return False
        return True

    def _link(self, entry):
        return os.symlink(entry.get('to'), entry.get('name'))
