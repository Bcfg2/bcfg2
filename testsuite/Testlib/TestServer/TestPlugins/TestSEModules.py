import os
import sys
import lxml.etree
import Bcfg2.Server.Plugin
from Bcfg2.Bcfg2Py3k import b64encode
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.SEModules import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import XI_NAMESPACE, XI, inPy3k, call, builtins, u, can_skip, \
    skip, skipIf, skipUnless, Bcfg2TestCase, DBModelTestCase, syncdb, \
    patchIf, datastore
from TestPlugin import TestSpecificData, TestGroupSpool

class TestSEModuleData(TestSpecificData):
    test_obj = SEModuleData
    path = os.path.join(datastore, "SEModules", "test.pp", "test.pp")

    def test_bind_entry(self):
        data = self.get_obj()
        data.data = "test"
        entry = lxml.etree.Element("test", name=self.path)
        data.bind_entry(entry, Mock())
        self.assertEqual(entry.get("name"), self.path)
        self.assertEqual(entry.get("encoding"), "base64")
        self.assertEqual(entry.text, b64encode(data.data))


class TestSEModules(TestGroupSpool):
    test_obj = SEModules

    def test__get_module_name(self):
        modules = self.get_obj()
        for mname in ["foo", "foo.pp"]:
            entry = lxml.etree.Element("SELinux", type="module", name=mname)
            self.assertEqual(modules._get_module_name(entry), "/foo.pp")

    @patch("Bcfg2.Server.Plugins.SEModules.SEModules._get_module_name")
    def test_HandlesEntry(self, mock_get_name):
        modules = self.get_obj()
        modules.Entries['SELinux']['/foo.pp'] = Mock()
        modules.Entries['SELinux']['/bar.pp'] = Mock()
        for el in [lxml.etree.Element("Path", name="/foo.pp"),
                   lxml.etree.Element("SELinux", type="fcontext",
                                      name="/foo.pp"),
                   lxml.etree.Element("SELinux", type="module",
                                      name="/baz.pp")]:
            mock_get_name.return_value = el.get("name")
            self.assertFalse(modules.HandlesEntry(el, Mock()))
            mock_get_name.assert_called_with(el)

        for el in [lxml.etree.Element("SELinux", type="module",
                                      name="/foo.pp"),
                   lxml.etree.Element("SELinux", type="module",
                                      name="/bar.pp")]:
            mock_get_name.return_value = el.get("name")
            self.assertTrue(modules.HandlesEntry(el, Mock()),
                            msg="SEModules fails to handle %s" % el.get("name"))
            mock_get_name.assert_called_with(el)

        TestGroupSpool.test_HandlesEntry(self)

    @patch("Bcfg2.Server.Plugins.SEModules.SEModules._get_module_name")
    def test_HandlesEntry(self, mock_get_name):
        modules = self.get_obj()
        handler = Mock()
        modules.Entries['SELinux']['/foo.pp'] = handler
        mock_get_name.return_value = "/foo.pp"
        
        entry = lxml.etree.Element("SELinux", type="module", name="foo")
        metadata = Mock()
        self.assertEqual(modules.HandleEntry(entry, metadata),
                         handler.return_value)
        mock_get_name.assert_called_with(entry)
        self.assertEqual(entry.get("name"), mock_get_name.return_value)
        handler.assert_called_with(entry, metadata)

        TestGroupSpool.test_HandlesEntry(self)

    def test_add_entry(self):
        @patch("%s.%s.event_path" %
               (self.test_obj.__module__, self.test_obj.__name__))
        @patch("%s.%s.add_entry" % (self.test_obj.__base__.__module__,
                                    self.test_obj.__base__.__name__))
        def inner(mock_add_entry, mock_event_path):
            modules = self.get_obj()

            evt = Mock()
            evt.filename = "test.pp.G10_foo"

            mock_event_path.return_value = os.path.join(datastore,
                                                        self.test_obj.__name__,
                                                        "test.pp",
                                                        "test.pp.G10_foo")
            modules.add_entry(evt)
            self.assertEqual(modules.filename_pattern, "test.pp")
            mock_add_entry.assert_called_with(modules, evt)
            mock_event_path.assert_called_with(evt)

        inner()
        TestGroupSpool.test_add_entry(self)
