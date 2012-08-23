import os
import sys
try:
    from base import POSIXTool
except ImportError:
    # py3k, incompatible syntax with py2.4
    exec("from .base import POSIXTool")

class POSIXPermissions(POSIXTool):
    __req__ = ['name', 'perms', 'owner', 'group']
    
