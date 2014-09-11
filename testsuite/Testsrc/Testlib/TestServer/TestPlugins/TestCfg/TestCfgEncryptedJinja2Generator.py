import os
import sys
from Bcfg2.Server.Plugins.Cfg.CfgEncryptedJinja2Generator import *

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
    from TestServer.TestPlugins.TestCfg.TestCfgJinja2Generator import \
        TestCfgJinja2Generator
    from Bcfg2.Server.Plugins.Cfg.CfgJinja2Generator import HAS_JINJA2
except ImportError:
    TestCfgJinja2Generator = object
    HAS_JINJA2 = False

try:
    from TestServer.TestPlugins.TestCfg.TestCfgEncryptedGenerator import \
        TestCfgEncryptedGenerator
    from Bcfg2.Server.Plugins.Cfg.CfgEncryptedGenerator import HAS_CRYPTO
except ImportError:
    TestCfgEncryptedGenerator = object
    HAS_CRYPTO = False


if can_skip or (HAS_CRYPTO and HAS_JINJA2):
    class TestCfgEncryptedJinja2Generator(TestCfgJinja2Generator,
                                           TestCfgEncryptedGenerator):
        test_obj = CfgEncryptedJinja2Generator

        @skipUnless(HAS_CRYPTO, "Encryption libraries not found, skipping")
        @skipUnless(HAS_JINJA2, "Jinja2 libraries not found, skipping")
        def setUp(self):
            pass

        def test_handle_event(self):
            TestCfgEncryptedGenerator.test_handle_event(self)

        def test_get_data(self):
            TestCfgJinja2Generator.test_get_data(self)
