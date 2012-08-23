import os
import sys
from base import POSIXTool

class POSIXPermissions(POSIXTool):
    __req__ = ['name', 'perms', 'owner', 'group']
    
