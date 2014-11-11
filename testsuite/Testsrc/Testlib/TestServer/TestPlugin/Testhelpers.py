import os
import sys
import copy
import genshi
import lxml.etree
import Bcfg2.Server
import genshi.core
from Bcfg2.Compat import reduce
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugin.helpers import *
from Bcfg2.Server.Plugin.exceptions import PluginInitError

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != '/':
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import *
from TestServer.TestPlugin.Testbase import TestPlugin, TestDebuggable
from TestServer.TestPlugin.Testinterfaces import TestGenerator

try:
    from Bcfg2.Server.Encryption import EVPError
except:
    pass


def tostring(el):
    return lxml.etree.tostring(el, xml_declaration=False).decode('UTF-8')


class FakeElementTree(lxml.etree._ElementTree):
    xinclude = Mock()
    parse = Mock


class TestFunctions(Bcfg2TestCase):
    def test_removecomment(self):
        data = [(None, "test", 1),
                (None, "test2", 2)]
        stream = [(genshi.core.COMMENT, "test", 0),
                  data[0],
                  (genshi.core.COMMENT, "test3", 0),
                  data[1]]
        self.assertItemsEqual(list(removecomment(stream)), data)


class TestDatabaseBacked(TestPlugin):
    test_obj = DatabaseBacked

    def setUp(self):
        TestPlugin.setUp(self)
        set_setup_default("%s_db" % self.test_obj.__name__.lower(), False)
        set_setup_default("db_engine", None)

    @skipUnless(HAS_DJANGO, "Django not found")
    def test__use_db(self):
        core = Mock()
        db = self.get_obj(core=core)
        attr = "%s_db" % self.test_obj.__name__.lower()

        db.core.database_available = True
        setattr(Bcfg2.Options.setup, attr, True)
        self.assertTrue(db._use_db)

        setattr(Bcfg2.Options.setup, attr, False)
        self.assertFalse(db._use_db)

        db.core.database_available = False
        self.assertFalse(db._use_db)

        setattr(Bcfg2.Options.setup, attr, True)
        self.assertRaises(PluginInitError, self.get_obj, core)


class TestPluginDatabaseModel(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestFileBacked(TestDebuggable):
    test_obj = FileBacked
    path = os.path.join(datastore, "test")

    def setUp(self):
        TestDebuggable.setUp(self)
        set_setup_default("filemonitor", MagicMock())

    def get_obj(self, path=None):
        if path is None:
            path = self.path
        return self.test_obj(path)

    @patch("%s.open" % builtins)
    def test_HandleEvent(self, mock_open):
        fb = self.get_obj()
        fb.Index = Mock()

        def reset():
            fb.Index.reset_mock()
            mock_open.reset_mock()

        for evt in ["exists", "changed", "created"]:
            reset()
            event = Mock()
            event.code2str.return_value = evt
            fb.HandleEvent(event)
            mock_open.assert_called_with(self.path)
            mock_open.return_value.read.assert_any_call()
            fb.Index.assert_any_call()

        reset()
        event = Mock()
        event.code2str.return_value = "endExist"
        fb.HandleEvent(event)
        self.assertFalse(mock_open.called)
        self.assertFalse(fb.Index.called)


class TestDirectoryBacked(TestDebuggable):
    test_obj = DirectoryBacked
    testpaths = {1: '',
                 2: '/foo',
                 3: '/foo/bar',
                 4: '/foo/bar/baz',
                 5: 'quux',
                 6: 'xyzzy/',
                 7: 'xyzzy/plugh/'}
    testfiles = ['foo', 'bar/baz.txt', 'plugh.py']
    ignore = []  # ignore no events
    badevents = []  # DirectoryBacked handles all files, so there's no
                    # such thing as a bad event

    def setUp(self):
        TestDebuggable.setUp(self)
        set_setup_default("filemonitor", MagicMock())

    def test_child_interface(self):
        """ ensure that the child object has the correct interface """
        self.assertTrue(hasattr(self.test_obj.__child__, "HandleEvent"))

    @patch("os.makedirs", Mock())
    def get_obj(self, fam=None):
        if fam is None:
            fam = Mock()

        @patch("%s.%s.add_directory_monitor" % (self.test_obj.__module__,
                                                self.test_obj.__name__),
               Mock())
        def inner():
            return self.test_obj(os.path.join(datastore,
                                              self.test_obj.__name__))
        return inner()

    @patch("os.makedirs")
    @patch("os.path.exists")
    def test__init(self, mock_exists, mock_makedirs):
        @patch("%s.%s.add_directory_monitor" % (self.test_obj.__module__,
                                                self.test_obj.__name__))
        def inner(mock_add_monitor):
            db = self.test_obj(datastore)
            mock_exists.return_value = True
            mock_add_monitor.assert_called_with('')
            mock_exists.assert_called_with(db.data)
            self.assertFalse(mock_makedirs.called)

            mock_add_monitor.reset_mock()
            mock_exists.reset_mock()
            mock_makedirs.reset_mock()
            mock_exists.return_value = False
            db = self.test_obj(datastore)
            mock_add_monitor.assert_called_with('')
            mock_exists.assert_called_with(db.data)
            mock_makedirs.assert_called_with(db.data)

        inner()

    def test__getitem(self):
        db = self.get_obj()
        db.entries.update(dict(a=1, b=2, c=3))
        self.assertEqual(db['a'], 1)
        self.assertEqual(db['b'], 2)
        expected = KeyError
        try:
            db['d']
        except expected:
            pass
        except:
            err = sys.exc_info()[1]
            self.assertFalse(True, "%s raised instead of %s" %
                             (err.__class__.__name__,
                              expected.__class__.__name__))
        else:
            self.assertFalse(True,
                             "%s not raised" % expected.__class__.__name__)

    def test__iter(self):
        db = self.get_obj()
        db.entries.update(dict(a=1, b=2, c=3))
        self.assertEqual([i for i in db],
                         [i for i in db.entries.items()])

    @patch("os.path.isdir")
    def test_add_directory_monitor(self, mock_isdir):
        db = self.get_obj()
        db.fam = Mock()
        db.fam.rv = 0

        def reset():
            db.fam.rv += 1
            db.fam.AddMonitor.return_value = db.fam.rv
            db.fam.reset_mock()
            mock_isdir.reset_mock()

        mock_isdir.return_value = True
        for path in self.testpaths.values():
            reset()
            db.add_directory_monitor(path)
            db.fam.AddMonitor.assert_called_with(os.path.join(db.data, path),
                                                 db)
            self.assertIn(db.fam.rv, db.handles)
            self.assertEqual(db.handles[db.fam.rv], path)

        reset()
        # test duplicate adds
        for path in self.testpaths.values():
            reset()
            db.add_directory_monitor(path)
            self.assertFalse(db.fam.AddMonitor.called)

        reset()
        mock_isdir.return_value = False
        db.add_directory_monitor('bogus')
        self.assertFalse(db.fam.AddMonitor.called)
        self.assertNotIn(db.fam.rv, db.handles)

    def test_add_entry(self):
        db = self.get_obj()
        db.fam = Mock()

        class MockChild(Mock):
            def __init__(self, path, **kwargs):
                Mock.__init__(self, **kwargs)
                self.path = path
                self.HandleEvent = Mock()
        db.__child__ = MockChild

        for path in self.testpaths.values():
            event = Mock()
            db.add_entry(path, event)
            self.assertIn(path, db.entries)
            self.assertEqual(db.entries[path].path,
                             os.path.join(db.data, path))
            db.entries[path].HandleEvent.assert_called_with(event)

    @patch("os.path.isdir")
    def test_HandleEvent(self, mock_isdir):
        db = self.get_obj()
        db.add_entry = Mock()
        db.add_directory_monitor = Mock()
        # a path with a leading / should never get into
        # DirectoryBacked.handles, so strip that test case
        for rid, path in self.testpaths.items():
            path = path.lstrip('/')
            db.handles[rid] = path

        def reset():
            mock_isdir.reset_mock()
            db.add_entry.reset_mock()
            db.add_directory_monitor.reset_mock()

        def get_event(filename, action, requestID):
            event = Mock()
            event.code2str.return_value = action
            event.filename = filename
            event.requestID = requestID
            return event

        # test events on the data directory itself
        reset()
        mock_isdir.return_value = True
        event = get_event(db.data, "exists", 1)
        db.HandleEvent(event)
        db.add_directory_monitor.assert_called_with("")

        # test events on paths that aren't handled
        reset()
        mock_isdir.return_value = False
        event = get_event('/' + self.testfiles[0], 'created',
                          max(self.testpaths.keys()) + 1)
        db.HandleEvent(event)
        self.assertFalse(db.add_directory_monitor.called)
        self.assertFalse(db.add_entry.called)

        for req_id, path in self.testpaths.items():
            # a path with a leading / should never get into
            # DirectoryBacked.handles, so strip that test case
            path = path.lstrip('/')
            basepath = os.path.join(datastore, path)
            for fname in self.testfiles:
                relpath = os.path.join(path, fname)
                abspath = os.path.join(basepath, fname)

                # test endExist does nothing
                reset()
                event = get_event(fname, 'endExist', req_id)
                db.HandleEvent(event)
                self.assertFalse(db.add_directory_monitor.called)
                self.assertFalse(db.add_entry.called)

                mock_isdir.return_value = True
                for evt in ["created", "exists", "changed"]:
                    # test that creating or changing a directory works
                    reset()
                    event = get_event(fname, evt, req_id)
                    db.HandleEvent(event)
                    db.add_directory_monitor.assert_called_with(relpath)
                    self.assertFalse(db.add_entry.called)

                mock_isdir.return_value = False
                for evt in ["created", "exists"]:
                    # test that creating a file works
                    reset()
                    event = get_event(fname, evt, req_id)
                    db.HandleEvent(event)
                    db.add_entry.assert_called_with(relpath, event)
                    self.assertFalse(db.add_directory_monitor.called)
                    db.entries[relpath] = MagicMock()

                # test that changing a file that already exists works
                reset()
                event = get_event(fname, "changed", req_id)
                db.HandleEvent(event)
                db.entries[relpath].HandleEvent.assert_called_with(event)
                self.assertFalse(db.add_directory_monitor.called)
                self.assertFalse(db.add_entry.called)

                # test that deleting an entry works
                reset()
                event = get_event(fname, "deleted", req_id)
                db.HandleEvent(event)
                self.assertNotIn(relpath, db.entries)

                # test that changing a file that doesn't exist works
                reset()
                event = get_event(fname, "changed", req_id)
                db.HandleEvent(event)
                db.add_entry.assert_called_with(relpath, event)
                self.assertFalse(db.add_directory_monitor.called)
                db.entries[relpath] = MagicMock()

        # test that deleting a directory works. this is a little
        # strange because the _parent_ directory has to handle the
        # deletion
        reset()
        event = get_event('quux', "deleted", 1)
        db.HandleEvent(event)
        for key in db.entries.keys():
            self.assertFalse(key.startswith('quux'))

        # test bad events
        for fname in self.badevents:
            reset()
            event = get_event(fname, "created", 1)
            db.HandleEvent(event)
            self.assertFalse(db.add_entry.called)
            self.assertFalse(db.add_directory_monitor.called)

        # test ignored events
        for fname in self.ignore:
            reset()
            event = get_event(fname, "created", 1)
            db.HandleEvent(event)
            self.assertFalse(mock_isdir.called,
                             msg="Failed to ignore %s" % fname)
            self.assertFalse(db.add_entry.called,
                             msg="Failed to ignore %s" % fname)
            self.assertFalse(db.add_directory_monitor.called,
                             msg="Failed to ignore %s" % fname)


class TestXMLFileBacked(TestFileBacked):
    test_obj = XMLFileBacked

    # can be set to True (on child test cases where should_monitor is
    # always True) or False (on child test cases where should_monitor
    # is always False)
    should_monitor = None
    path = os.path.join(datastore, "test", "test1.xml")

    def setUp(self):
        TestFileBacked.setUp(self)
        set_setup_default("encoding", 'utf-8')

    def get_obj(self, path=None, should_monitor=False):
        if path is None:
            path = self.path

        @patchIf(not isinstance(os.path.exists, Mock),
                 "os.path.exists", Mock())
        def inner():
            return self.test_obj(path, should_monitor=should_monitor)
        return inner()

    @patch("Bcfg2.Server.FileMonitor.get_fam")
    def test__init(self, mock_get_fam):
        xfb = self.get_obj()
        self.assertEqual(xfb.fam, mock_get_fam.return_value)

        if self.should_monitor:
            xfb = self.get_obj(should_monitor=True)
            xfb.fam.AddMonitor.assert_called_with(self.path, xfb)
        else:
            xfb = self.get_obj()
            self.assertFalse(xfb.fam.AddMonitor.called)

    @patch("glob.glob")
    @patch("lxml.etree.parse")
    def test_follow_xincludes(self, mock_parse, mock_glob):
        xfb = self.get_obj()
        xfb.add_monitor = Mock()
        xfb.add_monitor.side_effect = lambda p: xfb.extras.append(p)

        def reset():
            xfb.add_monitor.reset_mock()
            mock_glob.reset_mock()
            mock_parse.reset_mock()
            xfb.extras = []

        xdata = dict()
        mock_parse.side_effect = lambda p: xdata[p]
        mock_glob.side_effect = lambda g: [g]

        base = os.path.dirname(self.path)

        # basic functionality
        test2 = os.path.join(base, 'test2.xml')
        xdata[test2] = lxml.etree.Element("Test").getroottree()
        xfb._follow_xincludes(xdata=xdata[test2])
        self.assertFalse(xfb.add_monitor.called)

        if (not hasattr(self.test_obj, "xdata") or
            not isinstance(self.test_obj.xdata, property)):
            # if xdata is settable, test that method of getting data
            # to _follow_xincludes
            reset()
            xfb.xdata = xdata[test2].getroot()
            xfb._follow_xincludes()
            self.assertFalse(xfb.add_monitor.called)
            xfb.xdata = None

        reset()
        xfb._follow_xincludes(fname=test2)
        self.assertFalse(xfb.add_monitor.called)

        # test one level of xinclude
        xdata[self.path] = lxml.etree.Element("Test").getroottree()
        lxml.etree.SubElement(xdata[self.path].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href=test2)
        reset()
        xfb._follow_xincludes(fname=self.path)
        xfb.add_monitor.assert_called_with(test2)
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()])
        mock_glob.assert_called_with(test2)

        reset()
        xfb._follow_xincludes(fname=self.path, xdata=xdata[self.path])
        xfb.add_monitor.assert_called_with(test2)
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()
                               if f != self.path])
        mock_glob.assert_called_with(test2)

        # test two-deep level of xinclude, with some files in another
        # directory
        test3 = os.path.join(base, "test3.xml")
        test4 = os.path.join(base, "test_dir", "test4.xml")
        test5 = os.path.join(base, "test_dir", "test5.xml")
        test6 = os.path.join(base, "test_dir", "test6.xml")
        xdata[test3] = lxml.etree.Element("Test").getroottree()
        lxml.etree.SubElement(xdata[test3].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href=test4)
        xdata[test4] = lxml.etree.Element("Test").getroottree()
        lxml.etree.SubElement(xdata[test4].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href=test5)
        xdata[test5] = lxml.etree.Element("Test").getroottree()
        xdata[test6] = lxml.etree.Element("Test").getroottree()
        # relative includes
        lxml.etree.SubElement(xdata[self.path].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="test3.xml")
        lxml.etree.SubElement(xdata[test3].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="test_dir/test6.xml")

        reset()
        xfb._follow_xincludes(fname=self.path)
        expected = [call(f) for f in xdata.keys() if f != self.path]
        self.assertItemsEqual(xfb.add_monitor.call_args_list, expected)
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()])
        self.assertItemsEqual(mock_glob.call_args_list, expected)

        reset()
        xfb._follow_xincludes(fname=self.path, xdata=xdata[self.path])
        expected = [call(f) for f in xdata.keys() if f != self.path]
        self.assertItemsEqual(xfb.add_monitor.call_args_list, expected)
        self.assertItemsEqual(mock_parse.call_args_list, expected)
        self.assertItemsEqual(mock_glob.call_args_list, expected)

        # test wildcard xinclude
        reset()
        xdata[self.path] = lxml.etree.Element("Test").getroottree()
        lxml.etree.SubElement(xdata[self.path].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="*.xml")

        def glob_rv(path):
            if path == os.path.join(base, '*.xml'):
                return [self.path, test2, test3]
            else:
                return [path]
        mock_glob.side_effect = glob_rv

        xfb._follow_xincludes(xdata=xdata[self.path])
        expected = [call(f) for f in xdata.keys() if f != self.path]
        self.assertItemsEqual(xfb.add_monitor.call_args_list, expected)
        self.assertItemsEqual(mock_parse.call_args_list, expected)
        self.assertItemsEqual(mock_glob.call_args_list,
                              [call(os.path.join(base, '*.xml')), call(test4),
                               call(test5), call(test6)])


    @patch("lxml.etree._ElementTree", FakeElementTree)
    @patch("Bcfg2.Server.Plugin.helpers.%s._follow_xincludes" %
           test_obj.__name__)
    def test_Index(self, mock_follow):
        xfb = self.get_obj()

        def reset():
            mock_follow.reset_mock()
            FakeElementTree.xinclude.reset_mock()
            xfb.extras = []
            xfb.xdata = None

        # no xinclude
        reset()
        xdata = lxml.etree.Element("Test", name="test")
        children = [lxml.etree.SubElement(xdata, "Foo"),
                    lxml.etree.SubElement(xdata, "Bar", name="bar")]
        xfb.data = tostring(xdata)
        xfb.Index()
        mock_follow.assert_any_call()
        try:
            self.assertEqual(xfb.xdata.base, self.path)
        except AttributeError:
            # python 2.4 and/or lxml 2.0 don't store the base_url in
            # .base -- no idea where it's stored.
            pass
        self.assertItemsEqual([tostring(e) for e in xfb.entries],
                              [tostring(e) for e in children])

        # with xincludes
        reset()
        mock_follow.side_effect = \
            lambda: xfb.extras.extend(["/test/test2.xml",
                                       "/test/test_dir/test3.xml"])
        children.extend([
                lxml.etree.SubElement(xdata,
                                      Bcfg2.Server.XI_NAMESPACE + "include",
                                      href="/test/test2.xml"),
                lxml.etree.SubElement(xdata,
                                      Bcfg2.Server.XI_NAMESPACE + "include",
                                      href="/test/test_dir/test3.xml")])
        test2 = lxml.etree.Element("Test", name="test2")
        lxml.etree.SubElement(test2, "Baz")
        test3 = lxml.etree.Element("Test", name="test3")
        replacements = {"/test/test2.xml": test2,
                        "/test/test_dir/test3.xml": test3}

        def xinclude():
            for el in xfb.xdata.findall('//%sinclude' %
                                        Bcfg2.Server.XI_NAMESPACE):
                xfb.xdata.replace(el, replacements[el.get("href")])
        FakeElementTree.xinclude.side_effect = xinclude

        xfb.data = tostring(xdata)
        xfb.Index()
        mock_follow.assert_any_call()
        FakeElementTree.xinclude.assert_any_call
        try:
            self.assertEqual(xfb.xdata.base, self.path)
        except AttributeError:
            pass
        self.assertItemsEqual([tostring(e) for e in xfb.entries],
                              [tostring(e) for e in children])

    @patch("Bcfg2.Server.FileMonitor.get_fam", Mock())
    def test_add_monitor(self):
        xfb = self.get_obj()
        xfb.add_monitor("/test/test2.xml")
        self.assertIn("/test/test2.xml", xfb.extra_monitors)

        xfb = self.get_obj()
        xfb.fam = Mock()
        xfb.add_monitor("/test/test4.xml")
        xfb.fam.AddMonitor.assert_called_with("/test/test4.xml", xfb)
        self.assertIn("/test/test4.xml", xfb.extra_monitors)


class TestStructFile(TestXMLFileBacked):
    test_obj = StructFile

    def setUp(self):
        TestXMLFileBacked.setUp(self)
        set_setup_default("lax_decryption", False)

    def _get_test_data(self):
        """ build a very complex set of test data """
        # top-level group and client elements
        groups = dict()
        # group and client elements that are descendents of other group or
        # client elements
        subgroups = dict()
        # children of elements in `groups' that should be included in
        # match results
        children = dict()
        # children of elements in `subgroups' that should be included in
        # match results
        subchildren = dict()
        # top-level tags that are not group elements
        standalone = []
        xdata = lxml.etree.Element("Test", name="test")
        groups[0] = lxml.etree.SubElement(xdata, "Group", name="group1",
                                          include="true")
        children[0] = [lxml.etree.SubElement(groups[0], "Child", name="c1"),
                       lxml.etree.SubElement(groups[0], "Child", name="c2")]
        subgroups[0] = [lxml.etree.SubElement(groups[0], "Group",
                                              name="subgroup1", include="true"),
                        lxml.etree.SubElement(groups[0],
                                              "Client", name="client1",
                                              include="false")]
        subchildren[0] = \
            [lxml.etree.SubElement(subgroups[0][0], "Child", name="sc1"),
             lxml.etree.SubElement(subgroups[0][0], "Child", name="sc2",
                                   attr="some attr"),
             lxml.etree.SubElement(subgroups[0][0], "Child", name="sc3")]
        lxml.etree.SubElement(subchildren[0][-1], "SubChild", name="subchild")
        lxml.etree.SubElement(subgroups[0][1], "Child", name="sc4")

        groups[1] = lxml.etree.SubElement(xdata, "Group", name="group2",
                                          include="false")
        children[1] = []
        subgroups[1] = []
        subchildren[1] = []
        lxml.etree.SubElement(groups[1], "Child", name="c3")
        lxml.etree.SubElement(groups[1], "Child", name="c4")

        standalone.append(lxml.etree.SubElement(xdata,
                                                "Standalone", name="s1"))

        groups[2] = lxml.etree.SubElement(xdata, "Client", name="client2",
                                          include="false")
        children[2] = []
        subgroups[2] = []
        subchildren[2] = []
        lxml.etree.SubElement(groups[2], "Child", name="c5")
        lxml.etree.SubElement(groups[2], "Child", name="c6")

        standalone.append(lxml.etree.SubElement(xdata, "Standalone", name="s2",
                                                attr="some attr"))

        groups[3] = lxml.etree.SubElement(xdata, "Client", name="client3",
                                          include="true")
        children[3] = [lxml.etree.SubElement(groups[3], "Child", name="c7",
                                             attr="some_attr"),
                       lxml.etree.SubElement(groups[3], "Child", name="c8")]
        subgroups[3] = []
        subchildren[3] = []
        lxml.etree.SubElement(children[3][-1], "SubChild", name="subchild")

        standalone.append(lxml.etree.SubElement(xdata,
                                                "Standalone", name="s3"))
        lxml.etree.SubElement(standalone[-1], "SubStandalone", name="sub1")

        return (xdata, groups, subgroups, children, subchildren, standalone)

    def _get_template_test_data(self):
        (xdata, groups, subgroups, children, subchildren, standalone) = \
            self._get_test_data()
        template_xdata = \
            lxml.etree.Element("Test", name="test",
                               nsmap=dict(py='http://genshi.edgewall.org/'))
        template_xdata.extend(xdata.getchildren())
        return (template_xdata, groups, subgroups, children, subchildren,
                standalone)

    @patch("genshi.template.TemplateLoader")
    def test_Index(self, mock_TemplateLoader):
        TestXMLFileBacked.test_Index(self)

        sf = self.get_obj()
        sf.encryption = False
        sf.encoding = Mock()
        (xdata, groups, subgroups, children, subchildren, standalone) = \
            self._get_test_data()
        sf.data = lxml.etree.tostring(xdata)

        mock_TemplateLoader.reset_mock()
        sf.Index()
        self.assertFalse(mock_TemplateLoader.called)

        mock_TemplateLoader.reset_mock()
        template_xdata = \
            lxml.etree.Element("Test", name="test",
                               nsmap=dict(py='http://genshi.edgewall.org/'))
        template_xdata.extend(xdata.getchildren())
        sf.data = lxml.etree.tostring(template_xdata)
        sf.Index()
        mock_TemplateLoader.assert_called_with()
        loader = mock_TemplateLoader.return_value
        loader.load.assert_called_with(sf.name,
                                       cls=genshi.template.MarkupTemplate,
                                       encoding=Bcfg2.Options.setup.encoding)
        self.assertEqual(sf.template,
                         loader.load.return_value)

    @skipUnless(HAS_CRYPTO, "No crypto libraries found, skipping")
    def test_Index_crypto(self):
        if not self.test_obj.encryption:
            return
        Bcfg2.Options.setup.lax_decryption = False
        sf = self.get_obj()
        sf._decrypt = Mock()
        sf._decrypt.return_value = 'plaintext'
        sf.data = '''
<EncryptedData>
  <Group name="test">
    <Datum encrypted="foo">crypted</Datum>
  </Group>
  <Group name="test" negate="true">
    <Datum>plain</Datum>
  </Group>
</EncryptedData>'''

        # test successful decryption
        sf.Index()
        self.assertItemsEqual(
            sf._decrypt.call_args_list,
            [call(el) for el in sf.xdata.xpath("//*[@encrypted]")])
        for el in sf.xdata.xpath("//*[@encrypted]"):
            self.assertEqual(el.text, sf._decrypt.return_value)

        # test failed decryption, strict
        sf._decrypt.reset_mock()
        sf._decrypt.side_effect = EVPError
        self.assertRaises(PluginExecutionError, sf.Index)

        # test failed decryption, lax
        Bcfg2.Options.setup.lax_decryption = True
        sf._decrypt.reset_mock()
        sf.Index()
        self.assertItemsEqual(
            sf._decrypt.call_args_list,
            [call(el) for el in sf.xdata.xpath("//*[@encrypted]")])

    @skipUnless(HAS_CRYPTO, "No crypto libraries found, skipping")
    @patchIf(HAS_CRYPTO, "Bcfg2.Server.Encryption.ssl_decrypt")
    def test_decrypt(self, mock_ssl):
        sf = self.get_obj()

        def reset():
            mock_ssl.reset_mock()

        # test element without text contents
        Bcfg2.Options.setup.passphrases = dict()
        self.assertIsNone(sf._decrypt(lxml.etree.Element("Test")))
        self.assertFalse(mock_ssl.called)

        # test element with a passphrase in the config file
        reset()
        el = lxml.etree.Element("Test", encrypted="foo")
        el.text = "crypted"
        Bcfg2.Options.setup.passphrases = dict(foo="foopass", bar="barpass")
        mock_ssl.return_value = "decrypted with ssl"
        self.assertEqual(sf._decrypt(el), mock_ssl.return_value)
        mock_ssl.assert_called_with(el.text, "foopass")

        # test element without valid passphrase
        reset()
        el.set("encrypted", "true")
        self.assertRaises(EVPError, sf._decrypt, el)
        self.assertFalse(mock_ssl.called)

        # test failure to decrypt element with a passphrase in the config
        reset()
        mock_ssl.side_effect = EVPError
        self.assertRaises(EVPError, sf._decrypt, el)

    def test_include_element(self):
        sf = self.get_obj()
        metadata = Mock()
        metadata.groups = ["group1", "group2"]
        metadata.hostname = "foo.example.com"

        inc = lambda tag, **attrs: \
            sf._include_element(lxml.etree.Element(tag, **attrs), metadata)

        self.assertFalse(sf._include_element(lxml.etree.Comment("test"),
                                             metadata))

        self.assertFalse(inc("Group", name="group3"))
        self.assertFalse(inc("Group", name="group2", negate="true"))
        self.assertFalse(inc("Group", name="group2", negate="tRuE"))
        self.assertTrue(inc("Group", name="group2"))
        self.assertTrue(inc("Group", name="group2", negate="false"))
        self.assertTrue(inc("Group", name="group2", negate="faLSe"))
        self.assertTrue(inc("Group", name="group3", negate="true"))
        self.assertTrue(inc("Group", name="group3", negate="tRUe"))

        self.assertFalse(inc("Client", name="bogus.example.com"))
        self.assertFalse(inc("Client", name="foo.example.com", negate="true"))
        self.assertFalse(inc("Client", name="foo.example.com", negate="tRuE"))
        self.assertTrue(inc("Client", name="foo.example.com"))
        self.assertTrue(inc("Client", name="foo.example.com", negate="false"))
        self.assertTrue(inc("Client", name="foo.example.com", negate="faLSe"))
        self.assertTrue(inc("Client", name="bogus.example.com", negate="true"))
        self.assertTrue(inc("Client", name="bogus.example.com", negate="tRUe"))

        self.assertTrue(inc("Other"))

    def test__match(self):
        sf = self.get_obj()
        sf._include_element = Mock()
        metadata = Mock()

        sf._include_element.side_effect = \
            lambda x, _: (x.tag not in sf._include_tests.keys() or
                          x.get("include") == "true")

        for test_data in [self._get_test_data(),
                          self._get_template_test_data()]:
            (xdata, groups, subgroups, children, subchildren, standalone) = \
                test_data

            for i, group in groups.items():
                actual = sf._match(group, metadata)
                expected = children[i] + subchildren[i]
                self.assertEqual(len(actual), len(expected))
                # easiest way to compare the values is actually to make
                # them into an XML document and let assertXMLEqual compare
                # them
                xactual = lxml.etree.Element("Container")
                xactual.extend(actual)
                xexpected = lxml.etree.Element("Container")
                xexpected.extend(expected)
                self.assertXMLEqual(xactual, xexpected)

            for el in standalone:
                self.assertXMLEqual(el, sf._match(el, metadata)[0])

    def test_do_match(self):
        Bcfg2.Options.setup.lax_decryption = True
        sf = self.get_obj()
        sf._match = Mock()

        def match_rv(el, _):
            if el.tag not in sf._include_tests.keys():
                return [el]
            elif el.get("include") == "true":
                return el.getchildren()
            else:
                return []
        sf._match.side_effect = match_rv

        metadata = Mock()

        for test_data in [self._get_test_data(),
                          self._get_template_test_data()]:
            (xdata, groups, subgroups, children, subchildren, standalone) = \
                test_data
            sf.data = lxml.etree.tostring(xdata)
            sf.Index()

            actual = sf._do_match(metadata)
            expected = reduce(lambda x, y: x + y,
                              list(children.values()) + \
                                  list(subgroups.values())) + standalone
            self.assertEqual(len(actual), len(expected))
            # easiest way to compare the values is actually to make
            # them into an XML document and let assertXMLEqual compare
            # them
            xactual = lxml.etree.Element("Container")
            xactual.extend(actual)
            xexpected = lxml.etree.Element("Container")
            xexpected.extend(expected)
            self.assertXMLEqual(xactual, xexpected)

    def test__xml_match(self):
        sf = self.get_obj()
        sf._include_element = Mock()
        metadata = Mock()

        sf._include_element.side_effect = \
            lambda x, _: (x.tag not in sf._include_tests.keys() or
                          x.get("include") == "true")

        for test_data in [self._get_test_data(),
                          self._get_template_test_data()]:
            (xdata, groups, subgroups, children, subchildren, standalone) = \
                test_data

            actual = copy.deepcopy(xdata)
            for el in actual.getchildren():
                sf._xml_match(el, metadata)
            expected = lxml.etree.Element(xdata.tag, **dict(xdata.attrib))
            expected.text = xdata.text
            expected.extend(reduce(lambda x, y: x + y,
                                   list(children.values()) + \
                                       list(subchildren.values())))
            expected.extend(standalone)
            self.assertXMLEqual(actual, expected)

    def test_do_xmlmatch(self):
        sf = self.get_obj()
        sf._xml_match = Mock()
        metadata = Mock()

        for data_type, test_data in \
                [("", self._get_test_data()),
                 ("templated ", self._get_template_test_data())]:
            (xdata, groups, subgroups, children, subchildren, standalone) = \
                test_data
            sf.xdata = xdata
            sf._xml_match.reset_mock()

            sf._do_xmlmatch(metadata)
            actual = []
            for call in sf._xml_match.call_args_list:
                actual.append(call[0][0])
                self.assertEqual(call[0][1], metadata)
            expected = list(groups.values()) + standalone
            # easiest way to compare the values is actually to make
            # them into an XML document and let assertXMLEqual compare
            # them
            xactual = lxml.etree.Element("Container")
            xactual.extend(actual)
            xexpected = lxml.etree.Element("Container")
            xexpected.extend(expected)
            self.assertXMLEqual(xactual, xexpected,
                                "XMLMatch() calls were incorrect for "
                                "%stest data" % data_type)

    def test_match_ordering(self):
        """ Match() returns elements in document order """
        Bcfg2.Options.setup.lax_decryption = True
        sf = self.get_obj()
        sf._match = Mock()

        def match_rv(el, _):
            if el.tag not in sf._include_tests.keys():
                return [el]
            elif el.get("include") == "true":
                return el.getchildren()
            else:
                return []
        sf._match.side_effect = match_rv

        metadata = Mock()

        test_data = lxml.etree.Element("Test")
        group = lxml.etree.SubElement(test_data, "Group", name="group",
                                      include="true")
        first = lxml.etree.SubElement(group, "Element", name="first")
        second = lxml.etree.SubElement(test_data, "Element", name="second")

        # sanity check to ensure that first and second are in the
        # correct document order
        if test_data.xpath("//Element") != [first, second]:
            skip("lxml.etree does not construct documents in a reliable order")

        sf.data = lxml.etree.tostring(test_data)
        sf.Index()
        rv = sf._do_match(metadata)
        self.assertEqual(len(rv), 2,
                         "Match() seems to be broken, cannot test ordering")
        msg = "Match() does not return elements in document order:\n" + \
            "Expected: [%s, %s]\n" % (first, second) + \
            "Actual: %s" % rv
        self.assertXMLEqual(rv[0], first, msg)
        self.assertXMLEqual(rv[1], second, msg)

        # TODO: add tests to ensure that XMLMatch() returns elements
        # in document order


class TestInfoXML(TestStructFile):
    test_obj = InfoXML

    def _get_test_data(self):
        (xdata, groups, subgroups, children, subchildren, standalone) = \
            TestStructFile._get_test_data(self)
        idx = max(groups.keys()) + 1
        groups[idx] = lxml.etree.SubElement(
            xdata, "Path", name="path1", include="true")
        children[idx] = [lxml.etree.SubElement(groups[idx], "Child",
                                               name="pc1")]
        subgroups[idx] = [lxml.etree.SubElement(groups[idx], "Group",
                                                name="pg1", include="true"),
                          lxml.etree.SubElement(groups[idx], "Client",
                                                name="pc1", include="false")]
        subchildren[idx] = [lxml.etree.SubElement(subgroups[idx][0],
                                                  "SubChild", name="sc1")]

        idx += 1
        groups[idx] = lxml.etree.SubElement(
            xdata, "Path", name="path2", include="false")
        children[idx] = []
        subgroups[idx] = []
        subchildren[idx] = []

        path2 = lxml.etree.SubElement(groups[0], "Path", name="path2",
                                      include="true")
        subgroups[0].append(path2)
        subchildren[0].append(lxml.etree.SubElement(path2, "SubChild",
                                                    name="sc2"))
        return xdata, groups, subgroups, children, subchildren, standalone

    def test_include_element(self):
        TestStructFile.test_include_element(self)

        ix = self.get_obj()
        metadata = Mock()
        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        inc = lambda tag, **attrs: \
            ix._include_element(lxml.etree.Element(tag, **attrs),
                                metadata, entry)

        self.assertFalse(inc("Path", name="/etc/bar.conf"))
        self.assertFalse(inc("Path", name="/etc/foo.conf", negate="true"))
        self.assertFalse(inc("Path", name="/etc/foo.conf", negate="tRuE"))
        self.assertTrue(inc("Path", name="/etc/foo.conf"))
        self.assertTrue(inc("Path", name="/etc/foo.conf", negate="false"))
        self.assertTrue(inc("Path", name="/etc/foo.conf", negate="faLSe"))
        self.assertTrue(inc("Path", name="/etc/bar.conf", negate="true"))
        self.assertTrue(inc("Path", name="/etc/bar.conf", negate="tRUe"))

    def test_BindEntry(self):
        ix = self.get_obj()
        entry = lxml.etree.Element("Path", name=self.path)
        metadata = Mock()

        # test with bogus infoxml
        ix.Match = Mock()
        ix.Match.return_value = []
        self.assertRaises(PluginExecutionError,
                          ix.BindEntry, entry, metadata)
        ix.Match.assert_called_with(metadata, entry)

        # test with valid infoxml
        ix.Match.reset_mock()
        ix.Match.return_value = [lxml.etree.Element("Info",
                                                    mode="0600", owner="root")]
        ix.BindEntry(entry, metadata)
        ix.Match.assert_called_with(metadata, entry)
        self.assertItemsEqual(entry.attrib,
                              dict(name=self.path, mode="0600", owner="root"))

    def _get_test_data(self):
        (xdata, groups, subgroups, children, subchildren, standalone) = \
            TestStructFile._get_test_data(self)
        idx = max(groups.keys()) + 1
        groups[idx] = lxml.etree.SubElement(
            xdata, "Path", name="path1", include="true")
        children[idx] = [lxml.etree.SubElement(groups[idx], "Child",
                                               name="pc1")]
        subgroups[idx] = [lxml.etree.SubElement(groups[idx], "Group",
                                                name="pg1", include="true"),
                          lxml.etree.SubElement(groups[idx], "Client",
                                                name="pc1", include="false")]
        subchildren[idx] = [lxml.etree.SubElement(subgroups[idx][0],
                                                  "SubChild", name="sc1")]

        idx += 1
        groups[idx] = lxml.etree.SubElement(
            xdata, "Path", name="path2", include="false")
        children[idx] = []
        subgroups[idx] = []
        subchildren[idx] = []

        path2 = lxml.etree.SubElement(groups[0], "Path", name="path2",
                                      include="true")
        subgroups[0].append(path2)
        subchildren[0].append(lxml.etree.SubElement(path2, "SubChild",
                                                    name="sc2"))
        return xdata, groups, subgroups, children, subchildren, standalone

    def test_include_element(self):
        TestStructFile.test_include_element(self)

        ix = self.get_obj()
        metadata = Mock()
        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        inc = lambda tag, **attrs: \
            ix._include_element(lxml.etree.Element(tag, **attrs),
                                metadata, entry)

        self.assertFalse(inc("Path", name="/etc/bar.conf"))
        self.assertFalse(inc("Path", name="/etc/foo.conf", negate="true"))
        self.assertFalse(inc("Path", name="/etc/foo.conf", negate="tRuE"))
        self.assertTrue(inc("Path", name="/etc/foo.conf"))
        self.assertTrue(inc("Path", name="/etc/foo.conf", negate="false"))
        self.assertTrue(inc("Path", name="/etc/foo.conf", negate="faLSe"))
        self.assertTrue(inc("Path", name="/etc/bar.conf", negate="true"))
        self.assertTrue(inc("Path", name="/etc/bar.conf", negate="tRUe"))

    def test_include_element_altsrc(self):
        ix = self.get_obj()
        metadata = Mock()
        entry = lxml.etree.Element("Path", name="/etc/bar.conf",
                                   realname="/etc/foo.conf")
        inc = lambda tag, **attrs: \
            ix._include_element(lxml.etree.Element(tag, **attrs),
                                metadata, entry)

        self.assertFalse(inc("Path", name="/etc/bar.conf"))
        self.assertFalse(inc("Path", name="/etc/foo.conf", negate="true"))
        self.assertFalse(inc("Path", name="/etc/foo.conf", negate="tRuE"))
        self.assertTrue(inc("Path", name="/etc/foo.conf"))
        self.assertTrue(inc("Path", name="/etc/foo.conf", negate="false"))
        self.assertTrue(inc("Path", name="/etc/foo.conf", negate="faLSe"))
        self.assertTrue(inc("Path", name="/etc/bar.conf", negate="true"))
        self.assertTrue(inc("Path", name="/etc/bar.conf", negate="tRUe"))


    def test_BindEntry(self):
        ix = self.get_obj()
        entry = lxml.etree.Element("Path", name=self.path)
        metadata = Mock()

        # test with bogus infoxml
        ix.Match = Mock()
        ix.Match.return_value = []
        self.assertRaises(PluginExecutionError,
                          ix.BindEntry, entry, metadata)
        ix.Match.assert_called_with(metadata, entry)

        # test with valid infoxml
        ix.Match.reset_mock()
        ix.Match.return_value = [lxml.etree.Element("Info",
                                                    mode="0600", owner="root")]
        ix.BindEntry(entry, metadata)
        ix.Match.assert_called_with(metadata, entry)
        self.assertItemsEqual(entry.attrib,
                              dict(name=self.path, mode="0600", owner="root"))


class TestXMLDirectoryBacked(TestDirectoryBacked):
    test_obj = XMLDirectoryBacked
    testfiles = ['foo.xml', 'bar/baz.xml', 'plugh.plugh.xml']
    badpaths = ["foo", "foo.txt", "foo.xsd", "xml"]


class TestPrioDir(TestPlugin, TestGenerator, TestXMLDirectoryBacked):
    test_obj = PrioDir

    def setUp(self):
        TestPlugin.setUp(self)
        TestGenerator.setUp(self)
        TestXMLDirectoryBacked.setUp(self)

    def get_obj(self, core=None):
        if core is None:
            core = Mock()

        @patch("%s.%s.add_directory_monitor" %
               (self.test_obj.__module__, self.test_obj.__name__),
               Mock())
        @patchIf(not isinstance(os.makedirs, Mock), "os.makedirs", Mock())
        def inner():
            return self.test_obj(core)

        return inner()

    def test_HandleEvent(self):
        TestXMLDirectoryBacked.test_HandleEvent(self)

        @patch("Bcfg2.Server.Plugin.helpers.XMLDirectoryBacked.HandleEvent",
               Mock())
        def inner():
            pd = self.get_obj()
            test1 = lxml.etree.Element("Test")
            lxml.etree.SubElement(test1, "Path", name="/etc/foo.conf")
            lxml.etree.SubElement(lxml.etree.SubElement(test1,
                                                        "Group", name="foo"),
                                  "Path", name="/etc/bar.conf")

            test2 = lxml.etree.Element("Test")
            lxml.etree.SubElement(test2, "Path", name="/etc/baz.conf")
            lxml.etree.SubElement(test2, "Package", name="quux")
            lxml.etree.SubElement(lxml.etree.SubElement(test2,
                                                        "Group", name="bar"),
                                  "Package", name="xyzzy")
            pd.entries = {"/test1.xml": Mock(xdata=test1),
                          "/test2.xml": Mock(xdata=test2)}
            pd.HandleEvent(Mock())
            self.assertItemsEqual(pd.Entries,
                                  dict(Path={"/etc/foo.conf": pd.BindEntry,
                                             "/etc/bar.conf": pd.BindEntry,
                                             "/etc/baz.conf": pd.BindEntry},
                                       Package={"quux": pd.BindEntry,
                                                "xyzzy": pd.BindEntry}))

        inner()

    def test__matches(self):
        pd = self.get_obj()
        entry = lxml.etree.Element("Test", name="/etc/foo.conf")
        self.assertTrue(pd._matches(entry, Mock(),
                                    lxml.etree.Element("Test",
                                                       name="/etc/foo.conf")))
        self.assertFalse(pd._matches(entry, Mock(),
                                     lxml.etree.Element("Test",
                                                        name="/etc/baz.conf")))

    def test_BindEntry(self):
        pd = self.get_obj()
        children = [lxml.etree.Element("Child", name="child")]
        metadata = Mock()
        pd.entries = dict()

        def reset():
            metadata.reset_mock()
            for src in pd.entries.values():
                src.reset_mock()

        # test with no matches
        self.assertRaises(PluginExecutionError, pd.BindEntry, Mock(), metadata)

        def add_entry(name, data):
            path = os.path.join(pd.data, name)
            pd.entries[path] = Mock()
            pd.entries[path].priority = data.get("priority")
            pd.entries[path].XMLMatch.return_value = data

        test1 = lxml.etree.Element("Rules", priority="10")
        path1 = lxml.etree.SubElement(test1, "Path", name="/etc/foo.conf",
                                      attr="attr1")
        path1.extend(children)
        lxml.etree.SubElement(test1, "Path", name="/etc/bar.conf")
        add_entry('test1.xml', test1)

        test2 = lxml.etree.Element("Rules", priority="20")
        path2 = lxml.etree.SubElement(test2, "Path", name="/etc/bar.conf",
                                      attr="attr1")
        path2.text = "text"
        lxml.etree.SubElement(test2, "Package", name="quux")
        lxml.etree.SubElement(test2, "Package", name="xyzzy")
        add_entry('test2.xml', test2)

        test3 = lxml.etree.Element("Rules", priority="20")
        lxml.etree.SubElement(test3, "Path", name="/etc/baz.conf")
        lxml.etree.SubElement(test3, "Package", name="xyzzy")
        add_entry('test3.xml', test3)

        # test with exactly one match, children
        reset()
        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        pd.BindEntry(entry, metadata)
        self.assertXMLEqual(entry, path1)
        self.assertIsNot(entry, path1)
        for src in pd.entries.values():
            src.XMLMatch.assert_called_with(metadata)

        # test with multiple matches with different priorities, text
        reset()
        entry = lxml.etree.Element("Path", name="/etc/bar.conf")
        pd.BindEntry(entry, metadata)
        self.assertXMLEqual(entry, path2)
        self.assertIsNot(entry, path2)
        for src in pd.entries.values():
            src.XMLMatch.assert_called_with(metadata)

        # test with multiple matches with identical priorities
        reset()
        entry = lxml.etree.Element("Package", name="xyzzy")
        self.assertRaises(PluginExecutionError,
                          pd.BindEntry, entry, metadata)


class TestSpecificity(Bcfg2TestCase):
    test_obj = Specificity

    def get_obj(self, **kwargs):
        return self.test_obj(**kwargs)

    def test_matches(self):
        metadata = Mock()
        metadata.hostname = "foo.example.com"
        metadata.groups = ["group1", "group2"]
        self.assertTrue(self.get_obj(all=True).matches(metadata))
        self.assertTrue(self.get_obj(group="group1").matches(metadata))
        self.assertTrue(self.get_obj(hostname="foo.example.com").matches(metadata))
        self.assertFalse(self.get_obj().matches(metadata))
        self.assertFalse(self.get_obj(group="group3").matches(metadata))
        self.assertFalse(self.get_obj(hostname="bar.example.com").matches(metadata))

    def test__cmp(self):
        specs = [self.get_obj(all=True),
                 self.get_obj(group="group1", prio=10),
                 self.get_obj(group="group1", prio=20),
                 self.get_obj(hostname="foo.example.com")]

        for i in range(len(specs)):
            for j in range(len(specs)):
                if i == j:
                    self.assertEqual(0, specs[i].__cmp__(specs[j]))
                    self.assertEqual(0, specs[j].__cmp__(specs[i]))
                elif i > j:
                    self.assertEqual(-1, specs[i].__cmp__(specs[j]))
                    self.assertEqual(1, specs[j].__cmp__(specs[i]))
                elif i < j:
                    self.assertEqual(1, specs[i].__cmp__(specs[j]))
                    self.assertEqual(-1, specs[j].__cmp__(specs[i]))

    def test_cmp(self):
        """ test __lt__/__gt__/__eq__ """
        specs = [self.get_obj(all=True),
                 self.get_obj(group="group1", prio=10),
                 self.get_obj(group="group1", prio=20),
                 self.get_obj(hostname="foo.example.com")]

        for i in range(len(specs)):
            for j in range(len(specs)):
                if i < j:
                    self.assertGreater(specs[i], specs[j])
                    self.assertLess(specs[j], specs[i])
                    self.assertGreaterEqual(specs[i], specs[j])
                    self.assertLessEqual(specs[j], specs[i])
                elif i == j:
                    self.assertEqual(specs[i], specs[j])
                    self.assertEqual(specs[j], specs[i])
                    self.assertLessEqual(specs[i], specs[j])
                    self.assertGreaterEqual(specs[j], specs[i])
                elif i > j:
                    self.assertLess(specs[i], specs[j])
                    self.assertGreater(specs[j], specs[i])
                    self.assertLessEqual(specs[i], specs[j])
                    self.assertGreaterEqual(specs[j], specs[i])


class TestSpecificData(TestDebuggable):
    test_obj = SpecificData
    path = os.path.join(datastore, "test.txt")

    def setUp(self):
        TestDebuggable.setUp(self)
        set_setup_default("encoding", "utf-8")

    def get_obj(self, name=None, specific=None):
        if name is None:
            name = self.path
        if specific is None:
            specific = Mock()
        return self.test_obj(name, specific)

    def test__init(self):
        pass

    @patch("%s.open" % builtins)
    def test_handle_event(self, mock_open):
        event = Mock()
        event.code2str.return_value = 'deleted'
        sd = self.get_obj()
        sd.handle_event(event)
        self.assertFalse(mock_open.called)
        try:
            self.assertFalse(hasattr(sd, 'data'))
        except AssertionError:
            self.assertIsNone(sd.data)

        event = Mock()
        mock_open.return_value.read.return_value = "test"
        sd.handle_event(event)
        mock_open.assert_called_with(self.path)
        mock_open.return_value.read.assert_any_call()
        self.assertEqual(sd.data, "test")


class TestEntrySet(TestDebuggable):
    test_obj = EntrySet
    # filenames that should be matched successfully by the EntrySet
    # 'specific' regex.  these are filenames alone -- a specificity
    # will be added to these
    basenames = ["test", "test.py", "test with spaces.txt",
                 "test.multiple.dots.py", "test_underscores.and.dots",
                 "really_misleading.G10_test",
                 "name$with*regex(special){chars}",
                 "misleading.H_hostname.test.com"]
    # filenames that do not match any of the basenames (or the
    # basename regex, if applicable)
    bogus_names = ["bogus"]
    # filenames that should be ignored
    ignore = ["foo~", ".#foo", ".foo.swp", ".foo.swx",
              "test.txt.genshi_include", "test.G_foo.genshi_include"]

    def setUp(self):
        TestDebuggable.setUp(self)
        set_setup_default("default_owner")
        set_setup_default("default_group")
        set_setup_default("default_mode")
        set_setup_default("default_secontext")
        set_setup_default("default_important", False)
        set_setup_default("default_paranoid", False)
        set_setup_default("default_sensitive", False)

    def get_obj(self, basename="test", entry_type=MagicMock()):
        return self.test_obj(basename, path, entry_type)

    def test__init(self):
        for basename in self.basenames:
            eset = self.get_obj(basename=basename)
            self.assertIsInstance(eset.specific, re_type)
            self.assertTrue(eset.specific.match(os.path.join(datastore,
                                                             basename)))
            ppath = os.path.join(datastore, "Plugin", basename)
            self.assertTrue(eset.specific.match(ppath))
            self.assertTrue(eset.specific.match(ppath + ".G20_foo"))
            self.assertTrue(eset.specific.match(ppath + ".G1_foo"))
            self.assertTrue(eset.specific.match(ppath + ".G32768_foo"))
            # a group named '_'
            self.assertTrue(eset.specific.match(ppath + ".G10__"))
            self.assertTrue(eset.specific.match(ppath + ".H_hostname"))
            self.assertTrue(eset.specific.match(ppath + ".H_fqdn.subdomain.example.com"))
            self.assertTrue(eset.specific.match(ppath + ".G20_group_with_underscores"))

            self.assertFalse(eset.specific.match(ppath + ".G20_group with spaces"))
            self.assertFalse(eset.specific.match(ppath + ".G_foo"))
            self.assertFalse(eset.specific.match(ppath + ".G_"))
            self.assertFalse(eset.specific.match(ppath + ".G20_"))
            self.assertFalse(eset.specific.match(ppath + ".H_"))

            for bogus in self.bogus_names:
                self.assertFalse(eset.specific.match(os.path.join(datastore,
                                                                  "Plugin",
                                                                  bogus)))

            for ignore in self.ignore:
                self.assertTrue(eset.ignore.match(ignore),
                                "%s should be ignored but wasn't" % ignore)

            self.assertFalse(eset.ignore.match(basename))
            self.assertFalse(eset.ignore.match(basename + ".G20_foo"))
            self.assertFalse(eset.ignore.match(basename + ".G1_foo"))
            self.assertFalse(eset.ignore.match(basename + ".G32768_foo"))
            self.assertFalse(eset.ignore.match(basename + ".G10__"))
            self.assertFalse(eset.ignore.match(basename + ".H_hostname"))
            self.assertFalse(eset.ignore.match(basename + ".H_fqdn.subdomain.example.com"))
            self.assertFalse(eset.ignore.match(basename + ".G20_group_with_underscores"))

    def test_get_matching(self):
        items = {0: Mock(), 1: Mock(), 2: Mock(), 3: Mock(), 4: Mock(),
                 5: Mock()}
        items[0].specific.matches.return_value = False
        items[1].specific.matches.return_value = True
        items[2].specific.matches.return_value = False
        items[3].specific.matches.return_value = False
        items[4].specific.matches.return_value = True
        items[5].specific.matches.return_value = True
        metadata = Mock()
        eset = self.get_obj()
        eset.entries = items
        self.assertItemsEqual(eset.get_matching(metadata),
                              [items[1], items[4], items[5]])
        for i in items.values():
            i.specific.matches.assert_called_with(metadata)

    def test_best_matching(self):
        eset = self.get_obj()
        eset.get_matching = Mock()
        metadata = Mock()
        matching = []

        def reset():
            eset.get_matching.reset_mock()
            metadata.reset_mock()
            for m in matching:
                m.reset_mock()

        def specific(all=False, group=False, prio=None, hostname=False):
            spec = Mock()
            spec.specific = Specificity(all=all, group=group, prio=prio,
                                        hostname=hostname)
            return spec

        self.assertRaises(PluginExecutionError,
                          eset.best_matching, metadata, matching=[])

        reset()
        eset.get_matching.return_value = matching
        self.assertRaises(PluginExecutionError,
                          eset.best_matching, metadata)
        eset.get_matching.assert_called_with(metadata)

        # test with a single file for all
        reset()
        expected = specific(all=True)
        matching.append(expected)
        eset.get_matching.return_value = matching
        self.assertEqual(eset.best_matching(metadata), expected)
        eset.get_matching.assert_called_with(metadata)

        # test with a single group-specific file
        reset()
        expected = specific(group=True, prio=10)
        matching.append(expected)
        eset.get_matching.return_value = matching
        self.assertEqual(eset.best_matching(metadata), expected)
        eset.get_matching.assert_called_with(metadata)

        # test with multiple group-specific files
        reset()
        expected = specific(group=True, prio=20)
        matching.append(expected)
        eset.get_matching.return_value = matching
        self.assertEqual(eset.best_matching(metadata), expected)
        eset.get_matching.assert_called_with(metadata)

        # test with host-specific file
        reset()
        expected = specific(hostname=True)
        matching.append(expected)
        eset.get_matching.return_value = matching
        self.assertEqual(eset.best_matching(metadata), expected)
        eset.get_matching.assert_called_with(metadata)

    def test_handle_event(self):
        eset = self.get_obj()
        eset.entry_init = Mock()
        eset.reset_metadata = Mock()
        eset.update_metadata = Mock()

        def reset():
            eset.update_metadata.reset_mock()
            eset.reset_metadata.reset_mock()
            eset.entry_init.reset_mock()

        fname = "info.xml"
        for evt in ["exists", "created", "changed"]:
            reset()
            event = Mock()
            event.code2str.return_value = evt
            event.filename = fname
            eset.handle_event(event)
            eset.update_metadata.assert_called_with(event)
            self.assertFalse(eset.entry_init.called)
            self.assertFalse(eset.reset_metadata.called)

        reset()
        event = Mock()
        event.code2str.return_value = "deleted"
        event.filename = fname
        eset.handle_event(event)
        eset.reset_metadata.assert_called_with(event)
        self.assertFalse(eset.entry_init.called)
        self.assertFalse(eset.update_metadata.called)

        for evt in ["exists", "created", "changed"]:
            reset()
            event = Mock()
            event.code2str.return_value = evt
            event.filename = "test.txt"
            eset.handle_event(event)
            eset.entry_init.assert_called_with(event)
            self.assertFalse(eset.reset_metadata.called)
            self.assertFalse(eset.update_metadata.called)

        reset()
        entry = Mock()
        eset.entries["test.txt"] = entry
        event = Mock()
        event.code2str.return_value = "changed"
        event.filename = "test.txt"
        eset.handle_event(event)
        entry.handle_event.assert_called_with(event)
        self.assertFalse(eset.entry_init.called)
        self.assertFalse(eset.reset_metadata.called)
        self.assertFalse(eset.update_metadata.called)

        reset()
        entry = Mock()
        eset.entries["test.txt"] = entry
        event = Mock()
        event.code2str.return_value = "deleted"
        event.filename = "test.txt"
        eset.handle_event(event)
        self.assertNotIn("test.txt", eset.entries)

    def test_entry_init(self):
        eset = self.get_obj()
        eset.specificity_from_filename = Mock()

        def reset():
            eset.entry_type.reset_mock()
            eset.specificity_from_filename.reset_mock()

        event = Mock()
        event.code2str.return_value = "created"
        event.filename = "test.txt"
        eset.entry_init(event)
        eset.specificity_from_filename.assert_called_with("test.txt",
                                                          specific=None)
        eset.entry_type.assert_called_with(
            os.path.join(eset.path, "test.txt"),
            eset.specificity_from_filename.return_value)
        eset.entry_type.return_value.handle_event.assert_called_with(event)
        self.assertIn("test.txt", eset.entries)

        # test duplicate add
        reset()
        eset.entry_init(event)
        self.assertFalse(eset.specificity_from_filename.called)
        self.assertFalse(eset.entry_type.called)
        eset.entries["test.txt"].handle_event.assert_called_with(event)

        # test keyword args
        etype = Mock()
        specific = Mock()
        event = Mock()
        event.code2str.return_value = "created"
        event.filename = "test2.txt"
        eset.entry_init(event, entry_type=etype, specific=specific)
        eset.specificity_from_filename.assert_called_with("test2.txt",
                                                          specific=specific)
        etype.assert_called_with(os.path.join(eset.path, "test2.txt"),
                                 eset.specificity_from_filename.return_value)
        etype.return_value.handle_event.assert_called_with(event)
        self.assertIn("test2.txt", eset.entries)

        # test specificity error
        event = Mock()
        event.code2str.return_value = "created"
        event.filename = "test3.txt"
        eset.specificity_from_filename.side_effect = SpecificityError
        eset.entry_init(event)
        eset.specificity_from_filename.assert_called_with("test3.txt",
                                                          specific=None)
        self.assertFalse(eset.entry_type.called)

    @patch("Bcfg2.Server.Plugin.helpers.Specificity")
    def test_specificity_from_filename(self, mock_spec):
        # There's a strange scoping issue in py3k that prevents this
        # test from working as expected on sub-classes of EntrySet.
        # No idea what's going on, but until I can figure it out we
        # skip this test on subclasses
        if inPy3k and self.test_obj != EntrySet:
            return skip("Skipping this test for py3k scoping issues")

        def test(eset, fname, **kwargs):
            mock_spec.reset_mock()
            if "specific" in kwargs:
                specific = kwargs['specific']
                del kwargs['specific']
            else:
                specific = None
            self.assertEqual(eset.specificity_from_filename(fname,
                                                            specific=specific),
                             mock_spec.return_value)
            mock_spec.assert_called_with(**kwargs)

        def fails(eset, fname, specific=None):
            mock_spec.reset_mock()
            self.assertRaises(SpecificityError,
                              eset.specificity_from_filename, fname,
                              specific=specific)

        for basename in self.basenames:
            eset = self.get_obj(basename=basename)
            ppath = os.path.join(datastore, "Plugin", basename)
            test(eset, ppath, all=True)
            test(eset, ppath + ".G20_foo", group="foo", prio=20)
            test(eset, ppath + ".G1_foo", group="foo", prio=1)
            test(eset, ppath + ".G32768_foo", group="foo", prio=32768)
            test(eset, ppath + ".G10__", group="_", prio=10)
            test(eset, ppath + ".H_hostname", hostname="hostname")
            test(eset, ppath + ".H_fqdn.subdomain.example.com",
                 hostname="fqdn.subdomain.example.com")
            test(eset, ppath + ".G20_group_with_underscores",
                 group="group_with_underscores", prio=20)

            for bogus in self.bogus_names:
                fails(eset, bogus)
            fails(eset, ppath + ".G_group with spaces")
            fails(eset, ppath + ".G_foo")
            fails(eset, ppath + ".G_")
            fails(eset, ppath + ".G20_")
            fails(eset, ppath + ".H_")

    @patch("%s.open" % builtins)
    @patch("Bcfg2.Server.Plugin.helpers.InfoXML")
    def test_update_metadata(self, mock_InfoXML, mock_open):
        # There's a strange scoping issue in py3k that prevents this
        # test from working as expected on sub-classes of EntrySet.
        # No idea what's going on, but until I can figure it out we
        # skip this test on subclasses
        if inPy3k and self.test_obj != EntrySet:
            return skip("Skipping this test for py3k scoping issues")

        eset = self.get_obj()

        # add info.xml
        event = Mock()
        event.filename = "info.xml"
        eset.update_metadata(event)
        mock_InfoXML.assert_called_with(os.path.join(eset.path, "info.xml"))
        mock_InfoXML.return_value.HandleEvent.assert_called_with(event)
        self.assertEqual(eset.infoxml, mock_InfoXML.return_value)

        # modify info.xml
        mock_InfoXML.reset_mock()
        eset.update_metadata(event)
        self.assertFalse(mock_InfoXML.called)
        eset.infoxml.HandleEvent.assert_called_with(event)

    @patch("Bcfg2.Server.Plugin.helpers.default_path_metadata")
    def test_reset_metadata(self, mock_default_path_metadata):
        eset = self.get_obj()

        # test info.xml
        event = Mock()
        event.filename = "info.xml"
        eset.infoxml = Mock()
        eset.reset_metadata(event)
        self.assertIsNone(eset.infoxml)

    def test_bind_info_to_entry(self):
        eset = self.get_obj()
        eset.metadata = dict(owner="root", group="root")
        entry = lxml.etree.Element("Path", name="/test")
        metadata = Mock()
        eset.infoxml = None
        eset.bind_info_to_entry(entry, metadata)
        self.assertItemsEqual(entry.attrib,
                              dict(name="/test", owner="root", group="root"))

        entry = lxml.etree.Element("Path", name="/test")
        eset.infoxml = Mock()
        eset.bind_info_to_entry(entry, metadata)
        self.assertItemsEqual(entry.attrib,
                              dict(name="/test", owner="root", group="root"))
        eset.infoxml.BindEntry.assert_called_with(entry, metadata)

    def test_bind_entry(self):
        eset = self.get_obj()
        eset.best_matching = Mock()
        eset.bind_info_to_entry = Mock()

        entry = Mock()
        metadata = Mock()
        eset.bind_entry(entry, metadata)
        eset.bind_info_to_entry.assert_called_with(entry, metadata)
        eset.best_matching.assert_called_with(metadata)
        eset.best_matching.return_value.bind_entry.assert_called_with(entry,
                                                                      metadata)


class TestGroupSpool(TestPlugin, TestGenerator):
    test_obj = GroupSpool

    def setUp(self):
        TestPlugin.setUp(self)
        TestGenerator.setUp(self)
        set_setup_default("encoding", "utf-8")

    def get_obj(self, core=None):
        if core is None:
            core = MagicMock()

        @patch("%s.%s.AddDirectoryMonitor" % (self.test_obj.__module__,
                                              self.test_obj.__name__),
               Mock())
        def inner():
            return TestPlugin.get_obj(self, core=core)

        return inner()

    def test__init(self):
        @patchIf(not isinstance(os.makedirs, Mock), "os.makedirs", Mock())
        @patch("%s.%s.AddDirectoryMonitor" % (self.test_obj.__module__,
                                              self.test_obj.__name__))
        def inner(mock_Add):
            gs = self.test_obj(MagicMock())
            mock_Add.assert_called_with('')
            self.assertItemsEqual(gs.Entries, {gs.entry_type: {}})

        inner()

    @patch("os.path.isdir")
    @patch("os.path.isfile")
    def test_add_entry(self, mock_isfile, mock_isdir):
        gs = self.get_obj()
        gs.es_cls = Mock()
        gs.es_child_cls = Mock()
        gs.event_id = Mock()
        gs.event_path = Mock()
        gs.AddDirectoryMonitor = Mock()

        def reset():
            gs.es_cls.reset_mock()
            gs.es_child_cls.reset_mock()
            gs.AddDirectoryMonitor.reset_mock()
            gs.event_path.reset_mock()
            gs.event_id.reset_mock()
            mock_isfile.reset_mock()
            mock_isdir.reset_mock()

        # directory
        event = Mock()
        event.filename = "foo"
        basedir = "test"
        epath = os.path.join(gs.data, basedir, event.filename)
        ident = os.path.join(basedir, event.filename)
        gs.event_path.return_value = epath
        gs.event_id.return_value = ident
        mock_isdir.return_value = True
        mock_isfile.return_value = False
        gs.add_entry(event)
        gs.AddDirectoryMonitor.assert_called_with(os.path.join("/" + basedir,
                                                               event.filename))
        self.assertNotIn(ident, gs.entries)
        mock_isdir.assert_called_with(epath)

        # file that is not in self.entries
        reset()
        event = Mock()
        event.filename = "foo"
        basedir = "test/foo/"
        epath = os.path.join(gs.data, basedir, event.filename)
        ident = basedir[:-1]
        gs.event_path.return_value = epath
        gs.event_id.return_value = ident
        mock_isdir.return_value = False
        mock_isfile.return_value = True
        gs.add_entry(event)
        self.assertFalse(gs.AddDirectoryMonitor.called)
        gs.es_cls.assert_called_with(gs.filename_pattern,
                                     gs.data + ident,
                                     gs.es_child_cls)
        self.assertIn(ident, gs.entries)
        self.assertEqual(gs.entries[ident], gs.es_cls.return_value)
        self.assertIn(ident, gs.Entries[gs.entry_type])
        self.assertEqual(gs.Entries[gs.entry_type][ident],
                         gs.es_cls.return_value.bind_entry)
        gs.entries[ident].handle_event.assert_called_with(event)
        mock_isfile.assert_called_with(epath)

        # file that is in self.entries
        reset()
        gs.add_entry(event)
        self.assertFalse(gs.AddDirectoryMonitor.called)
        self.assertFalse(gs.es_cls.called)
        gs.entries[ident].handle_event.assert_called_with(event)

    def test_event_path(self):
        gs = self.get_obj()
        gs.handles[1] = "/var/lib/foo/"
        gs.handles[2] = "/etc/foo/"
        gs.handles[3] = "/usr/share/foo/"
        event = Mock()
        event.filename = "foo"
        for i in range(1, 4):
            event.requestID = i
            self.assertEqual(gs.event_path(event),
                             os.path.join(datastore, gs.name,
                                          gs.handles[event.requestID].lstrip('/'),
                                          event.filename))

    @patch("os.path.isdir")
    def test_event_id(self, mock_isdir):
        gs = self.get_obj()
        gs.event_path = Mock()

        def reset():
            gs.event_path.reset_mock()
            mock_isdir.reset_mock()

        gs.handles[1] = "/var/lib/foo/"
        gs.handles[2] = "/etc/foo/"
        gs.handles[3] = "/usr/share/foo/"
        event = Mock()
        event.filename = "foo"
        for i in range(1, 4):
            event.requestID = i
            reset()
            mock_isdir.return_value = True
            self.assertEqual(gs.event_id(event),
                             os.path.join(gs.handles[event.requestID].lstrip('/'),
                                          event.filename))
            mock_isdir.assert_called_with(gs.event_path.return_value)

            reset()
            mock_isdir.return_value = False
            self.assertEqual(gs.event_id(event),
                             gs.handles[event.requestID].rstrip('/'))
            mock_isdir.assert_called_with(gs.event_path.return_value)

    def test_set_debug(self):
        gs = self.get_obj()
        gs.entries = {"/foo": Mock(),
                      "/bar": Mock(),
                      "/baz/quux": Mock()}

        @patch("Bcfg2.Server.Plugin.helpers.Plugin.set_debug")
        def inner(mock_debug):
            gs.set_debug(True)
            mock_debug.assert_called_with(gs, True)
            for entry in gs.entries.values():
                entry.set_debug.assert_called_with(True)

        inner()

        TestPlugin.test_set_debug(self)

    def test_HandleEvent(self):
        gs = self.get_obj()
        gs.entries = {"/foo": Mock(),
                      "/bar": Mock(),
                      "/baz": Mock(),
                      "/baz/quux": Mock()}
        for path in gs.entries.keys():
            gs.Entries[gs.entry_type] = {path: Mock()}
        gs.handles = {1: "/foo/",
                      2: "/bar/",
                      3: "/baz/",
                      4: "/baz/quux"}

        gs.add_entry = Mock()
        gs.event_id = Mock()

        def reset():
            gs.add_entry.reset_mock()
            gs.event_id.reset_mock()
            for entry in gs.entries.values():
                entry.reset_mock()

        # test event creation, changing entry that doesn't exist
        for evt in ["exists", "created", "changed"]:
            reset()
            event = Mock()
            event.filename = "foo"
            event.requestID = 1
            event.code2str.return_value = evt
            gs.HandleEvent(event)
            gs.event_id.assert_called_with(event)
            gs.add_entry.assert_called_with(event)

        # test deleting entry, changing entry that does exist
        for evt in ["changed", "deleted"]:
            reset()
            event = Mock()
            event.filename = "quux"
            event.requestID = 4
            event.code2str.return_value = evt
            gs.event_id.return_value = "/baz/quux"
            gs.HandleEvent(event)
            gs.event_id.assert_called_with(event)
            self.assertIn(gs.event_id.return_value, gs.entries)
            gs.entries[gs.event_id.return_value].handle_event.assert_called_with(event)
            self.assertFalse(gs.add_entry.called)

        # test deleting directory
        reset()
        event = Mock()
        event.filename = "quux"
        event.requestID = 3
        event.code2str.return_value = "deleted"
        gs.event_id.return_value = "/baz/quux"
        gs.HandleEvent(event)
        gs.event_id.assert_called_with(event)
        self.assertNotIn("/baz/quux", gs.entries)
        self.assertNotIn("/baz/quux", gs.Entries[gs.entry_type])
