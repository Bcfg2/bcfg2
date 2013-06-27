import os
import sys
import errno
import lxml.etree
import Bcfg2.Options
from Bcfg2.Compat import walk_packages
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg import *
from Bcfg2.Server.Plugin import PluginExecutionError, Specificity

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
from TestPlugin import TestSpecificData, TestEntrySet, TestGroupSpool, \
    TestPullTarget


class TestCfgBaseFileMatcher(TestSpecificData):
    test_obj = CfgBaseFileMatcher
    path = os.path.join(datastore, "test+test.txt")

    def test_get_regex(self):
        if self.test_obj.__basenames__:
            basenames = self.test_obj.__basenames__
        else:
            basenames = [os.path.basename(self.path)]
        if self.test_obj.__extensions__:
            extensions = self.test_obj.__extensions__
        else:
            extensions = ['']
        for extension in extensions:
            regex = self.test_obj.get_regex(basenames)
            for basename in basenames:
                def test_match(spec):
                    mstr = basename
                    if spec:
                        mstr += "." + spec
                    if extension:
                        mstr += "." + extension
                    return regex.match(mstr)

                self.assertTrue(test_match(''))
                self.assertFalse(regex.match("bogus"))
                if self.test_obj.__specific__:
                    if extension:
                        self.assertFalse(regex.match("bogus." + extension))
                    self.assertTrue(test_match("G20_foo"))
                    self.assertTrue(test_match("G1_foo"))
                    self.assertTrue(test_match("G32768_foo"))
                    # a group named '_'
                    self.assertTrue(test_match("G10__"))
                    self.assertTrue(test_match("H_hostname"))
                    self.assertTrue(test_match("H_fqdn.subdomain.example.com"))
                    self.assertTrue(test_match("G20_group_with_underscores"))

                    self.assertFalse(test_match("G20_group with spaces"))
                    self.assertFalse(test_match("G_foo"))
                    self.assertFalse(test_match("G_"))
                    self.assertFalse(test_match("G20_"))
                    self.assertFalse(test_match("H_"))
                else:
                    self.assertFalse(test_match("G20_foo"))
                    self.assertFalse(test_match("H_hostname"))

    @patch("Bcfg2.Server.Plugins.Cfg.CfgBaseFileMatcher.get_regex")
    def test_handles(self, mock_get_regex):
        match = Mock()
        mock_get_regex.return_value = Mock()
        mock_get_regex.return_value.match = match

        evt = Mock()
        evt.filename = "event.txt"

        if self.test_obj.__basenames__:
            match.return_value = False
            self.assertFalse(self.test_obj.handles(evt))
            mock_get_regex.assert_called_with(
                [b for b in self.test_obj.__basenames__])
            print("match calls: %s" % match.call_args_list)
            print("expected: %s" % [call(evt.filename)
                                   for b in self.test_obj.__basenames__])
            match.assert_called_with(evt.filename)

            mock_get_regex.reset_mock()
            match.reset_mock()
            match.return_value = True
            self.assertTrue(self.test_obj.handles(evt))
            match.assert_called_with(evt.filename)
        else:
            match.return_value = False
            self.assertFalse(self.test_obj.handles(evt,
                                         basename=os.path.basename(self.path)))
            mock_get_regex.assert_called_with([os.path.basename(self.path)])
            match.assert_called_with(evt.filename)

            mock_get_regex.reset_mock()
            match.reset_mock()
            match.return_value = True
            self.assertTrue(self.test_obj.handles(evt,
                                        basename=os.path.basename(self.path)))
            mock_get_regex.assert_called_with([os.path.basename(self.path)])
            match.assert_called_with(evt.filename)

    def test_ignore(self):
        evt = Mock()
        evt.filename = "event.txt"

        if not self.test_obj.__ignore__:
            self.assertFalse(self.test_obj.ignore(evt))
        else:
            self.assertFalse(self.test_obj.ignore(evt))
            for extension in self.test_obj.__ignore__:
                for name in ["event.txt", "....", extension, "." + extension]:
                    for filler in ['', '.blah', '......', '.' + extension]:
                        evt.filename = name + filler + '.' + extension
                        self.assertTrue(self.test_obj.ignore(evt))


class TestCfgGenerator(TestCfgBaseFileMatcher):
    test_obj = CfgGenerator

    def test_get_data(self):
        cg = self.get_obj()
        cg.data = "foo bar baz"
        self.assertEqual(cg.data, cg.get_data(Mock(), Mock()))


class TestCfgFilter(TestCfgBaseFileMatcher):
    test_obj = CfgFilter

    def test_modify_data(self):
        cf = self.get_obj()
        self.assertRaises(NotImplementedError,
                          cf.modify_data, Mock(), Mock(), Mock())


class TestCfgInfo(TestCfgBaseFileMatcher):
    test_obj = CfgInfo

    def get_obj(self, name=None):
        if name is None:
            name = self.path
        return self.test_obj(name)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgBaseFileMatcher.__init__")
    def test__init(self, mock__init):
        ci = self.get_obj("test.txt")
        mock__init.assert_called_with(ci, "test.txt", None, None)

    def test_bind_info_to_entry(self):
        ci = self.get_obj()
        self.assertRaises(NotImplementedError,
                          ci.bind_info_to_entry, Mock(), Mock())


class TestCfgVerifier(TestCfgBaseFileMatcher):
    test_obj = CfgVerifier

    def test_verify_entry(self):
        cf = self.get_obj()
        self.assertRaises(NotImplementedError,
                          cf.verify_entry, Mock(), Mock(), Mock())


class TestCfgCreator(TestCfgBaseFileMatcher):
    test_obj = CfgCreator
    path = "/foo/bar/test.txt"

    def get_obj(self, name=None):
        if name is None:
            name = self.path
        return self.test_obj(name)

    def test_create_data(self):
        cc = self.get_obj()
        self.assertRaises(NotImplementedError,
                          cc.create_data, Mock(), Mock())

    def test_get_filename(self):
        cc = self.get_obj()

        # tuples of (args to get_filename(), expected result)
        cases = [(dict(), "/foo/bar/bar"),
                 (dict(prio=50), "/foo/bar/bar"),
                 (dict(ext=".crypt"), "/foo/bar/bar.crypt"),
                 (dict(ext="bar"), "/foo/bar/barbar"),
                 (dict(host="foo.bar.example.com"),
                  "/foo/bar/bar.H_foo.bar.example.com"),
                 (dict(host="foo.bar.example.com", prio=50, ext=".crypt"),
                  "/foo/bar/bar.H_foo.bar.example.com.crypt"),
                 (dict(group="group", prio=1), "/foo/bar/bar.G01_group"),
                 (dict(group="group", prio=50), "/foo/bar/bar.G50_group"),
                 (dict(group="group", prio=50, ext=".crypt"),
                  "/foo/bar/bar.G50_group.crypt")]

        for args, expected in cases:
            self.assertEqual(cc.get_filename(**args), expected)

    @patch("os.makedirs")
    @patch("%s.open" % builtins)
    def test_write_data(self, mock_open, mock_makedirs):
        cc = self.get_obj()
        data = "test\ntest"
        parent = os.path.dirname(self.path)

        def reset():
            mock_open.reset_mock()
            mock_makedirs.reset_mock()

        # test writing file
        reset()
        spec = dict(group="foogroup", prio=9)
        cc.write_data(data, **spec)
        mock_makedirs.assert_called_with(parent)
        mock_open.assert_called_with(cc.get_filename(**spec), "wb")
        mock_open.return_value.write.assert_called_with(data)

        # test already-exists error from makedirs
        reset()
        mock_makedirs.side_effect = OSError(errno.EEXIST, self.path)
        cc.write_data(data)
        mock_makedirs.assert_called_with(parent)
        mock_open.assert_called_with(cc.get_filename(), "wb")
        mock_open.return_value.write.assert_called_with(data)

        # test error from open
        reset()
        mock_open.side_effect = IOError
        self.assertRaises(CfgCreationError, cc.write_data, data)

        # test real error from makedirs
        reset()
        mock_makedirs.side_effect = OSError
        self.assertRaises(CfgCreationError, cc.write_data, data)


class TestCfgDefaultInfo(TestCfgInfo):
    test_obj = CfgDefaultInfo

    def get_obj(self, *_):
        return self.test_obj()

    def test__init(self):
        pass

    def test_handle_event(self):
        # this CfgInfo handler doesn't handle any events -- it's not
        # file-driven, but based on the built-in defaults
        pass

    @patch("Bcfg2.Server.Plugin.default_path_metadata")
    def test_bind_info_to_entry(self, mock_default_path_metadata):
        cdi = self.get_obj()
        entry = lxml.etree.Element("Test", name="test")
        mock_default_path_metadata.return_value = \
            dict(owner="root", mode="0600")
        cdi.bind_info_to_entry(entry, Mock())
        self.assertItemsEqual(entry.attrib,
                              dict(owner="root", mode="0600", name="test"))


class TestCfgEntrySet(TestEntrySet):
    test_obj = CfgEntrySet

    def test__init(self):
        pass

    def test_handlers(self):
        # this is really really difficult to mock out, so we just get
        # a list of handlers and make sure that it roughly matches
        # what's on the filesystem
        expected = []
        for submodule in walk_packages(path=Bcfg2.Server.Plugins.Cfg.__path__,
                                       prefix="Bcfg2.Server.Plugins.Cfg."):
            expected.append(submodule[1].rsplit('.', 1)[-1])
        self.assertItemsEqual(expected, [h.__name__ for h in handlers()])

    @patch("Bcfg2.Server.Plugins.Cfg.handlers")
    def test_handle_event(self, mock_handlers):
        eset = self.get_obj()
        eset.entry_init = Mock()
        mock_handlers.return_value = [Mock(), Mock(), Mock()]
        for hdlr in mock_handlers.return_value:
            hdlr.__name__ = "handler"
        eset.entries = dict()

        def reset():
            eset.entry_init.reset_mock()
            for hdlr in mock_handlers.return_value:
                hdlr.reset_mock()

        # test that a bogus deleted event is discarded
        evt = Mock()
        evt.code2str.return_value = "deleted"
        evt.filename = os.path.join(datastore, "test.txt")
        eset.handle_event(evt)
        self.assertFalse(eset.entry_init.called)
        self.assertItemsEqual(eset.entries, dict())
        for hdlr in mock_handlers.return_value:
            self.assertFalse(hdlr.handles.called)
            self.assertFalse(hdlr.ignore.called)

        # test creation of a new file
        for action in ["exists", "created", "changed"]:
            evt = Mock()
            evt.code2str.return_value = action
            evt.filename = os.path.join(datastore, "test.txt")

            # test with no handler that handles
            for hdlr in mock_handlers.return_value:
                hdlr.handles.return_value = False
                hdlr.ignore.return_value = False

            reset()
            eset.handle_event(evt)
            self.assertFalse(eset.entry_init.called)
            self.assertItemsEqual(eset.entries, dict())
            for hdlr in mock_handlers.return_value:
                hdlr.handles.assert_called_with(evt, basename=eset.path)
                hdlr.ignore.assert_called_with(evt, basename=eset.path)

            # test with a handler that handles the entry
            reset()
            mock_handlers.return_value[-1].handles.return_value = True
            eset.handle_event(evt)
            eset.entry_init.assert_called_with(evt, mock_handlers.return_value[-1])
            for hdlr in mock_handlers.return_value:
                hdlr.handles.assert_called_with(evt, basename=eset.path)
                if not hdlr.return_value:
                    hdlr.ignore.assert_called_with(evt, basename=eset.path)

            # test with a handler that ignores the entry before one
            # that handles it
            reset()
            mock_handlers.return_value[0].ignore.return_value = True
            eset.handle_event(evt)
            self.assertFalse(eset.entry_init.called)
            mock_handlers.return_value[0].handles.assert_called_with(evt,
                                                        basename=eset.path)
            mock_handlers.return_value[0].ignore.assert_called_with(evt,
                                                       basename=eset.path)
            for hdlr in mock_handlers.return_value[1:]:
                self.assertFalse(hdlr.handles.called)
                self.assertFalse(hdlr.ignore.called)

        # test changed event with an entry that already exists
        reset()
        evt = Mock()
        evt.code2str.return_value = "changed"
        evt.filename = os.path.join(datastore, "test.txt")
        eset.entries[evt.filename] = Mock()
        eset.handle_event(evt)
        self.assertFalse(eset.entry_init.called)
        for hdlr in mock_handlers.return_value:
            self.assertFalse(hdlr.handles.called)
            self.assertFalse(hdlr.ignore.called)
        eset.entries[evt.filename].handle_event.assert_called_with(evt)

        # test deleted event with an entry that already exists
        reset()
        evt.code2str.return_value = "deleted"
        eset.handle_event(evt)
        self.assertFalse(eset.entry_init.called)
        for hdlr in mock_handlers.return_value:
            self.assertFalse(hdlr.handles.called)
            self.assertFalse(hdlr.ignore.called)
        self.assertItemsEqual(eset.entries, dict())

    def test_get_matching(self):
        eset = self.get_obj()
        eset.get_handlers = Mock()
        metadata = Mock()
        self.assertEqual(eset.get_matching(metadata),
                         eset.get_handlers.return_value)
        eset.get_handlers.assert_called_with(metadata, CfgGenerator)

    @patch("Bcfg2.Server.Plugin.EntrySet.entry_init")
    def test_entry_init(self, mock_entry_init):
        eset = self.get_obj()
        eset.entries = dict()
        evt = Mock()
        evt.filename = "test.txt"
        handler = Mock()
        handler.__basenames__ = []
        handler.__extensions__ = []
        handler.deprecated = False
        handler.experimental = False
        handler.__specific__ = True

        # test handling an event with the parent entry_init
        eset.entry_init(evt, handler)
        mock_entry_init.assert_called_with(eset, evt, entry_type=handler,
                                           specific=handler.get_regex.return_value)
        self.assertItemsEqual(eset.entries, dict())

        # test handling the event with a Cfg handler
        handler.__specific__ = False
        eset.entry_init(evt, handler)
        handler.assert_called_with(os.path.join(eset.path, evt.filename))
        self.assertItemsEqual(eset.entries,
                              {evt.filename: handler.return_value})
        handler.return_value.handle_event.assert_called_with(evt)

        # test handling an event for an entry that already exists with
        # a Cfg handler
        handler.reset_mock()
        eset.entry_init(evt, handler)
        self.assertFalse(handler.called)
        self.assertItemsEqual(eset.entries,
                              {evt.filename: handler.return_value})
        eset.entries[evt.filename].handle_event.assert_called_with(evt)

    @patch("Bcfg2.Server.Plugins.Cfg.u_str")
    @patch("Bcfg2.Server.Plugins.Cfg.b64encode")
    def test_bind_entry(self, mock_b64encode, mock_u_str):
        mock_u_str.side_effect = lambda x: x

        eset = self.get_obj()
        eset.bind_info_to_entry = Mock()
        eset._generate_data = Mock()
        eset.get_handlers = Mock()
        eset._validate_data = Mock()
        eset.setup = dict(validate=False)

        def reset():
            mock_b64encode.reset_mock()
            mock_u_str.reset_mock()
            eset.bind_info_to_entry.reset_mock()
            eset._generate_data.reset_mock()
            eset.get_handlers.reset_mock()
            eset._validate_data.reset_mock()
            return lxml.etree.Element("Path", name="/test.txt")

        entry = reset()
        metadata = Mock()

        # test basic entry, no validation, no filters, etc.
        eset._generate_data.return_value = ("data", None)
        eset.get_handlers.return_value = []
        bound = eset.bind_entry(entry, metadata)
        eset.bind_info_to_entry.assert_called_with(entry, metadata)
        eset._generate_data.assert_called_with(entry, metadata)
        self.assertFalse(eset._validate_data.called)
        expected = lxml.etree.Element("Path", name="/test.txt")
        expected.text = "data"
        self.assertXMLEqual(bound, expected)
        self.assertEqual(bound, entry)

        # test empty entry
        entry = reset()
        eset._generate_data.return_value = ("", None)
        bound = eset.bind_entry(entry, metadata)
        eset.bind_info_to_entry.assert_called_with(entry, metadata)
        eset._generate_data.assert_called_with(entry, metadata)
        self.assertFalse(eset._validate_data.called)
        expected = lxml.etree.Element("Path", name="/test.txt", empty="true")
        self.assertXMLEqual(bound, expected)
        self.assertEqual(bound, entry)

        # test filters
        entry = reset()
        generator = Mock()
        generator.specific = Specificity(all=True)
        eset._generate_data.return_value = ("initial data", generator)
        filters = [Mock(), Mock()]
        filters[0].modify_data.return_value = "modified data"
        filters[1].modify_data.return_value = "final data"
        eset.get_handlers.return_value = filters
        bound = eset.bind_entry(entry, metadata)
        eset.bind_info_to_entry.assert_called_with(entry, metadata)
        eset._generate_data.assert_called_with(entry, metadata)
        filters[0].modify_data.assert_called_with(entry, metadata,
                                                  "initial data")
        filters[1].modify_data.assert_called_with(entry, metadata,
                                                  "modified data")
        self.assertFalse(eset._validate_data.called)
        expected = lxml.etree.Element("Path", name="/test.txt")
        expected.text = "final data"
        self.assertXMLEqual(bound, expected)

        # test base64 encoding
        entry = reset()
        entry.set("encoding", "base64")
        mock_b64encode.return_value = "base64 data"
        eset.get_handlers.return_value = []
        eset._generate_data.return_value = ("data", None)
        bound = eset.bind_entry(entry, metadata)
        eset.bind_info_to_entry.assert_called_with(entry, metadata)
        eset._generate_data.assert_called_with(entry, metadata)
        self.assertFalse(eset._validate_data.called)
        mock_b64encode.assert_called_with("data")
        self.assertFalse(mock_u_str.called)
        expected = lxml.etree.Element("Path", name="/test.txt",
                                      encoding="base64")
        expected.text = "base64 data"
        self.assertXMLEqual(bound, expected)
        self.assertEqual(bound, entry)

        # test successful validation
        entry = reset()
        eset.setup['validate'] = True
        bound = eset.bind_entry(entry, metadata)
        eset.bind_info_to_entry.assert_called_with(entry, metadata)
        eset._generate_data.assert_called_with(entry, metadata)
        eset._validate_data.assert_called_with(entry, metadata, "data")
        expected = lxml.etree.Element("Path", name="/test.txt")
        expected.text = "data"
        self.assertXMLEqual(bound, expected)
        self.assertEqual(bound, entry)

        # test failed validation
        entry = reset()
        eset._validate_data.side_effect = CfgVerificationError
        self.assertRaises(PluginExecutionError,
                          eset.bind_entry, entry, metadata)
        eset.bind_info_to_entry.assert_called_with(entry, metadata)
        eset._generate_data.assert_called_with(entry, metadata)
        eset._validate_data.assert_called_with(entry, metadata, "data")

    def test_get_handlers(self):
        eset = self.get_obj()
        eset.entries['test1.txt'] = CfgInfo("test1.txt")
        eset.entries['test2.txt'] = CfgGenerator("test2.txt", Mock(), None)
        eset.entries['test2.txt'].specific.matches.return_value = True
        eset.entries['test3.txt'] = CfgInfo("test3.txt")
        eset.entries['test4.txt'] = CfgGenerator("test4.txt", Mock(), None)
        eset.entries['test4.txt'].specific.matches.return_value = False
        eset.entries['test5.txt'] = CfgGenerator("test5.txt", Mock(), None)
        eset.entries['test5.txt'].specific.matches.return_value = True
        eset.entries['test6.txt'] = CfgVerifier("test6.txt", Mock(), None)
        eset.entries['test6.txt'].specific.matches.return_value = True
        eset.entries['test7.txt'] = CfgFilter("test7.txt", Mock(), None)
        eset.entries['test7.txt'].specific.matches.return_value = False

        def reset():
            for e in eset.entries.values():
                if e.specific is not None:
                    e.specific.reset_mock()

        metadata = Mock()
        self.assertItemsEqual(eset.get_handlers(metadata, CfgGenerator),
                              [eset.entries['test2.txt'],
                               eset.entries['test5.txt']])
        for ename in ['test2.txt', 'test4.txt', 'test5.txt']:
            eset.entries[ename].specific.matches.assert_called_with(metadata)
        for ename in ['test6.txt', 'test7.txt']:
            self.assertFalse(eset.entries[ename].specific.matches.called)

        reset()
        self.assertItemsEqual(eset.get_handlers(metadata, CfgInfo),
                              [eset.entries['test1.txt'],
                               eset.entries['test3.txt']])
        for entry in eset.entries.values():
            if entry.specific is not None:
                self.assertFalse(entry.specific.matches.called)

        reset()
        self.assertItemsEqual(eset.get_handlers(metadata, CfgVerifier),
                              [eset.entries['test6.txt']])
        eset.entries['test6.txt'].specific.matches.assert_called_with(metadata)
        for ename, entry in eset.entries.items():
            if ename != 'test6.txt' and entry.specific is not None:
                self.assertFalse(entry.specific.matches.called)

        reset()
        self.assertItemsEqual(eset.get_handlers(metadata, CfgFilter), [])
        eset.entries['test7.txt'].specific.matches.assert_called_with(metadata)
        for ename, entry in eset.entries.items():
            if ename != 'test7.txt' and entry.specific is not None:
                self.assertFalse(entry.specific.matches.called)

        reset()
        self.assertItemsEqual(eset.get_handlers(metadata, Mock), [])
        for ename, entry in eset.entries.items():
            if entry.specific is not None:
                self.assertFalse(entry.specific.matches.called)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgDefaultInfo")
    def test_bind_info_to_entry(self, mock_DefaultInfo):
        eset = self.get_obj()
        eset.get_handlers = Mock()
        eset.get_handlers.return_value = []
        metadata = Mock()

        def reset():
            eset.get_handlers.reset_mock()
            mock_DefaultInfo.reset_mock()
            return lxml.etree.Element("Path", name="/test.txt")

        # test with no info handlers
        entry = reset()
        eset.bind_info_to_entry(entry, metadata)
        eset.get_handlers.assert_called_with(metadata, CfgInfo)
        mock_DefaultInfo.return_value.bind_info_to_entry.assert_called_with(
            entry, metadata)
        self.assertEqual(entry.get("type"), "file")

        # test with one info handler
        entry = reset()
        handler = Mock()
        eset.get_handlers.return_value = [handler]
        eset.bind_info_to_entry(entry, metadata)
        eset.get_handlers.assert_called_with(metadata, CfgInfo)
        mock_DefaultInfo.return_value.bind_info_to_entry.assert_called_with(
            entry, metadata)
        handler.bind_info_to_entry.assert_called_with(entry, metadata)
        self.assertEqual(entry.get("type"), "file")

        # test with more than one info handler
        entry = reset()
        handlers = [Mock(), Mock()]
        eset.get_handlers.return_value = handlers
        eset.bind_info_to_entry(entry, metadata)
        eset.get_handlers.assert_called_with(metadata, CfgInfo)
        mock_DefaultInfo.return_value.bind_info_to_entry.assert_called_with(
            entry, metadata)
        # we don't care which handler gets called as long as exactly
        # one of them does
        called = 0
        for handler in handlers:
            if handler.bind_info_to_entry.called:
                handler.bind_info_to_entry.assert_called_with(entry, metadata)
                called += 1
        self.assertEqual(called, 1)
        self.assertEqual(entry.get("type"), "file")

    def test_create_data(self):
        eset = self.get_obj()
        eset.best_matching = Mock()
        creator = Mock()
        creator.create_data.return_value = "data"
        eset.best_matching.return_value = creator
        eset.get_handlers = Mock()
        entry = lxml.etree.Element("Path", name="/test.txt", mode="0640")
        metadata = Mock()

        def reset():
            eset.best_matching.reset_mock()
            eset.get_handlers.reset_mock()

        # test success
        self.assertEqual(eset._create_data(entry, metadata), "data")
        eset.get_handlers.assert_called_with(metadata, CfgCreator)
        eset.best_matching.assert_called_with(metadata,
                                              eset.get_handlers.return_value)

        # test failure to create data
        reset()
        creator.create_data.side_effect = OSError
        self.assertRaises(PluginExecutionError,
                          eset._create_data, entry, metadata)

    def test_generate_data(self):
        eset = self.get_obj()
        eset.best_matching = Mock()
        eset._create_data = Mock()
        generator = Mock()
        generator.get_data.return_value = "data"
        eset.best_matching.return_value = generator
        eset.get_handlers = Mock()
        entry = lxml.etree.Element("Path", name="/test.txt", mode="0640")
        metadata = Mock()

        def reset():
            eset.best_matching.reset_mock()
            eset.get_handlers.reset_mock()
            eset._create_data.reset_mock()

        # test success
        self.assertEqual(eset._generate_data(entry, metadata)[0],
                         "data")
        eset.get_handlers.assert_called_with(metadata, CfgGenerator)
        eset.best_matching.assert_called_with(metadata,
                                              eset.get_handlers.return_value)
        self.assertFalse(eset._create_data.called)

        # test failure to generate data
        reset()
        generator.get_data.side_effect = OSError
        self.assertRaises(PluginExecutionError,
                          eset._generate_data, entry, metadata)

        # test no generator found
        reset()
        eset.best_matching.side_effect = PluginExecutionError
        self.assertEqual(eset._generate_data(entry, metadata),
                         (eset._create_data.return_value, None))
        eset.get_handlers.assert_called_with(metadata, CfgGenerator)
        eset.best_matching.assert_called_with(metadata,
                                              eset.get_handlers.return_value)
        eset._create_data.assert_called_with(entry, metadata)


    def test_validate_data(self):
        class MockChild1(Mock):
            pass

        class MockChild2(Mock):
            pass

        eset = self.get_obj()
        eset.get_handlers = Mock()
        handlers1 = [MockChild1(), MockChild1()]
        handlers2 = [MockChild2()]
        eset.get_handlers.return_value = [handlers1[0], handlers2[0],
                                          handlers1[1]]
        eset.best_matching = Mock()
        eset.best_matching.side_effect = lambda m, v: v[0]
        entry = lxml.etree.Element("Path", name="/test.txt")
        metadata = Mock()
        data = "data"

        eset._validate_data(entry, metadata, data)
        eset.get_handlers.assert_called_with(metadata, CfgVerifier)
        self.assertItemsEqual(eset.best_matching.call_args_list,
                              [call(metadata, handlers1),
                               call(metadata, handlers2)])
        handlers1[0].verify_entry.assert_called_with(entry, metadata, data)
        handlers2[0].verify_entry.assert_called_with(entry, metadata, data)

    def test_specificity_from_filename(self):
        pass


class TestCfg(TestGroupSpool, TestPullTarget):
    test_obj = Cfg

    def get_obj(self, core=None):
        if core is None:
            core = Mock()
        return TestGroupSpool.get_obj(self, core=core)

    @patch("Bcfg2.Options.get_option_parser")
    @patch("Bcfg2.Server.Plugin.GroupSpool.__init__")
    @patch("Bcfg2.Server.Plugin.PullTarget.__init__")
    def test__init(self, mock_pulltarget_init, mock_groupspool_init,
                   mock_get_option_parser):
        setup = MagicMock()
        setup.__contains__.return_value = False
        mock_get_option_parser.return_value = setup

        def reset():
            core.reset_mock()
            setup.reset_mock()
            mock_pulltarget_init.reset_mock()
            mock_groupspool_init.reset_mock()

        core = Mock()
        cfg = self.test_obj(core, datastore)
        mock_pulltarget_init.assert_called_with(cfg)
        mock_groupspool_init.assert_called_with(cfg, core, datastore)
        setup.add_option.assert_called_with(
            "validate",
            Bcfg2.Options.CFG_VALIDATION)
        mock_get_option_parser.return_value.reparse.assert_called_with()

        reset()
        setup.__contains__.return_value = True
        cfg = self.test_obj(core, datastore)
        mock_pulltarget_init.assert_called_with(cfg)
        mock_groupspool_init.assert_called_with(cfg, core, datastore)
        self.assertFalse(setup.add_option.called)
        self.assertFalse(setup.reparse.called)

    def test_has_generator(self):
        cfg = self.get_obj()
        cfg.entries = dict()
        entry = lxml.etree.Element("Path", name="/test.txt")
        metadata = Mock()

        self.assertFalse(cfg.has_generator(entry, metadata))

        eset = Mock()
        eset.get_handlers.return_value = []
        cfg.entries[entry.get("name")] = eset
        self.assertFalse(cfg.has_generator(entry, metadata))
        eset.get_handlers.assert_called_with(metadata, CfgGenerator)

        eset.get_handlers.reset_mock()
        eset.get_handlers.return_value = [Mock()]
        self.assertTrue(cfg.has_generator(entry, metadata))
        eset.get_handlers.assert_called_with(metadata, CfgGenerator)
