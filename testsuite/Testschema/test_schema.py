import os
import sys
import glob
import lxml.etree
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


XS = "http://www.w3.org/2001/XMLSchema"
XS_NS = "{%s}" % XS
NSMAP = dict(xs=XS)


class TestSchemas(Bcfg2TestCase):
    schema_url = "http://www.w3.org/2001/XMLSchema.xsd"

    @skipUnless(HAS_XMLLINT, "xmllint not installed")
    def test_valid(self):
        schemas = [s for s in glob.glob(os.path.join(srcpath, '*.xsd'))]
        xmllint = Popen(['xmllint', '--xinclude', '--noout', '--schema',
                         self.schema_url] + schemas,
                        stdout=PIPE, stderr=STDOUT)
        print(xmllint.communicate()[0].decode())
        self.assertEqual(xmllint.wait(), 0)

    def test_duplicates(self):
        entities = dict()
        for root, _, files in os.walk(srcpath):
            for fname in files:
                if not fname.endswith(".xsd"):
                    continue
                path = os.path.join(root, fname)
                relpath = path[len(srcpath):].strip("/")
                schema = lxml.etree.parse(path).getroot()
                ns = schema.get("targetNamespace")
                if ns not in entities:
                    entities[ns] = dict(group=dict(),
                                        attributeGroup=dict(),
                                        simpleType=dict(),
                                        complexType=dict())
                for entity in schema.xpath("//xs:*[@name]", namespaces=NSMAP):
                    tag = entity.tag[len(XS_NS):]
                    if tag not in entities[ns]:
                        continue
                    name = entity.get("name")
                    if name in entities[ns][tag]:
                        self.assertNotIn(name, entities[ns][tag],
                                         "Duplicate %s %s (in %s and %s)" %
                                         (tag, name, fname,
                                          entities[ns][tag][name]))
                    entities[ns][tag][name] = fname
