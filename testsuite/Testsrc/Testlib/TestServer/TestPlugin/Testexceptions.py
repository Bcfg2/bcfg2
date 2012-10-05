import os
import sys
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugin.exceptions import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != '/':
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import *


class TestPluginInitError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestPluginExecutionError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestMetadataConsistencyError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestMetadataRuntimeError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestValidationError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestSpecificityError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass

