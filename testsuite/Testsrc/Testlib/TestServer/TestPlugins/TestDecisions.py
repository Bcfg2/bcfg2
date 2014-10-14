import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Decisions import *

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
from TestPlugin import TestStructFile, TestPlugin, TestDecision


class TestDecisionFile(TestStructFile):
    test_obj = DecisionFile

    def test_get_decisions(self):
        df = self.get_obj()
        metadata = Mock()

        df.xdata = None
        self.assertItemsEqual(df.get_decisions(metadata), [])

        df.xdata = lxml.etree.Element("Decisions")
        df.XMLMatch = Mock()
        df.XMLMatch.return_value = lxml.etree.Element("Decisions")
        lxml.etree.SubElement(df.XMLMatch.return_value,
                              "Decision", type="Service", name='*')
        lxml.etree.SubElement(df.XMLMatch.return_value,
                              "Decision", type="Path",
                              name='/etc/apt/apt.conf')

        self.assertItemsEqual(df.get_decisions(metadata),
                              [("Service", '*'),
                               ("Path", '/etc/apt/apt.conf')])
        df.XMLMatch.assert_called_with(metadata)


class TestDecisions(TestPlugin, TestDecision):
    test_obj = Decisions

    def test_GetDecisions(self):
        d = self.get_obj()
        d.whitelist = Mock()
        d.blacklist = Mock()
        metadata = Mock()

        self.assertEqual(d.GetDecisions(metadata, "whitelist"),
                         d.whitelist.get_decisions.return_value)
        d.whitelist.get_decisions.assert_called_with(metadata)

        self.assertEqual(d.GetDecisions(metadata, "blacklist"),
                         d.blacklist.get_decisions.return_value)
        d.blacklist.get_decisions.assert_called_with(metadata)
