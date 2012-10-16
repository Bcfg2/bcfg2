import os
import re
import sys
import glob
from subprocess import Popen, PIPE, STDOUT

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
_path = os.path.dirname(__file__)
while _path != '/':
    if os.path.basename(_path).lower().startswith("test"):
        sys.path.append(_path)
    if os.path.basename(_path) == "testsuite":
        break
    _path = os.path.dirname(_path)
from common import *

# path to Bcfg2 schema directory
srcpath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                       "schemas"))

# test for xmllint existence
try:
    Popen(['xmllint'], stdout=PIPE, stderr=STDOUT).wait()
    HAS_XMLLINT = True
except OSError:
    HAS_XMLLINT = False


class TestSchemas(Bcfg2TestCase):
    schema_url = "http://www.w3.org/2001/XMLSchema.xsd"

    @skipUnless(HAS_XMLLINT, "xmllint not installed")
    def test_valid(self):
        schemas = [s for s in glob.glob(os.path.join(srcpath,'*.xsd'))]
        xmllint = Popen(['xmllint', '--xinclude', '--noout', '--schema',
                         self.schema_url] + schemas,
                        stdout=PIPE, stderr=STDOUT)
        print(xmllint.communicate()[0])
        self.assertEqual(xmllint.wait(), 0)
