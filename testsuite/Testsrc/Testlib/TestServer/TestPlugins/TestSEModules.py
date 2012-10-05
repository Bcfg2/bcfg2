import os
import sys
import lxml.etree
from Bcfg2.Compat import b64encode
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
from common import *
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
            self.assertEqual(modules._get_module_name(entry), "foo")

    def test__get_module_filename(self):
        modules = self.get_obj()
        for mname in ["foo", "foo.pp"]:
            entry = lxml.etree.Element("SELinux", type="module", name=mname)
            self.assertEqual(modules._get_module_filename(entry), "/foo.pp")

    def test_HandlesEntry(self):
        modules = self.get_obj()
        modules._get_module_filename = Mock()
        modules.Entries['SELinux']['/foo.pp'] = Mock()
        modules.Entries['SELinux']['/bar.pp'] = Mock()
        for el in [lxml.etree.Element("Path", name="foo.pp"),
                   lxml.etree.Element("SELinux", type="fcontext",
                                      name="foo.pp"),
                   lxml.etree.Element("SELinux", type="module",
                                      name="baz.pp")]:
            modules._get_module_filename.return_value = "/" + el.get("name")
            self.assertFalse(modules.HandlesEntry(el, Mock()))
            if el.get("type") == "module":
                modules._get_module_filename.assert_called_with(el)

        for el in [lxml.etree.Element("SELinux", type="module",
                                      name="foo.pp"),
                   lxml.etree.Element("SELinux", type="module",
                                      name="bar.pp")]:
            modules._get_module_filename.return_value = "/" + el.get("name")
            self.assertTrue(modules.HandlesEntry(el, Mock()),
                            msg="SEModules fails to handle %s" % el.get("name"))
            modules._get_module_filename.assert_called_with(el)

        TestGroupSpool.test_HandlesEntry(self)

    def test_HandleEntry(self):
        modules = self.get_obj()
        modules._get_module_name = Mock()
        handler = Mock()
        modules.Entries['SELinux']['/foo.pp'] = handler
        modules._get_module_name.return_value = "foo"

        entry = lxml.etree.Element("SELinux", type="module", name="foo")
        metadata = Mock()
        self.assertEqual(modules.HandleEntry(entry, metadata),
                         handler.return_value)
        modules._get_module_name.assert_called_with(entry)
        self.assertEqual(entry.get("name"),
                         modules._get_module_name.return_value)
        handler.assert_called_with(entry, metadata)

        TestGroupSpool.test_HandlesEntry(self)

    def test_add_entry(self):
        @patch("%s.%s.add_entry" % (self.test_obj.__base__.__module__,
                                    self.test_obj.__base__.__name__))
        def inner(mock_add_entry):
            modules = self.get_obj()
            modules.event_path = Mock()

            evt = Mock()
            evt.filename = "test.pp.G10_foo"

            modules.event_path.return_value = \
                os.path.join(datastore,
                             self.test_obj.__name__,
                             "test.pp",
                             "test.pp.G10_foo")
            modules.add_entry(evt)
            self.assertEqual(modules.filename_pattern, "test.pp")
            mock_add_entry.assert_called_with(modules, evt)
            modules.event_path.assert_called_with(evt)

        inner()
        TestGroupSpool.test_add_entry(self)
