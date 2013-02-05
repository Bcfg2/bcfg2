import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Bundler import *

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
from TestPlugin import TestStructFile, TestPlugin, TestStructure, \
    TestXMLDirectoryBacked


class TestBundleFile(TestStructFile):
    test_obj = BundleFile
    path = os.path.join(datastore, "test", "test1.xml")

    def test_bundle_name(self):
        cases = [("foo.xml", "foo"),
                 ("foo.bar.xml", "foo.bar"),
                 ("foo-bar-baz.xml", "foo-bar-baz"),
                 ("foo....xml", "foo..."),
                 ("foo.genshi", "foo")]
        bf = self.get_obj()
        for fname, bname in cases:
            bf.name = fname
            self.assertEqual(bf.bundle_name, bname)


class TestBundler(TestPlugin, TestStructure, TestXMLDirectoryBacked):
    test_obj = Bundler

    def get_obj(self, core=None):
        @patch("%s.%s.add_directory_monitor" % (self.test_obj.__module__,
                                                self.test_obj.__name__),
               Mock())
        def inner():
            return TestPlugin.get_obj(self, core=core)
        return inner()

    @patch("Bcfg2.Server.Plugin.XMLDirectoryBacked.HandleEvent")
    def test_HandleEvent(self, mock_HandleEvent):
        b = self.get_obj()
        b.bundles = dict(foo=Mock(), bar=Mock())
        b.entries = {"foo.xml": BundleFile("foo.xml"),
                     "baz.xml": BundleFile("baz.xml")}
        event = Mock()
        b.HandleEvent(event)
        mock_HandleEvent.assert_called_with(b, event)
        self.assertItemsEqual(b.bundles,
                              dict(foo=b.entries['foo.xml'],
                                   baz=b.entries['baz.xml']))

    def test_BuildStructures(self):
        b = self.get_obj()
        b.bundles = dict(foo=Mock(), bar=Mock(), baz=Mock())
        metadata = Mock()
        metadata.bundles = ["foo", "baz"]

        self.assertItemsEqual(b.BuildStructures(metadata),
                              [b.bundles[n].XMLMatch.return_value
                               for n in metadata.bundles])
        for bname in metadata.bundles:
            b.bundles[bname].XMLMatch.assert_called_with(metadata)
