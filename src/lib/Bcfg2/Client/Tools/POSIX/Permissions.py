""" Handle <Path type='permissions' ...> entries """

from Bcfg2.Client.Tools.POSIX.base import POSIXTool


class POSIXPermissions(POSIXTool):
    """ Handle <Path type='permissions' ...> entries """
    __req__ = ['name', 'mode', 'owner', 'group']
