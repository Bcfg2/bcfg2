import os
import sys
import lxml.etree
import Bcfg2.Server.Plugin
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.GroupPatterns import *

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
from TestPlugin import TestXMLFileBacked, TestPlugin, TestConnector


class TestPatternMap(Bcfg2TestCase):
    def test_ranges(self):
        """ test processing NameRange patterns """
        tests = [("foo[[1-5]]",
                  ["foo1", "foo2", "foo5"],
                  ["foo", "foo0", "foo10"]),
                 ("[[10-99]]foo",
                  ["10foo", "99foo", "25foo"],
                  ["foo", "1foo", "999foo", "110foo"]),
                 ("foo[[1,3,5-10]]bar",
                  ["foo1bar", "foo7bar", "foo10bar"],
                  ["foo2bar", "foobar", "foo3", "5bar"]),
                 ("[[9-15]]foo[[16-20]]",
                  ["9foo18", "13foo17"],
                  ["8foo21", "12foo21", "8foo18", "16foo16",
                   "15foo15", "29foo20", "9foo200", "29foo200"])]

        groups = MagicMock()
        for rng, inc, exc in tests:
            pmap = PatternMap(None, rng, groups)
            for test in inc:
                self.assertEqual(pmap.process(test), groups)
            for test in exc:
                self.assertIsNone(pmap.process(test))

    def test_simple_patterns(self):
        """ test processing NamePatterns without backreferences """
        tests = [("foo.*",
                  ["foo", "foobar", "barfoo", "barfoobar"],
                  ["bar", "fo0"]),
                 ("^[A-z]fooo?$",
                  ["Afoo", "bfooo"],
                  ["foo", "fooo", "AAfoo", "Afoooo"])]

        groups = ["a", "b", "c"]
        for rng, inc, exc in tests:
            pmap = PatternMap(rng, None, groups)
            for test in inc:
                self.assertItemsEqual(pmap.process(test), groups)
            for test in exc:
                self.assertIsNone(pmap.process(test))

    def test_backref_patterns(self):
        """ test NamePatterns with backreferences """
        tests = [("foo(.*)", ['a', 'a$1', '$1a', '$$', '$a', '$1'],
                  {"foo": ['a', 'a', 'a', '$$', '$a', ''],
                   "foooOOo": ['a', 'aoOOo', 'oOOoa', '$$', '$a', 'oOOo'],
                   "barfoo$1": ['a', 'a$1', '$1a', '$$', '$a', '$1']}),
                 ("^([a-z])foo(.+)", ['a', 'a$1', '$1a$2', '$1$$2', '$2'],
                  {"foo": None,
                   "afooa": ['a', 'aa', 'aaa', 'a$a', 'a'],
                   "bfoobar": ['a', 'ab', 'babar', 'b$bar', 'bar']})]

        for rng, groups, cases in tests:
            pmap = PatternMap(rng, None, groups)
            for name, ret in cases.items():
                if ret is None:
                    self.assertIsNone(pmap.process(name))
                else:
                    self.assertItemsEqual(pmap.process(name), ret)


class TestPatternFile(TestXMLFileBacked):
    test_obj = PatternFile
    should_monitor = True

    def get_obj(self, path=None, fam=None, core=None, should_monitor=True):
        if path is None:
            path = self.path
        if fam and not core:
            core = Mock()
            core.fam = fam
        elif not core:
            core = Mock()

        @patchIf(not isinstance(lxml.etree.Element, Mock),
                 "lxml.etree.Element", Mock())
        def inner():
            return self.test_obj(path, core=core)
        return inner()

    @patch("Bcfg2.Server.Plugins.GroupPatterns.PatternMap")
    def test_Index(self, mock_PatternMap):
        TestXMLFileBacked.test_Index(self)
        core = Mock()
        pf = self.get_obj(core=core)

        pf.data = """
<GroupPatterns>
  <GroupPattern>
    <NamePattern>foo.*</NamePattern>
    <Group>test1</Group>
    <Group>test2</Group>
  </GroupPattern>
  <GroupPattern>
    <NameRange>foo[[1-5]]</NameRange>
    <Group>test3</Group>
  </GroupPattern>
</GroupPatterns>"""

        core.metadata_cache_mode = 'aggressive'
        pf.Index()
        core.metadata_cache.expire.assert_called_with()
        self.assertItemsEqual(mock_PatternMap.call_args_list,
                              [call("foo.*", None, ["test1", "test2"]),
                               call(None, "foo[[1-5]]", ["test3"])])

    def test_process_patterns(self):
        pf = self.get_obj()
        pf.patterns = [Mock(), Mock(), Mock()]
        pf.patterns[0].process.return_value = ["a", "b"]
        pf.patterns[1].process.return_value = None
        pf.patterns[2].process.return_value = ["b", "c"]
        self.assertItemsEqual(pf.process_patterns("foo.example.com"),
                              ["a", "b", "b", "c"])
        for pat in pf.patterns:
            pat.process.assert_called_with("foo.example.com")


class TestGroupPatterns(TestPlugin, TestConnector):
    test_obj = GroupPatterns

    def get_obj(self, core=None):
        @patchIf(not isinstance(lxml.etree.Element, Mock),
                 "lxml.etree.Element", Mock())
        def inner():
            return TestPlugin.get_obj(self, core=core)
        return inner()


    def test_get_additional_groups(self):
        gp = self.get_obj()
        gp.config = Mock()
        metadata = Mock()
        self.assertEqual(gp.get_additional_groups(metadata),
                         gp.config.process_patterns.return_value)
        gp.config.process_patterns.assert_called_with(metadata.hostname)
