import os
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Permissions import *
from Test__init import get_posix_object
from .....common import *

def get_permissions_object(posix=None):
    if posix is None:
        posix = get_posix_object()
    return POSIXPermissions(posix.logger, posix.setup, posix.config)

class TestPOSIXPermissions(Bcfg2TestCase):
    # nothing to test!
    pass
