""" Handle <Path type="hardlink" ...> entries """

import os
from Bcfg2.Client.Tools.POSIX.base import POSIXLinkTool


class POSIXHardlink(POSIXLinkTool):
    """ Handle <Path type="hardlink" ...> entries """
    __linktype__ = "hardlink"

    def _verify(self, entry):
        return os.path.samefile(entry.get('name'), entry.get('to'))

    def _link(self, entry):
        ## TODO: set permissions
        return os.link(entry.get('to'), entry.get('name'))
