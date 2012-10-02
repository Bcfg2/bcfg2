import os
import sys
from Bcfg2.Server.Plugins.Cfg.CfgPlaintextGenerator import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from TestServer.TestPlugins.TestCfg.Test_init import TestCfgGenerator


class TestCfgPlaintextGenerator(TestCfgGenerator):
    test_obj = CfgPlaintextGenerator
