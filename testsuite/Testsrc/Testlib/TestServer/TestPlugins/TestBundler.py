import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Bundler import *
from Bcfg2.version import Bcfg2VersionInfo

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
        b.bundles = dict(error=Mock(), skip=Mock(), xinclude=Mock(),
                         has_dep=Mock(), is_dep=Mock(), indep=Mock())
        expected = dict()

        b.bundles['error'].XMLMatch.side_effect = TemplateError(None)

        xinclude = lxml.etree.Element("Bundle")
        lxml.etree.SubElement(lxml.etree.SubElement(xinclude, "Bundle"),
                              "Path", name="/test")
        b.bundles['xinclude'].XMLMatch.return_value = xinclude
        expected['xinclude'] = lxml.etree.Element("Bundle", name="xinclude")
        lxml.etree.SubElement(expected['xinclude'], "Path", name="/test")

        has_dep = lxml.etree.Element("Bundle")
        lxml.etree.SubElement(has_dep, "RequiredBundle", name="is_dep")
        lxml.etree.SubElement(has_dep, "RequiredBundle", name="is_mod_dep",
                              inherit_modification="true")
        lxml.etree.SubElement(has_dep, "Package", name="foo")
        b.bundles['has_dep'].XMLMatch.return_value = has_dep
        expected['has_dep'] = lxml.etree.Element("Bundle", name="has_dep")
        lxml.etree.SubElement(expected['has_dep'], "Package", name="foo")
        lxml.etree.SubElement(expected['has_dep'], "Bundle",
                              name="is_mod_dep")

        is_dep = lxml.etree.Element("Bundle")
        lxml.etree.SubElement(is_dep, "Package", name="bar")
        b.bundles['is_dep'].XMLMatch.return_value = is_dep
        expected['is_dep'] = lxml.etree.Element("Bundle", name="is_dep")
        lxml.etree.SubElement(expected['is_dep'], "Package", name="bar")

        indep = lxml.etree.Element("Bundle", independent="true")
        lxml.etree.SubElement(indep, "Service", name="baz")
        b.bundles['indep'].XMLMatch.return_value = indep
        expected['indep'] = lxml.etree.Element("Independent", name="indep")
        lxml.etree.SubElement(expected['indep'], "Service", name="baz")

        metadata = Mock()
        metadata.bundles = set(["error", "xinclude", "has_dep", "indep"])
        metadata.version_info = Bcfg2VersionInfo('1.4.0')

        rv = b.BuildStructures(metadata)
        self.assertEqual(len(rv), 4)
        for bundle in rv:
            name = bundle.get("name")
            self.assertIsNotNone(name,
                                "Bundle %s was not built" % name)
            self.assertIn(name, expected,
                          "Unexpected bundle %s was built" % name)
            self.assertXMLEqual(bundle, expected[name],
                                "Bundle %s was not built correctly" % name)
            b.bundles[name].XMLMatch.assert_called_with(metadata)

        b.bundles['error'].XMLMatch.assert_called_with(metadata)
        self.assertFalse(b.bundles['skip'].XMLMatch.called)

    def test_BuildStructuresOldClient(self):
        b = self.get_obj()
        b.bundles = dict(has_dep=Mock())
        expected = dict()

        has_dep = lxml.etree.Element("Bundle")
        lxml.etree.SubElement(has_dep, "RequiredBundle", name="is_dep")
        lxml.etree.SubElement(has_dep, "RequiredBundle", name="is_mod_dep",
                              inherit_modification="true")
        lxml.etree.SubElement(has_dep, "Package", name="foo")
        b.bundles['has_dep'].XMLMatch.return_value = has_dep
        expected['has_dep'] = lxml.etree.Element("Bundle", name="has_dep")
        lxml.etree.SubElement(expected['has_dep'], "Package", name="foo")

        metadata = Mock()
        metadata.bundles = set(["has_dep"])
        metadata.version_info = Bcfg2VersionInfo('1.3.0')

        rv = b.BuildStructures(metadata)
        self.assertEqual(len(rv), len(metadata.bundles))
        for bundle in rv:
            name = bundle.get("name")
            self.assertIsNotNone(name,
                                "Bundle %s was not built" % name)
            self.assertIn(name, expected,
                          "Unexpected bundle %s was built" % name)
            self.assertXMLEqual(bundle, expected[name],
                                "Bundle %s was not built correctly" % name)
            b.bundles[name].XMLMatch.assert_called_with(metadata)
