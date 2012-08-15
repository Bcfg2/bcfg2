import os
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Permissions import *
from Test__init import get_posix_object

def call(*args, **kwargs):
    """ the Mock call object is a fairly recent addition, but it's
    very very useful, so we create our own function to create Mock
    calls """
    return (args, kwargs)

def get_permissions_object(posix=None):
    if posix is None:
        posix = get_posix_object()
    return POSIXPermissions(posix.logger, posix.setup, posix.config)

class TestPOSIXPermissions(unittest.TestCase):
    # nothing to test!
    pass
