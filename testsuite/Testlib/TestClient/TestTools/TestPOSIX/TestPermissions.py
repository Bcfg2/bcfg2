import os
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Permissions import *
from .Test__init import get_posix_object
from .Testbase import TestPOSIXTool
from .....common import *

class TestPOSIXPermissions(TestPOSIXTool):
    test_obj = POSIXPermissions
