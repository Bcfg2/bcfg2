import os
import sys
import copy
import lxml.etree
import Bcfg2.Options
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Rules import *
from Bcfg2.Server.Plugin import PluginExecutionError

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
from TestPlugin.Testhelpers import TestPrioDir


class TestRules(TestPrioDir):
    test_obj = Rules

    abstract = dict(
        basic=lxml.etree.Element("Path", name="/etc/basic"),
        unhandled=lxml.etree.Element("Path", name="/etc/unhandled"),
        priority=lxml.etree.Element("Path", name="/etc/priority"),
        content=lxml.etree.Element("Path", name="/etc/text-content"),
        duplicate=lxml.etree.Element("SEBoolean", name="duplicate"),
        group=lxml.etree.Element("SEPort", name="6789/tcp"),
        children=lxml.etree.Element("Path", name="/etc/child-entries"),
        regex=lxml.etree.Element("Package", name="regex"),
        replace_name=lxml.etree.Element("POSIXUser", name="regex"),
        slash=lxml.etree.Element("Path", name="/etc/trailing/slash"),
        no_slash=lxml.etree.Element("Path", name="/etc/no/trailing/slash/"))

    concrete = dict(
        basic=lxml.etree.Element("Path", name="/etc/basic", type="directory",
                                 owner="root", group="root", mode="0600"),
        priority=lxml.etree.Element("Path", name="/etc/priority",
                                    type="directory", owner="root",
                                    group="root", mode="0600"),
        content=lxml.etree.Element("Path", name="/etc/text-content",
                                   type="file", owner="bar", group="bar",
                                   mode="0644"),
        duplicate=lxml.etree.Element("SEBoolean", name="duplicate",
                                     value="on"),
        group=lxml.etree.Element("SEPort", name="6789/tcp",
                                 selinuxtype="bcfg2_server_t"),
        children=lxml.etree.Element("Path", name="/etc/child-entries",
                                    type="directory", owner="root",
                                    group="root", mode="0775"),
        regex=lxml.etree.Element("Package", name="regex", type="yum",
                                 version="any"),
        replace_name=lxml.etree.Element("POSIXUser", name="regex",
                                        home="/foobar%{bar}/regex"),
        slash=lxml.etree.Element("Path", name="/etc/trailing/slash",
                                 type="directory", owner="root", group="root",
                                 mode="0600"),
        no_slash=lxml.etree.Element("Path", name="/etc/no/trailing/slash/",
                                    type="directory", owner="root",
                                    group="root", mode="0600"))

    concrete['content'].text = "Text content"
    lxml.etree.SubElement(concrete['children'],
                          "ACL", type="default", scope="user", user="foouser",
                          perms="rw")
    lxml.etree.SubElement(concrete['children'],
                          "ACL", type="default", scope="group", group="users",
                          perms="rx")

    in_file = copy.deepcopy(concrete)
    in_file['regex'].set("name", ".*")
    in_file['replace_name'].set("home", "/foobar%{bar}/%{name}")
    in_file['replace_name'].set("name", ".*")
    in_file['slash'].set("name", "/etc/trailing/slash/")
    in_file['no_slash'].set("name", "/etc/no/trailing/slash")

    rules1 = lxml.etree.Element("Rules", priority="10")
    rules1.append(in_file['basic'])
    lxml.etree.SubElement(rules1, "Path", name="/etc/priority",
                          type="directory", owner="foo", group="foo",
                          mode="0644")
    foogroup = lxml.etree.SubElement(rules1, "Group", name="foogroup")
    foogroup.append(in_file['group'])
    rules1.append(in_file['content'])
    rules1.append(copy.copy(in_file['duplicate']))

    rules2 = lxml.etree.Element("Rules", priority="20")
    rules2.append(in_file['priority'])
    rules2.append(in_file['children'])
    rules2.append(in_file['no_slash'])

    rules3 = lxml.etree.Element("Rules", priority="10")
    rules3.append(in_file['duplicate'])
    rules3.append(in_file['regex'])
    rules3.append(in_file['replace_name'])
    rules3.append(in_file['slash'])

    rules = {"rules1.xml": rules1, "rules2.xml": rules2, "rules3.xml": rules3}

    def setUp(self):
        TestPrioDir.setUp(self)
        set_setup_default("lax_decryption", True)
        set_setup_default("rules_regex", False)
        set_setup_default("rules_replace_name", False)

    def get_child(self, name):
        """ Turn one of the XML documents in `rules` into a child
        object """
        filename = os.path.join(datastore, self.test_obj.name, name)
        rv = self.test_obj.__child__(filename)
        rv.data = lxml.etree.tostring(self.rules[name])
        rv.Index()
        return rv

    def get_obj(self, core=None):
        r = TestPrioDir.get_obj(self, core=core)
        r.entries = dict([(n, self.get_child(n)) for n in self.rules.keys()])
        return r

    def _do_test(self, name, groups=None):
        if groups is None:
            groups = []
        r = self.get_obj()
        metadata = Mock(groups=groups)
        entry = copy.deepcopy(self.abstract[name])
        self.assertTrue(r.HandlesEntry(entry, metadata))
        r.HandleEntry(entry, metadata)
        self.assertXMLEqual(entry, self.concrete[name])

    def _do_test_failure(self, name, groups=None, handles=None):
        if groups is None:
            groups = []
        r = self.get_obj()
        metadata = Mock(groups=groups)
        entry = self.abstract[name]
        if handles is not None:
            self.assertEqual(handles, r.HandlesEntry(entry, metadata))
        self.assertRaises(PluginExecutionError,
                          r.HandleEntry, entry, metadata)

    def test_basic(self):
        """ Test basic Rules usage """
        self._do_test('basic')
        self._do_test_failure('unhandled', handles=False)

    def test_priority(self):
        """ Test that Rules respects priority """
        self._do_test('priority')

    def test_duplicate(self):
        """ Test that Rules raises exceptions for duplicate entries """
        self._do_test_failure('duplicate')

    def test_content(self):
        """ Test that Rules copies text content from concrete entries """
        self._do_test('content')

    def test_group(self):
        """ Test that Rules respects <Group/> tags """
        self._do_test('group', groups=['foogroup'])
        self._do_test_failure('group', groups=['bargroup'], handles=False)

    def test_children(self):
        """ Test that Rules copies child elements from concrete entries """
        self._do_test('children')

    def test_regex(self):
        """ Test that Rules handles regular expressions properly """
        Bcfg2.Options.setup.rules_regex = False
        self._do_test_failure('regex', handles=False)
        Bcfg2.Options.setup.rules_regex = True
        self._do_test('regex')
        Bcfg2.Options.setup.rules_regex = False

    def test_replace_name(self):
        """ Test that Rules handles replaces name in attribues with regular expressions """
        Bcfg2.Options.setup.rules_regex = False
        Bcfg2.Options.setup.rules_replace_name = False
        self._do_test_failure('replace_name', handles=False)
        Bcfg2.Options.setup.rules_regex = True
        Bcfg2.Options.setup.rules_replace_name = True
        self._do_test('replace_name')
        Bcfg2.Options.setup.rules_regex = False
        Bcfg2.Options.setup.rules_replace_name = False

    def test_slash(self):
        """ Test that Rules handles trailing slashes on Path entries """
        self._do_test('slash')
        self._do_test('no_slash')
