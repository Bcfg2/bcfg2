import os
import sys
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenshiGenerator import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import *

from TestServer.TestPlugins.TestCfg.TestCfgGenshiGenerator import \
    TestCfgGenshiGenerator


class TestCfgEncryptedGenshiGenerator(TestCfgGenshiGenerator):
    test_obj = CfgEncryptedGenshiGenerator

    @skipUnless(HAS_CRYPTO, "Encryption libraries not found, skipping")
    def setUp(self):
        TestCfgGenshiGenerator.setUp(self)
