import os
import re
import sys
import copy
import lxml.etree
import Bcfg2.Server
from Bcfg2.Compat import reduce
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugin.helpers import *

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


def tostring(el):
    return lxml.etree.tostring(el, xml_declaration=False).decode('UTF-8')


class FakeElementTree(lxml.etree._ElementTree):
    xinclude = Mock()


class TestFunctions(Bcfg2TestCase):
    def test_bind_info(self):
        entry = lxml.etree.Element("Path", name="/test")
        metadata = Mock()
        default = dict(test1="test1", test2="test2")
        # test without infoxml
        bind_info(entry, metadata, default=default)
        self.assertItemsEqual(entry.attrib,
                              dict(test1="test1",
                                   test2="test2",
                                   name="/test"))

        # test with bogus infoxml
        entry = lxml.etree.Element("Path", name="/test")
        infoxml = Mock()
        self.assertRaises(PluginExecutionError,
                          bind_info,
                          entry, metadata, infoxml=infoxml)
        infoxml.pnode.Match.assert_called_with(metadata, dict(), entry=entry)

        # test with valid infoxml
        entry = lxml.etree.Element("Path", name="/test")
        infoxml.reset_mock()
        infodata = {None: {"test3": "test3", "test4": "test4"}}
        def infoxml_rv(metadata, rv, entry=None):
            rv['Info'] = infodata
        infoxml.pnode.Match.side_effect = infoxml_rv
        bind_info(entry, metadata, infoxml=infoxml, default=default)
        # mock objects don't properly track the called-with value of
        # arguments whose value is changed by the function, so it
        # thinks Match() was called with the final value of the mdata
        # arg, not the initial value.  makes this test a little less
        # worthwhile, TBH.
        infoxml.pnode.Match.assert_called_with(metadata, dict(Info=infodata),
                                               entry=entry)
        self.assertItemsEqual(entry.attrib,
                              dict(test1="test1",
                                   test2="test2",
                                   test3="test3",
                                   test4="test4",
                                   name="/test"))


class TestDatabaseBacked(TestPlugin):
    test_obj = DatabaseBacked

    @skipUnless(HAS_DJANGO, "Django not found")
    def test__use_db(self):
        core = Mock()
        core.setup.cfp.getboolean.return_value = True
        db = self.get_obj(core)
        self.assertTrue(db._use_db)

        core = Mock()
        core.setup.cfp.getboolean.return_value = False
        db = self.get_obj(core)
        self.assertFalse(db._use_db)

        Bcfg2.Server.Plugin.helpers.HAS_DJANGO = False
        core = Mock()
        db = self.get_obj(core)
        self.assertFalse(db._use_db)

        core = Mock()
        core.setup.cfp.getboolean.return_value = True
        db = self.get_obj(core)
        self.assertFalse(db._use_db)
        Bcfg2.Server.Plugin.helpers.HAS_DJANGO = True


class TestPluginDatabaseModel(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestFileBacked(Bcfg2TestCase):
    test_obj = FileBacked
    path = os.path.join(datastore, "test")

    def get_obj(self, path=None, fam=None):
        if path is None:
            path = self.path
        return self.test_obj(path, fam=fam)

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


class TestDirectoryBacked(Bcfg2TestCase):
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

    def test_child_interface(self):
        """ ensure that the child object has the correct interface """
        self.assertTrue(hasattr(self.test_obj.__child__, "HandleEvent"))

    def get_obj(self, fam=None):
        if fam is None:
            fam = Mock()

        @patch("%s.%s.add_directory_monitor" % (self.test_obj.__module__,
                                                self.test_obj.__name__),
               Mock())
        def inner():
            return self.test_obj(os.path.join(datastore,
                                              self.test_obj.__name__),
                                 fam)
        return inner()

    def test__init(self):
        @patch("%s.%s.add_directory_monitor" % (self.test_obj.__module__,
                                                self.test_obj.__name__))
        def inner(mock_add_monitor):
            db = self.test_obj(datastore, Mock())
            mock_add_monitor.assert_called_with('')

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
            def __init__(self, path, fam, **kwargs):
                Mock.__init__(self, **kwargs)
                self.path = path
                self.fam = fam
                self.HandleEvent = Mock()
        db.__child__ = MockChild

        for path in self.testpaths.values():
            event = Mock()
            db.add_entry(path, event)
            self.assertIn(path, db.entries)
            self.assertEqual(db.entries[path].path,
                             os.path.join(db.data, path))
            self.assertEqual(db.entries[path].fam, db.fam)
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
    path = os.path.join(datastore, "test", "test1.xml")

    def get_obj(self, path=None, fam=None, should_monitor=False):
        if path is None:
            path = self.path
        return self.test_obj(path, fam=fam, should_monitor=should_monitor)

    def test__init(self):
        fam = Mock()
        xfb = self.get_obj()
        self.assertIsNone(xfb.fam)

        xfb = self.get_obj(fam=fam)
        self.assertFalse(fam.AddMonitor.called)

        fam.reset_mock()
        xfb = self.get_obj(fam=fam, should_monitor=True)
        fam.AddMonitor.assert_called_with(self.path, xfb)

    @patch("os.path.exists")
    @patch("lxml.etree.parse")
    def test_follow_xincludes(self, mock_parse, mock_exists):
        xfb = self.get_obj()
        xfb.add_monitor = Mock()

        def reset():
            xfb.add_monitor.reset_mock()
            mock_parse.reset_mock()
            mock_exists.reset_mock()
            xfb.extras = []

        mock_exists.return_value = True
        xdata = dict()
        mock_parse.side_effect = lambda p: xdata[p]

        # basic functionality
        xdata['/test/test2.xml'] = lxml.etree.Element("Test").getroottree()
        xfb._follow_xincludes(xdata=xdata['/test/test2.xml'])
        self.assertFalse(xfb.add_monitor.called)

        if (not hasattr(self.test_obj, "xdata") or
            not isinstance(self.test_obj.xdata, property)):
            # if xdata is settable, test that method of getting data
            # to _follow_xincludes
            reset()
            xfb.xdata = xdata['/test/test2.xml'].getroot()
            xfb._follow_xincludes()
            self.assertFalse(xfb.add_monitor.called)
            xfb.xdata = None

        reset()
        xfb._follow_xincludes(fname="/test/test2.xml")
        self.assertFalse(xfb.add_monitor.called)

        # test one level of xinclude
        xdata[self.path] = lxml.etree.Element("Test").getroottree()
        lxml.etree.SubElement(xdata[self.path].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="/test/test2.xml")
        reset()
        xfb._follow_xincludes(fname=self.path)
        xfb.add_monitor.assert_called_with("/test/test2.xml")
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()])
        mock_exists.assert_called_with("/test/test2.xml")

        reset()
        xfb._follow_xincludes(fname=self.path, xdata=xdata[self.path])
        xfb.add_monitor.assert_called_with("/test/test2.xml")
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()
                               if f != self.path])
        mock_exists.assert_called_with("/test/test2.xml")

        # test two-deep level of xinclude, with some files in another
        # directory
        xdata["/test/test3.xml"] = \
            lxml.etree.Element("Test").getroottree()
        lxml.etree.SubElement(xdata["/test/test3.xml"].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="/test/test_dir/test4.xml")
        xdata["/test/test_dir/test4.xml"] = \
            lxml.etree.Element("Test").getroottree()
        lxml.etree.SubElement(xdata["/test/test_dir/test4.xml"].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="/test/test_dir/test5.xml")
        xdata['/test/test_dir/test5.xml'] = \
            lxml.etree.Element("Test").getroottree()
        xdata['/test/test_dir/test6.xml'] = \
            lxml.etree.Element("Test").getroottree()
        # relative includes
        lxml.etree.SubElement(xdata[self.path].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="test3.xml")
        lxml.etree.SubElement(xdata["/test/test3.xml"].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="test_dir/test6.xml")

        reset()
        xfb._follow_xincludes(fname=self.path)
        self.assertItemsEqual(xfb.add_monitor.call_args_list,
                              [call(f) for f in xdata.keys() if f != self.path])
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()])
        self.assertItemsEqual(mock_exists.call_args_list,
                              [call(f) for f in xdata.keys() if f != self.path])

        reset()
        xfb._follow_xincludes(fname=self.path, xdata=xdata[self.path])
        self.assertItemsEqual(xfb.add_monitor.call_args_list,
                              [call(f) for f in xdata.keys() if f != self.path])
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys() if f != self.path])
        self.assertItemsEqual(mock_exists.call_args_list,
                              [call(f) for f in xdata.keys() if f != self.path])

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

        # syntax error
        xfb.data = "<"
        self.assertRaises(PluginInitError, xfb.Index)

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

    def test_add_monitor(self):
        xfb = self.get_obj()
        xfb.add_monitor("/test/test2.xml")
        self.assertIn("/test/test2.xml", xfb.extras)

        fam = Mock()
        xfb = self.get_obj(fam=fam)
        fam.reset_mock()
        xfb.add_monitor("/test/test3.xml")
        self.assertFalse(fam.AddMonitor.called)
        self.assertIn("/test/test3.xml", xfb.extras)

        fam.reset_mock()
        xfb = self.get_obj(fam=fam, should_monitor=True)
        xfb.add_monitor("/test/test4.xml")
        fam.AddMonitor.assert_called_with("/test/test4.xml", xfb)
        self.assertIn("/test/test4.xml", xfb.extras)


class TestStructFile(TestXMLFileBacked):
    test_obj = StructFile

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

        standalone.append(lxml.etree.SubElement(xdata, "Standalone", name="s1"))

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

        standalone.append(lxml.etree.SubElement(xdata, "Standalone", name="s3"))
        lxml.etree.SubElement(standalone[-1], "SubStandalone", name="sub1")

        children[4] = standalone
        return (xdata, groups, subgroups, children, subchildren, standalone)

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

    @patch("Bcfg2.Server.Plugin.helpers.%s._include_element" %
           test_obj.__name__)
    def test__match(self, mock_include):
        sf = self.get_obj()
        metadata = Mock()
        
        (xdata, groups, subgroups, children, subchildren, standalone) = \
            self._get_test_data()

        mock_include.side_effect = \
            lambda x, _: (x.tag not in ['Client', 'Group'] or
                          x.get("include") == "true")

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

    @patch("Bcfg2.Server.Plugin.helpers.%s._match" % test_obj.__name__)
    def test_Match(self, mock_match):
        sf = self.get_obj()
        metadata = Mock()

        (xdata, groups, subgroups, children, subchildren, standalone) = \
            self._get_test_data()
        sf.entries.extend(copy.deepcopy(xdata).getchildren())

        def match_rv(el, _):
            if el.tag not in ['Client', 'Group']:
                return [el]
            elif x.get("include") == "true":
                return el.getchildren()
            else:
                return []
        mock_match.side_effect = match_rv
        actual = sf.Match(metadata)
        expected = reduce(lambda x, y: x + y,
                          list(children.values()) + list(subgroups.values()))
        self.assertEqual(len(actual), len(expected))
        # easiest way to compare the values is actually to make
        # them into an XML document and let assertXMLEqual compare
        # them
        xactual = lxml.etree.Element("Container")
        xactual.extend(actual)
        xexpected = lxml.etree.Element("Container")
        xexpected.extend(expected)
        self.assertXMLEqual(xactual, xexpected)

    @patch("Bcfg2.Server.Plugin.helpers.%s._include_element" %
           test_obj.__name__)
    def test__xml_match(self, mock_include):
        sf = self.get_obj()
        metadata = Mock()
        
        (xdata, groups, subgroups, children, subchildren, standalone) = \
            self._get_test_data()

        mock_include.side_effect = \
            lambda x, _: (x.tag not in ['Client', 'Group'] or
                          x.get("include") == "true")

        actual = copy.deepcopy(xdata)
        for el in actual.getchildren():
            sf._xml_match(el, metadata)
        expected = lxml.etree.Element(xdata.tag, **dict(xdata.attrib))
        expected.text = xdata.text
        expected.extend(reduce(lambda x, y: x + y,
                               list(children.values()) + list(subchildren.values())))
        expected.extend(standalone)
        self.assertXMLEqual(actual, expected)

    @patch("Bcfg2.Server.Plugin.helpers.%s._xml_match" % test_obj.__name__)
    def test_Match(self, mock_xml_match):
        sf = self.get_obj()
        metadata = Mock()

        (sf.xdata, groups, subgroups, children, subchildren, standalone) = \
            self._get_test_data()

        sf.XMLMatch(metadata)
        actual = []
        for call in mock_xml_match.call_args_list:
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
        self.assertXMLEqual(xactual, xexpected)


class TestINode(Bcfg2TestCase):
    test_obj = INode

    # INode.__init__ and INode._load_children() call each other
    # recursively, which makes this class kind of a nightmare to test.
    # we have to first patch INode._load_children so that we can
    # create an INode object with no children loaded, then we unpatch
    # INode._load_children and patch INode.__init__ so that child
    # objects aren't actually created.  but in order to test things
    # atomically, we do this umpteen times in order to test with
    # different data.  this convenience method makes this a little
    # easier.  fun fun fun.
    @patch("Bcfg2.Server.Plugin.helpers.%s._load_children" %
           test_obj.__name__, Mock())
    def _get_inode(self, data, idict):
        return self.test_obj(data, idict)

    def test_raw_predicates(self):
        metadata = Mock()
        metadata.groups = ["group1", "group2"]
        metadata.hostname = "foo.example.com"
        entry = None

        parent_predicate = lambda m, e: True
        pred = eval(self.test_obj.raw['Client'] % dict(name="foo.example.com"),
                    dict(predicate=parent_predicate))
        self.assertTrue(pred(metadata, entry))
        pred = eval(self.test_obj.raw['Client'] % dict(name="bar.example.com"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))

        pred = eval(self.test_obj.raw['Group'] % dict(name="group1"),
                    dict(predicate=parent_predicate))
        self.assertTrue(pred(metadata, entry))
        pred = eval(self.test_obj.raw['Group'] % dict(name="group3"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))

        pred = eval(self.test_obj.nraw['Client'] % dict(name="foo.example.com"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(self.test_obj.nraw['Client'] % dict(name="bar.example.com"),
                    dict(predicate=parent_predicate))
        self.assertTrue(pred(metadata, entry))

        pred = eval(self.test_obj.nraw['Group'] % dict(name="group1"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(self.test_obj.nraw['Group'] % dict(name="group3"),
                    dict(predicate=parent_predicate))
        self.assertTrue(pred(metadata, entry))

        parent_predicate = lambda m, e: False
        pred = eval(self.test_obj.raw['Client'] % dict(name="foo.example.com"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(self.test_obj.raw['Group'] % dict(name="group1"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(self.test_obj.nraw['Client'] % dict(name="bar.example.com"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(self.test_obj.nraw['Group'] % dict(name="group3"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))

        self.assertItemsEqual(self.test_obj.containers,
                              self.test_obj.raw.keys())
        self.assertItemsEqual(self.test_obj.containers,
                              self.test_obj.nraw.keys())

    @patch("Bcfg2.Server.Plugin.helpers.INode._load_children")
    def test__init(self, mock_load_children):
        data = lxml.etree.Element("Bogus")
        # called with no parent, should not raise an exception; it's a
        # top-level tag in an XML file and so is not expected to be a
        # proper predicate
        INode(data, dict())
        self.assertRaises(PluginExecutionError,
                          INode, data, dict(), Mock())

        data = lxml.etree.Element("Client", name="foo.example.com")
        idict = dict()
        inode = INode(data, idict)
        mock_load_children.assert_called_with(data, idict)
        self.assertTrue(inode.predicate(Mock(), Mock()))

        parent = Mock()
        parent.predicate = lambda m, e: True
        metadata = Mock()
        metadata.groups = ["group1", "group2"]
        metadata.hostname = "foo.example.com"
        entry = None

        # test setting predicate with parent object
        mock_load_children.reset_mock()
        inode = INode(data, idict, parent=parent)
        mock_load_children.assert_called_with(data, idict)
        self.assertTrue(inode.predicate(metadata, entry))

        # test negation
        data = lxml.etree.Element("Client", name="foo.example.com",
                                  negate="true")
        mock_load_children.reset_mock()
        inode = INode(data, idict, parent=parent)
        mock_load_children.assert_called_with(data, idict)
        self.assertFalse(inode.predicate(metadata, entry))

        # test failure of a matching predicate (client names do not match)
        data = lxml.etree.Element("Client", name="foo.example.com")
        metadata.hostname = "bar.example.com"
        mock_load_children.reset_mock()
        inode = INode(data, idict, parent=parent)
        mock_load_children.assert_called_with(data, idict)
        self.assertFalse(inode.predicate(metadata, entry))

        # test that parent predicate is AND'ed in correctly
        parent.predicate = lambda m, e: False
        metadata.hostname = "foo.example.com"
        mock_load_children.reset_mock()
        inode = INode(data, idict, parent=parent)
        mock_load_children.assert_called_with(data, idict)
        self.assertFalse(inode.predicate(metadata, entry))

    def test_load_children(self):
        data = lxml.etree.Element("Parent")
        child1 = lxml.etree.SubElement(data, "Client", name="foo.example.com")
        child2 = lxml.etree.SubElement(data, "Group", name="bar", negate="true")
        idict = dict()

        inode = self._get_inode(data, idict)

        @patch("Bcfg2.Server.Plugin.helpers.%s.__init__" %
               inode.__class__.__name__)
        def inner(mock_init):
            mock_init.return_value = None
            inode._load_children(data, idict)
            self.assertItemsEqual(mock_init.call_args_list,
                                  [call(child1, idict, inode),
                                   call(child2, idict, inode)])
            self.assertEqual(idict, dict())
            self.assertItemsEqual(inode.contents, dict())

        inner()
            
        data = lxml.etree.Element("Parent")
        child1 = lxml.etree.SubElement(data, "Data", name="child1",
                                       attr="some attr")
        child1.text = "text"
        subchild1 = lxml.etree.SubElement(child1, "SubChild", name="subchild")
        child2 = lxml.etree.SubElement(data, "Group", name="bar", negate="true")
        idict = dict()

        inode = self._get_inode(data, idict)
        inode.ignore = []

        @patch("Bcfg2.Server.Plugin.helpers.%s.__init__" %
               inode.__class__.__name__)
        def inner2(mock_init):
            mock_init.return_value = None
            inode._load_children(data, idict)
            mock_init.assert_called_with(child2, idict, inode)
            tag = child1.tag
            name = child1.get("name")
            self.assertEqual(idict, dict(Data=[name]))
            self.assertIn(tag, inode.contents)
            self.assertIn(name, inode.contents[tag])
            self.assertItemsEqual(inode.contents[tag][name],
                                  dict(name=name,
                                       attr=child1.get('attr'),
                                       __text__=child1.text,
                                       __children__=[subchild1]))

        inner2()
        
        # test ignore.  no ignore is set on INode by default, so we
        # have to set one
        old_ignore = copy.copy(self.test_obj.ignore)
        self.test_obj.ignore.append("Data")
        idict = dict()

        inode = self._get_inode(data, idict)

        @patch("Bcfg2.Server.Plugin.helpers.%s.__init__" %
               inode.__class__.__name__)
        def inner3(mock_init):
            mock_init.return_value = None
            inode._load_children(data, idict)
            mock_init.assert_called_with(child2, idict, inode)
            self.assertEqual(idict, dict())
            self.assertItemsEqual(inode.contents, dict())

        inner3()
        self.test_obj.ignore = old_ignore

    def test_Match(self):
        idata = lxml.etree.Element("Parent")
        contents = lxml.etree.SubElement(idata, "Data", name="contents",
                                         attr="some attr")
        child = lxml.etree.SubElement(idata, "Group", name="bar", negate="true")

        inode = INode(idata, dict())
        inode.predicate = Mock()
        inode.predicate.return_value = False

        metadata = Mock()
        metadata.groups = ['foo']
        data = dict()
        entry = child

        inode.Match(metadata, data, entry=child)
        self.assertEqual(data, dict())
        inode.predicate.assert_called_with(metadata, child)

        inode.predicate.reset_mock()
        inode.Match(metadata, data)
        self.assertEqual(data, dict())
        # can't easily compare XML args without the original
        # object, and we're testing that Match() works without an
        # XML object passed in, so...
        self.assertEqual(inode.predicate.call_args[0][0],
                         metadata)
        self.assertXMLEqual(inode.predicate.call_args[0][1],
                            lxml.etree.Element("None"))

        inode.predicate.reset_mock()
        inode.predicate.return_value = True
        inode.Match(metadata, data, entry=child)
        self.assertEqual(data, inode.contents)
        inode.predicate.assert_called_with(metadata, child)
            

class TestInfoNode(TestINode):
    __test__ = True
    test_obj = InfoNode

    def test_raw_predicates(self):
        TestINode.test_raw_predicates(self)
        metadata = Mock()
        entry = lxml.etree.Element("Path", name="/tmp/foo",
                                   realname="/tmp/bar")

        parent_predicate = lambda m, d: True
        pred = eval(self.test_obj.raw['Path'] % dict(name="/tmp/foo"),
                    dict(predicate=parent_predicate))
        self.assertTrue(pred(metadata, entry))
        pred = eval(InfoNode.raw['Path'] % dict(name="/tmp/bar"),
                    dict(predicate=parent_predicate))
        self.assertTrue(pred(metadata, entry))
        pred = eval(InfoNode.raw['Path'] % dict(name="/tmp/bogus"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))

        pred = eval(self.test_obj.nraw['Path'] % dict(name="/tmp/foo"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(InfoNode.nraw['Path'] % dict(name="/tmp/bar"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(InfoNode.nraw['Path'] % dict(name="/tmp/bogus"),
                    dict(predicate=parent_predicate))
        self.assertTrue(pred(metadata, entry))

        parent_predicate = lambda m, d: False
        pred = eval(self.test_obj.raw['Path'] % dict(name="/tmp/foo"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(InfoNode.raw['Path'] % dict(name="/tmp/bar"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))
        pred = eval(InfoNode.nraw['Path'] % dict(name="/tmp/bogus"),
                    dict(predicate=parent_predicate))
        self.assertFalse(pred(metadata, entry))


class TestXMLSrc(TestXMLFileBacked):
    test_obj = XMLSrc

    def test_node_interface(self):
        # ensure that the node object has the necessary interface
        self.assertTrue(hasattr(self.test_obj.__node__, "Match"))

    @patch("%s.open" % builtins)
    def test_HandleEvent(self, mock_open):
        xdata = lxml.etree.Element("Test")
        lxml.etree.SubElement(xdata, "Path", name="path", attr="whatever")

        xsrc = self.get_obj("/test/foo.xml")
        xsrc.__node__ = Mock()
        mock_open.return_value.read.return_value = tostring(xdata)

        if xsrc.__priority_required__:
            # test with no priority at all
            self.assertRaises(PluginExecutionError,
                              xsrc.HandleEvent, Mock())

            # test with bogus priority
            xdata.set("priority", "cow")
            mock_open.return_value.read.return_value = tostring(xdata)
            self.assertRaises(PluginExecutionError,
                               xsrc.HandleEvent, Mock())

            # assign a priority to use in future tests
            xdata.set("priority", "10")
            mock_open.return_value.read.return_value = tostring(xdata)

        mock_open.reset_mock()
        xsrc = self.get_obj("/test/foo.xml")
        xsrc.__node__ = Mock()        
        xsrc.HandleEvent(Mock())
        mock_open.assert_called_with("/test/foo.xml")
        mock_open.return_value.read.assert_any_call()
        self.assertXMLEqual(xsrc.__node__.call_args[0][0], xdata)
        self.assertEqual(xsrc.__node__.call_args[0][1], dict())
        self.assertEqual(xsrc.pnode, xsrc.__node__.return_value)
        self.assertEqual(xsrc.cache, None)
        
    @patch("Bcfg2.Server.Plugin.helpers.XMLSrc.HandleEvent")
    def test_Cache(self, mock_HandleEvent):
        xsrc = self.get_obj("/test/foo.xml")
        metadata = Mock()
        xsrc.Cache(metadata)
        mock_HandleEvent.assert_any_call()
        
        xsrc.pnode = Mock()
        xsrc.Cache(metadata)
        xsrc.pnode.Match.assert_called_with(metadata, xsrc.__cacheobj__())
        self.assertEqual(xsrc.cache[0], metadata)

        xsrc.pnode.reset_mock()
        xsrc.Cache(metadata)
        self.assertFalse(xsrc.pnode.Mock.called)
        self.assertEqual(xsrc.cache[0], metadata)

        xsrc.cache = ("bogus")
        xsrc.Cache(metadata)
        xsrc.pnode.Match.assert_called_with(metadata, xsrc.__cacheobj__())
        self.assertEqual(xsrc.cache[0], metadata)


class TestInfoXML(TestXMLSrc):
    test_obj = InfoXML


class TestXMLDirectoryBacked(TestDirectoryBacked):
    test_obj = XMLDirectoryBacked
    testfiles = ['foo.xml', 'bar/baz.xml', 'plugh.plugh.xml']
    badpaths = ["foo", "foo.txt", "foo.xsd", "xml"]


class TestPrioDir(TestPlugin, TestGenerator, TestXMLDirectoryBacked):
    test_obj = PrioDir

    @patch("Bcfg2.Server.Plugin.helpers.%s.add_directory_monitor" %
           test_obj.__name__,
           Mock())
    def get_obj(self, core=None):
        if core is None:
            core = Mock()
        return self.test_obj(core, datastore)

    def test_HandleEvent(self):
        TestXMLDirectoryBacked.test_HandleEvent(self)

        @patch("Bcfg2.Server.Plugin.helpers.XMLDirectoryBacked.HandleEvent",
               Mock())
        def inner():
            pd = self.get_obj()
            test1 = Mock()
            test1.items = dict(Path=["/etc/foo.conf", "/etc/bar.conf"])
            test2 = Mock()
            test2.items = dict(Path=["/etc/baz.conf"],
                               Package=["quux", "xyzzy"])
            pd.entries = {"/test1.xml": test1,
                          "/test2.xml": test2}
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
        self.assertTrue(pd._matches(lxml.etree.Element("Test",
                                                       name="/etc/foo.conf"),
                                    Mock(),
                                    {"/etc/foo.conf": pd.BindEntry,
                                     "/etc/bar.conf": pd.BindEntry}))
        self.assertFalse(pd._matches(lxml.etree.Element("Test",
                                                        name="/etc/baz.conf"),
                                     Mock(),
                                     {"/etc/foo.conf": pd.BindEntry,
                                      "/etc/bar.conf": pd.BindEntry}))

    def test_BindEntry(self):
        pd = self.get_obj()
        pd.get_attrs = Mock(return_value=dict(test1="test1", test2="test2"))
        entry = lxml.etree.Element("Path", name="/etc/foo.conf", test1="bogus")
        metadata = Mock()
        pd.BindEntry(entry, metadata)
        pd.get_attrs.assert_called_with(entry, metadata)
        self.assertItemsEqual(entry.attrib,
                              dict(name="/etc/foo.conf",
                                   test1="test1", test2="test2"))
        
    def test_get_attrs(self):
        pd = self.get_obj()
        entry = lxml.etree.Element("Path", name="/etc/foo.conf")
        children = [lxml.etree.Element("Child")]
        metadata = Mock()
        pd.entries = dict()

        def reset():
            metadata.reset_mock()
            for src in pd.entries.values():
                src.reset_mock()
                src.cache = None

        # test with no matches
        self.assertRaises(PluginExecutionError,
                          pd.get_attrs, entry, metadata)

        def add_entry(name, data, prio=10):
            path = os.path.join(pd.data, name)
            pd.entries[path] = Mock()
            pd.entries[path].priority = prio
            def do_Cache(metadata):
                pd.entries[path].cache = (metadata, data)
            pd.entries[path].Cache.side_effect = do_Cache

        add_entry('test1.xml',
                  dict(Path={'/etc/foo.conf': dict(attr="attr1",
                                                   __children__=children),
                             '/etc/bar.conf': dict()}))
        add_entry('test2.xml',
                  dict(Path={'/etc/bar.conf': dict(__text__="text",
                                                   attr="attr1")},
                       Package={'quux': dict(),
                                'xyzzy': dict()}),
                  prio=20)
        add_entry('test3.xml',
                  dict(Path={'/etc/baz.conf': dict()},
                       Package={'xyzzy': dict()}),
                  prio=20)

        # test with exactly one match, __children__
        reset()
        self.assertItemsEqual(pd.get_attrs(entry, metadata),
                              dict(attr="attr1"))
        for src in pd.entries.values():
            src.Cache.assert_called_with(metadata)
        self.assertEqual(len(entry.getchildren()), 1)
        self.assertXMLEqual(entry.getchildren()[0], children[0])

        # test with multiple matches with different priorities, __text__
        reset()
        entry = lxml.etree.Element("Path", name="/etc/bar.conf")
        self.assertItemsEqual(pd.get_attrs(entry, metadata),
                              dict(attr="attr1"))
        for src in pd.entries.values():
            src.Cache.assert_called_with(metadata)
        self.assertEqual(entry.text, "text")

        # test with multiple matches with identical priorities
        reset()
        entry = lxml.etree.Element("Package", name="xyzzy")
        self.assertRaises(PluginExecutionError,
                          pd.get_attrs, entry, metadata)
        

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


class TestSpecificData(Bcfg2TestCase):
    test_obj = SpecificData
    path = os.path.join(datastore, "test.txt")

    def get_obj(self, name=None, specific=None, encoding=None):
        if name is None:
            name = self.path
        if specific is None:
            specific = Mock()
        return self.test_obj(name, specific, encoding)

    def test__init(self):
        pass

    @patch("%s.open" % builtins)
    def test_handle_event(self, mock_open):
        event = Mock()
        event.code2str.return_value = 'deleted'
        sd = self.get_obj()
        sd.handle_event(event)
        self.assertFalse(mock_open.called)
        if hasattr(sd, 'data'):
            self.assertIsNone(sd.data)
        else:
            self.assertFalse(hasattr(sd, 'data'))

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
    
    def get_obj(self, basename="test", path=datastore, entry_type=MagicMock(),
                encoding=None):
        return self.test_obj(basename, path, entry_type, encoding)

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
                self.assertTrue(eset.ignore.match(ignore))

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

        for fname in ["info", "info.xml", ":info"]:
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
        eset.entry_type.assert_called_with(os.path.join(eset.path, "test.txt"),
                                           eset.specificity_from_filename.return_value, None)
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
                                 eset.specificity_from_filename.return_value,
                                 None)
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
        
        for fname in [':info', 'info']:
            event = Mock()
            event.filename = fname
            
            idata = ["owner:owner",
                     "group:             GROUP",
                     "mode: 775",
                     "important:     true",
                     "bogus: line"]
            mock_open.return_value.readlines.return_value = idata
            eset.update_metadata(event)
            expected = DEFAULT_FILE_METADATA.copy()
            expected['owner'] = 'owner'
            expected['group'] = 'GROUP'
            expected['mode'] = '0775'
            expected['important'] = 'true'
            self.assertItemsEqual(eset.metadata,
                                  expected)
                                  
    def test_reset_metadata(self):
        eset = self.get_obj()

        # test info.xml
        event = Mock()
        event.filename = "info.xml"
        eset.infoxml = Mock()
        eset.reset_metadata(event)
        self.assertIsNone(eset.infoxml)

        for fname in [':info', 'info']:
            event = Mock()
            event.filename = fname
            eset.metadata = Mock()
            eset.reset_metadata(event)
            self.assertItemsEqual(eset.metadata, DEFAULT_FILE_METADATA)

    @patch("Bcfg2.Server.Plugin.helpers.bind_info")
    def test_bind_info_to_entry(self, mock_bind_info):
        # There's a strange scoping issue in py3k that prevents this
        # test from working as expected on sub-classes of EntrySet.
        # No idea what's going on, but until I can figure it out we
        # skip this test on subclasses
        if inPy3k and self.test_obj != EntrySet:
            return skip("Skipping this test for py3k scoping issues")

        eset = self.get_obj()
        entry = Mock()
        metadata = Mock()
        eset.bind_info_to_entry(entry, metadata)
        mock_bind_info.assert_called_with(entry, metadata,
                                          infoxml=eset.infoxml,
                                          default=eset.metadata)

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

    def get_obj(self, core=None):
        if core is None:
            core = MagicMock()
            core.setup = MagicMock()
        else:
            try:
                core.setup['encoding']
            except TypeError:
                core.setup.__getitem__ = MagicMock()

        @patch("%s.%s.AddDirectoryMonitor" % (self.test_obj.__module__,
                                              self.test_obj.__name__),
               Mock())
        def inner():
            return TestPlugin.get_obj(self, core=core)

        return inner()

    def test__init(self):
        @patch("%s.%s.AddDirectoryMonitor" % (self.test_obj.__module__,
                                              self.test_obj.__name__))
        def inner(mock_Add):
            gs = self.test_obj(MagicMock(), datastore)
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
                                     gs.es_child_cls,
                                     gs.encoding)
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

    def test_toggle_debug(self):
        gs = self.get_obj()
        gs.entries = {"/foo": Mock(),
                      "/bar": Mock(),
                      "/baz/quux": Mock()}
        
        @patch("Bcfg2.Server.Plugin.helpers.Plugin.toggle_debug")
        def inner(mock_debug):
            gs.toggle_debug()
            mock_debug.assert_called_with(gs)
            for entry in gs.entries.values():
                entry.toggle_debug.assert_any_call()
        
        inner()
        
        TestPlugin.test_toggle_debug(self)

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



