import os
import sys
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedCheetahGenerator import *

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
    from TestServer.TestPlugins.TestCfg.TestCfgCheetahGenerator import \
        TestCfgCheetahGenerator
    from Bcfg2.Server.Plugins.Cfg.CfgCheetahGenerator import HAS_CHEETAH
except ImportError:
    TestCfgCheetahGenerator = object
    HAS_CHEETAH = False

try:
    from TestServer.TestPlugins.TestCfg.TestCfgEncryptedGenerator import \
        TestCfgEncryptedGenerator
    from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator import HAS_CRYPTO
except ImportError:
    TestCfgEncryptedGenerator = object
    HAS_CRYPTO = False


if can_skip or (HAS_CRYPTO and HAS_CHEETAH):
    class TestCfgEncryptedCheetahGenerator(TestCfgCheetahGenerator,
                                           TestCfgEncryptedGenerator):
        test_obj = CfgEncryptedCheetahGenerator

        @skipUnless(HAS_CRYPTO, "Encryption libraries not found, skipping")
        @skipUnless(HAS_CHEETAH, "Cheetah libraries not found, skipping")
        def setUp(self):
            pass

        def test_handle_event(self):
            TestCfgEncryptedGenerator.test_handle_event(self)

        def test_get_data(self):
            TestCfgCheetahGenerator.test_get_data(self)
