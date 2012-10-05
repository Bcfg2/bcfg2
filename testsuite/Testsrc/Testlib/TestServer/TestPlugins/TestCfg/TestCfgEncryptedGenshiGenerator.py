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

try:
    from TestServer.TestPlugins.TestCfg.TestCfgGenshiGenerator import \
        TestCfgGenshiGenerator
    HAS_GENSHI = True
except ImportError:
    TestCfgGenshiGenerator = object
    HAS_GENSHI = False


if can_skip or (HAS_CRYPTO and HAS_GENSHI):
    class TestCfgEncryptedGenshiGenerator(TestCfgGenshiGenerator):
        test_obj = CfgEncryptedGenshiGenerator

        @skipUnless(HAS_CRYPTO, "Encryption libraries not found, skipping")
        @skipUnless(HAS_GENSHI, "Genshi libraries not found, skipping")
        def setUp(self):
            pass
