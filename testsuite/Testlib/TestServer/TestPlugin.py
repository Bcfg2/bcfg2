import os
import copy
import logging
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugin import *
import Bcfg2.Server

datastore = '/'

def call(*args, **kwargs):
    """ the Mock call object is a fairly recent addition, but it's
    very very useful, so we create our own function to create Mock
    calls """
    return (args, kwargs)

class Bcfg2TestCase(unittest.TestCase):
    def assertXMLEqual(self, el1, el2, msg=None):
        self.assertEqual(el1.tag, el2.tag, msg=msg)
        self.assertEqual(el1.text, el2.text, msg=msg)
        self.assertItemsEqual(el1.attrib, el2.attrib, msg=msg)
        self.assertEqual(len(el1.getchildren()),
                         len(el2.getchildren()))
        for child1 in el1.getchildren():
            cname = child1.get("name")
            self.assertIsNotNone(cname,
                                 msg="Element %s has no 'name' attribute" %
                                 child1.tag)
            children2 = el2.xpath("*[@name='%s']" % cname)
            self.assertEqual(len(children2), 1,
                             msg="More than one element named %s" % cname)
            self.assertXMLEqual(child1, children2[0], msg=msg)        


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


class TestPluginInitError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestPluginExecutionError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestDebuggable(Bcfg2TestCase):
    def test__init(self):
        d = Debuggable()
        self.assertIsInstance(d.logger, logging.Logger)
        self.assertFalse(d.debug_flag)

    @patch("Bcfg2.Server.Plugin.Debuggable.debug_log")
    def test_toggle_debug(self, mock_debug):
        d = Debuggable()
        orig = d.debug_flag
        d.toggle_debug()
        self.assertNotEqual(orig, d.debug_flag)
        self.assertTrue(mock_debug.called)

        mock_debug.reset_mock()

        changed = d.debug_flag
        d.toggle_debug()
        self.assertNotEqual(changed, d.debug_flag)
        self.assertEqual(orig, d.debug_flag)
        self.assertTrue(mock_debug.called)

    def test_debug_log(self):
        d = Debuggable()
        d.logger = Mock()
        d.debug_flag = False
        d.debug_log("test")
        self.assertFalse(d.logger.error.called)
        
        d.logger.reset_mock()
        d.debug_log("test", flag=True)
        self.assertTrue(d.logger.error.called)

        d.logger.reset_mock()
        d.debug_flag = True
        d.debug_log("test")
        self.assertTrue(d.logger.error.called)


class TestPlugin(TestDebuggable):
    def test__init(self):
        core = Mock()
        p = Plugin(core, datastore)
        self.assertEqual(p.data, os.path.join(datastore, p.name))
        self.assertEqual(p.core, core)
        self.assertIsInstance(p, Debuggable)

    @patch("os.makedirs")
    def test_init_repo(self, mock_makedirs):
        Plugin.init_repo(datastore)
        mock_makedirs.assert_called_with(os.path.join(datastore, Plugin.name))


class TestDatabaseBacked(TestPlugin):
    @unittest.skipUnless(has_django, "Django not found")
    def test__use_db(self):
        core = Mock()
        core.setup.cfp.getboolean.return_value = True
        db = DatabaseBacked(core, datastore)
        self.assertTrue(db._use_db)

        core = Mock()
        core.setup.cfp.getboolean.return_value = False
        db = DatabaseBacked(core, datastore)
        self.assertFalse(db._use_db)
        
        Bcfg2.Server.Plugin.has_django = False
        core = Mock()
        db = DatabaseBacked(core, datastore)
        self.assertFalse(db._use_db)

        core = Mock()
        core.setup.cfp.getboolean.return_value = True
        db = DatabaseBacked(core, datastore)
        self.assertFalse(db._use_db)
        Bcfg2.Server.Plugin.has_django = True


class TestPluginDatabaseModel(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestGenerator(Bcfg2TestCase):
    def test_HandleEntry(self):
        g = Generator()
        self.assertRaises(NotImplementedError,
                          g.HandleEntry, None, None)


class TestStructure(Bcfg2TestCase):
    def test_BuildStructures(self):
        s = Structure()
        self.assertRaises(NotImplementedError,
                          s.BuildStructures, None)


class TestMetadata(Bcfg2TestCase):
    def test_get_initial_metadata(self):
        m = Metadata()
        self.assertRaises(NotImplementedError,
                          m.get_initial_metadata, None)

    def test_merge_additional_data(self):
        m = Metadata()
        self.assertRaises(NotImplementedError,
                          m.merge_additional_data, None, None, None)

    def test_merge_additional_groups(self):
        m = Metadata()
        self.assertRaises(NotImplementedError,
                          m.merge_additional_groups, None, None)


class TestConnector(Bcfg2TestCase):
    """ placeholder """
    pass


class TestProbing(Bcfg2TestCase):
    """ placeholder """
    pass


class TestStatistics(TestPlugin):
    """ placeholder """
    pass


class TestThreadedStatistics(TestStatistics):
    data = [("foo.example.com", "<foo/>"),
            ("bar.example.com", "<bar/>")]

    @patch("threading.Thread.start")
    def test__init(self, mock_start):
        core = Mock()
        ts = ThreadedStatistics(core, datastore)
        mock_start.assert_any_call()

    @patch("__builtin__.open")
    @patch("Bcfg2.Server.Plugin.ThreadedStatistics.run", Mock())
    def test_save(self, mock_open):
        core = Mock()
        ts = ThreadedStatistics(core, datastore)
        queue = Mock()
        queue.empty = Mock(side_effect=Empty)
        ts.work_queue = queue

        mock_open.side_effect = OSError
        # test that save does _not_ raise an exception even when
        # everything goes pear-shaped
        ts.save()
        queue.empty.assert_any_call()
        mock_open.assert_called_with(ts.pending_file, 'w')

        queue.reset_mock()
        mock_open.reset_mock()

        queue.data = []
        for hostname, xml in self.data:
            md = Mock()
            md.hostname = hostname
            queue.data.append((md, lxml.etree.XML(xml)))
        queue.empty.side_effect = lambda: len(queue.data) == 0
        queue.get_nowait = Mock(side_effect=lambda: queue.data.pop())
        mock_open.side_effect = None

        # oh, the joy of working around different package names in
        # py3k...
        with patch("%s.dump" % cPickle.__name__) as mock_dump:
            ts.save()
            queue.empty.assert_any_call()
            queue.get_nowait.assert_any_call()
            mock_open.assert_called_with(ts.pending_file, 'w')
            mock_open.return_value.close.assert_any_call()
            # the order of the queue data gets changed, so we have to
            # verify this call in an ugly way
            self.assertItemsEqual(mock_dump.call_args[0][0], self.data)
            self.assertEqual(mock_dump.call_args[0][1], mock_open.return_value)
        
    @patch("os.unlink")
    @patch("os.path.exists")
    @patch("__builtin__.open")
    @patch("lxml.etree.XML")
    @patch("Bcfg2.Server.Plugin.ThreadedStatistics.run", Mock())
    def test_load(self, mock_XML, mock_open, mock_exists, mock_unlink):
        core = Mock()
        core.terminate.isSet.return_value = False
        ts = ThreadedStatistics(core, datastore)
        
        with patch("%s.load" % cPickle.__name__) as mock_load:
            ts.work_queue = Mock()
            ts.work_queue.data = []
            def reset():
                core.reset_mock()
                mock_open.reset_mock()
                mock_exists.reset_mock()
                mock_unlink.reset_mock()
                mock_load.reset_mock()
                mock_XML.reset_mock()
                ts.work_queue.reset_mock()
                ts.work_queue.data = []

            mock_exists.return_value = False
            self.assertTrue(ts.load())
            mock_exists.assert_called_with(ts.pending_file)

            reset()
            mock_exists.return_value = True
            mock_open.side_effect = OSError
            self.assertFalse(ts.load())
            mock_exists.assert_called_with(ts.pending_file)
            mock_open.assert_called_with(ts.pending_file, 'r')

            reset()
            mock_open.side_effect = None
            mock_load.return_value = self.data
            ts.work_queue.put_nowait.side_effect = Full
            self.assertTrue(ts.load())
            mock_exists.assert_called_with(ts.pending_file)
            mock_open.assert_called_with(ts.pending_file, 'r')
            mock_open.return_value.close.assert_any_call()
            mock_load.assert_called_with(mock_open.return_value)

            reset()
            core.build_metadata.side_effect = lambda x: x
            mock_XML.side_effect = lambda x, parser=None: x
            ts.work_queue.put_nowait.side_effect = None
            self.assertTrue(ts.load())
            mock_exists.assert_called_with(ts.pending_file)
            mock_open.assert_called_with(ts.pending_file, 'r')
            mock_open.return_value.close.assert_any_call()
            mock_load.assert_called_with(mock_open.return_value)
            self.assertItemsEqual(mock_XML.call_args_list,
                                  [call(x, parser=Bcfg2.Server.XMLParser)
                                   for h, x in self.data])
            self.assertItemsEqual(ts.work_queue.put_nowait.call_args_list,
                                  [call((h, x)) for h, x in self.data])
            mock_unlink.assert_called_with(ts.pending_file)

    @patch("threading.Thread.start", Mock())
    @patch("Bcfg2.Server.Plugin.ThreadedStatistics.load")
    @patch("Bcfg2.Server.Plugin.ThreadedStatistics.save")
    @patch("Bcfg2.Server.Plugin.ThreadedStatistics.handle_statistic")
    def test_run(self, mock_handle, mock_save, mock_load):
        core = Mock()
        ts = ThreadedStatistics(core, datastore)
        mock_load.return_value = True
        ts.work_queue = Mock()

        def reset():
            mock_handle.reset_mock()
            mock_save.reset_mock()
            mock_load.reset_mock()
            core.reset_mock()
            ts.work_queue.reset_mock()
            ts.work_queue.data = self.data[:]
            ts.work_queue.get_calls = 0

        reset()

        def get_rv(**kwargs):
            ts.work_queue.get_calls += 1
            try:
                return ts.work_queue.data.pop()
            except:
                raise Empty
        ts.work_queue.get.side_effect = get_rv
        def terminate_isset():
            # this lets the loop go on a few iterations with an empty
            # queue to test that it doesn't error out
            return ts.work_queue.get_calls > 3
        core.terminate.isSet.side_effect = terminate_isset

        ts.run()
        mock_load.assert_any_call()
        self.assertGreaterEqual(ts.work_queue.get.call_count, len(self.data))
        self.assertItemsEqual(mock_handle.call_args_list,
                              [call(h, x) for h, x in self.data])
        mock_save.assert_any_call()

    @patch("copy.copy", Mock(side_effect=lambda x: x))
    @patch("Bcfg2.Server.Plugin.ThreadedStatistics.run", Mock())
    def test_process_statistics(self):
        core = Mock()
        ts = ThreadedStatistics(core, datastore)
        ts.work_queue = Mock()
        ts.process_statistics(*self.data[0])
        ts.work_queue.put_nowait.assert_called_with(self.data[0])

        ts.work_queue.reset_mock()
        ts.work_queue.put_nowait.side_effect = Full
        # test that no exception is thrown
        ts.process_statistics(*self.data[0])
        

class TestPullSource(Bcfg2TestCase):
    def test_GetCurrentEntry(self):
        ps = PullSource()
        self.assertRaises(NotImplementedError,
                          ps.GetCurrentEntry, None, None, None)


class TestPullTarget(Bcfg2TestCase):
    def test_AcceptChoices(self):
        pt = PullTarget()
        self.assertRaises(NotImplementedError,
                          pt.AcceptChoices, None, None)

    def test_AcceptPullData(self):
        pt = PullTarget()
        self.assertRaises(NotImplementedError,
                          pt.AcceptPullData, None, None, None)


class TestDecision(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestValidationError(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestStructureValidator(Bcfg2TestCase):
    def test_validate_structures(self):
        sv = StructureValidator()
        self.assertRaises(NotImplementedError,
                          sv.validate_structures, None, None)


class TestGoalValidator(Bcfg2TestCase):
    def test_validate_goals(self):
        gv = GoalValidator()
        self.assertRaises(NotImplementedError,
                          gv.validate_goals, None, None)


class TestVersion(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestClientRunHooks(Bcfg2TestCase):
    """ placeholder for future tests """
    pass


class TestFileBacked(Bcfg2TestCase):
    @patch("__builtin__.open")
    @patch("Bcfg2.Server.Plugin.FileBacked.Index")
    def test_HandleEvent(self, mock_Index, mock_open):
        path = "/test"
        fb = FileBacked(path)

        def reset():
            mock_Index.reset_mock()
            mock_open.reset_mock()

        for evt in ["exists", "changed", "created"]:
            reset()
            event = Mock()
            event.code2str.return_value = evt
            fb.HandleEvent(event)
            mock_open.assert_called_with(path)
            mock_open.return_value.read.assert_any_call()
            mock_Index.assert_any_call()

        reset()
        event = Mock()
        event.code2str.return_value = "endExist"
        fb.HandleEvent(event)
        self.assertFalse(mock_open.called)
        self.assertFalse(mock_Index.called)


class TestDirectoryBacked(Bcfg2TestCase):
    testpaths = {1: '',
                 2: '/foo',
                 3: '/foo/bar',
                 4: '/foo/bar/baz',
                 5: 'quux',
                 6: 'xyzzy/',
                 7: 'xyzzy/plugh/'}

    @patch("Bcfg2.Server.Plugin.DirectoryBacked.add_directory_monitor", Mock())
    def get_obj(self, fam=None):
        if fam is None:
            fam = Mock()
        return DirectoryBacked(datastore, fam)

    @patch("Bcfg2.Server.Plugin.DirectoryBacked.add_directory_monitor")
    def test__init(self, mock_add_monitor):
        db = DirectoryBacked(datastore, Mock())
        mock_add_monitor.assert_called_with('')

    def test__getitem(self):
        db = self.get_obj()
        db.entries.update(dict(a=1, b=2, c=3))
        self.assertEqual(db['a'], 1)
        self.assertEqual(db['b'], 2)
        with self.assertRaises(KeyError):
            db['d']

    def test__iter(self):
        db = self.get_obj()
        db.entries.update(dict(a=1, b=2, c=3))
        self.assertEqual([i for i in db],
                         [i for i in db.entries.items()])

    @patch("os.path.isdir")
    def test_add_directory_monitor(self, mock_isdir):
        fam = Mock()
        fam.rv = 0
        db = self.get_obj(fam=fam)
        
        def reset():
            fam.rv += 1
            fam.AddMonitor.return_value = fam.rv
            fam.reset_mock()
            mock_isdir.reset_mock()

        mock_isdir.return_value = True
        for path in self.testpaths.values():
            reset()
            db.add_directory_monitor(path)
            fam.AddMonitor.assert_called_with(os.path.join(datastore,
                                                           path),
                                              db)
            self.assertIn(fam.rv, db.handles)
            self.assertEqual(db.handles[fam.rv], path)

        reset()
        # test duplicate adds
        for path in self.testpaths.values():
            reset()
            db.add_directory_monitor(path)
            self.assertFalse(fam.AddMonitor.called)

        reset()
        mock_isdir.return_value = False
        db.add_directory_monitor('bogus')
        self.assertFalse(fam.AddMonitor.called)
        self.assertNotIn(fam.rv, db.handles)

    def test_add_entry(self):
        fam = Mock()
        db = self.get_obj(fam=fam)
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
                             os.path.join(datastore, path))
            self.assertEqual(db.entries[path].fam, fam)
            db.entries[path].HandleEvent.assert_called_with(event)

    @patch("os.path.isdir")
    @patch("Bcfg2.Server.Plugin.DirectoryBacked.add_entry")
    @patch("Bcfg2.Server.Plugin.DirectoryBacked.add_directory_monitor")
    def test_HandleEvent(self, mock_add_monitor, mock_add_entry, mock_isdir):
        fam = Mock()
        db = self.get_obj(fam=fam)
        # a path with a leading / should never get into
        # DirectoryBacked.handles, so strip that test case
        for rid, path in self.testpaths.items():
            path = path.lstrip('/')
            db.handles[rid] = path

        def reset():
            fam.reset_mock()
            mock_isdir.reset_mock()
            mock_add_entry.reset_mock()
            mock_add_monitor.reset_mock()

        def get_event(filename, action, requestID):
            event = Mock()
            event.code2str.return_value = action
            event.filename = filename
            event.requestID = requestID
            return event

        # test that events on paths that aren't handled fail properly
        reset()
        event = get_event('/foo', 'created', max(self.testpaths.keys()) + 1)
        db.HandleEvent(event)
        self.assertFalse(mock_add_monitor.called)
        self.assertFalse(mock_add_entry.called)

        for req_id, path in self.testpaths.items():
            # a path with a leading / should never get into
            # DirectoryBacked.handles, so strip that test case
            path = path.lstrip('/')
            basepath = os.path.join(datastore, path)
            for fname in ['foo', 'bar/baz.txt', 'plugh.py']:
                relpath = os.path.join(path, fname)
                abspath = os.path.join(basepath, fname)

                # test endExist does nothing
                reset()
                event = get_event(fname, 'endExist', req_id)
                db.HandleEvent(event)
                self.assertFalse(mock_add_monitor.called)
                self.assertFalse(mock_add_entry.called)

                mock_isdir.return_value = True
                for evt in ["created", "exists", "changed"]:
                    # test that creating or changing a directory works
                    reset()
                    event = get_event(fname, evt, req_id)
                    db.HandleEvent(event)
                    mock_add_monitor.assert_called_with(relpath)
                    self.assertFalse(mock_add_entry.called)

                mock_isdir.return_value = False
                for evt in ["created", "exists"]:
                    # test that creating a file works
                    reset()
                    event = get_event(fname, evt, req_id)
                    db.HandleEvent(event)
                    mock_add_entry.assert_called_with(relpath, event)
                    self.assertFalse(mock_add_monitor.called)
                    db.entries[relpath] = Mock()

                # test that changing a file that already exists works
                reset()
                event = get_event(fname, "changed", req_id)
                db.HandleEvent(event)
                db.entries[relpath].HandleEvent.assert_called_with(event)
                self.assertFalse(mock_add_monitor.called)
                self.assertFalse(mock_add_entry.called)

                # test that deleting an entry works
                reset()
                event = get_event(fname, "deleted", req_id)
                db.HandleEvent(event)
                self.assertNotIn(relpath, db.entries)
                
                # test that changing a file that doesn't exist works
                reset()
                event = get_event(fname, "changed", req_id)
                db.HandleEvent(event)
                mock_add_entry.assert_called_with(relpath, event)
                self.assertFalse(mock_add_monitor.called)
                db.entries[relpath] = Mock()
            
        # test that deleting a directory works. this is a little
        # strange because the _parent_ directory has to handle the
        # deletion
        reset()
        event = get_event('quux', "deleted", 1)
        db.HandleEvent(event)
        for key in db.entries.keys():
            self.assertFalse(key.startswith('quux'))
                

class TestXMLFileBacked(TestFileBacked):
    def test__init(self):
        fam = Mock()
        fname = "/test"
        xfb = XMLFileBacked(fname)
        self.assertIsNone(xfb.fam)

        xfb = XMLFileBacked(fname, fam=fam)
        self.assertFalse(fam.AddMonitor.called)

        fam.reset_mock()
        xfb = XMLFileBacked(fname, fam=fam, should_monitor=True)
        fam.AddMonitor.assert_called_with(fname, xfb)

    @patch("os.path.exists")
    @patch("lxml.etree.parse")
    @patch("Bcfg2.Server.Plugin.XMLFileBacked.add_monitor")
    def test_follow_xincludes(self, mock_add_monitor, mock_parse, mock_exists):
        fname = "/test/test1.xml"
        xfb = XMLFileBacked(fname)
        
        def reset():
            mock_add_monitor.reset_mock()
            mock_parse.reset_mock()
            mock_exists.reset_mock()
            xfb.extras = []

        mock_exists.return_value = True
        xdata = dict()
        mock_parse.side_effect = lambda p: xdata[p]

        # basic functionality
        xdata['/test/test2.xml'] = lxml.etree.Element("Test").getroottree()
        xfb._follow_xincludes(xdata=xdata['/test/test2.xml'])
        self.assertFalse(mock_add_monitor.called)

        reset()
        xfb.xdata = xdata['/test/test2.xml'].getroot()
        xfb._follow_xincludes()
        self.assertFalse(mock_add_monitor.called)
        xfb.xdata = None

        reset()
        xfb._follow_xincludes(fname="/test/test2.xml")
        self.assertFalse(mock_add_monitor.called)

        # test one level of xinclude
        xdata[fname] = lxml.etree.Element("Test").getroottree()
        lxml.etree.SubElement(xdata[fname].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="/test/test2.xml")
        reset()
        xfb._follow_xincludes(fname=fname)
        mock_add_monitor.assert_called_with("/test/test2.xml")
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()])
        mock_exists.assert_called_with("/test/test2.xml")

        reset()
        xfb._follow_xincludes(xdata=xdata[fname])
        mock_add_monitor.assert_called_with("/test/test2.xml")
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()
                               if f != fname])
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
        lxml.etree.SubElement(xdata[fname].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="test3.xml")
        lxml.etree.SubElement(xdata["/test/test3.xml"].getroot(),
                              Bcfg2.Server.XI_NAMESPACE + "include",
                              href="test_dir/test6.xml")

        reset()
        xfb._follow_xincludes(fname=fname)
        self.assertItemsEqual(mock_add_monitor.call_args_list,
                              [call(f) for f in xdata.keys() if f != fname])
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys()])
        self.assertItemsEqual(mock_exists.call_args_list,
                              [call(f) for f in xdata.keys() if f != fname])

        reset()
        xfb._follow_xincludes(xdata=xdata[fname])
        self.assertItemsEqual(mock_add_monitor.call_args_list,
                              [call(f) for f in xdata.keys() if f != fname])
        self.assertItemsEqual(mock_parse.call_args_list,
                              [call(f) for f in xdata.keys() if f != fname])
        self.assertItemsEqual(mock_exists.call_args_list,
                              [call(f) for f in xdata.keys() if f != fname])

    @patch("lxml.etree._ElementTree", FakeElementTree)
    @patch("Bcfg2.Server.Plugin.XMLFileBacked._follow_xincludes")
    def test_Index(self, mock_follow):
        fname = "/test/test1.xml"
        xfb = XMLFileBacked(fname)
        
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
        xfb.data = lxml.etree.tostring(xdata)
        xfb.Index()
        mock_follow.assert_any_call()
        self.assertEqual(xfb.xdata.base, fname)
        self.assertItemsEqual([lxml.etree.tostring(e) for e in xfb.entries],
                              [lxml.etree.tostring(e) for e in children])

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

        xfb.data = lxml.etree.tostring(xdata)
        xfb.Index()
        mock_follow.assert_any_call()
        FakeElementTree.xinclude.assert_any_call
        self.assertEqual(xfb.xdata.base, fname)
        self.assertItemsEqual([lxml.etree.tostring(e) for e in xfb.entries],
                              [lxml.etree.tostring(e) for e in children])

    def test_add_monitor(self):
        fname = "/test/test1.xml"
        xfb = XMLFileBacked(fname)
        xfb.add_monitor("/test/test2.xml")
        self.assertIn("/test/test2.xml", xfb.extras)

        fam = Mock()
        xfb = XMLFileBacked(fname, fam=fam)
        fam.reset_mock()
        xfb.add_monitor("/test/test3.xml")
        self.assertFalse(fam.AddMonitor.called)
        self.assertIn("/test/test3.xml", xfb.extras)

        fam.reset_mock()
        xfb = XMLFileBacked(fname, fam=fam, should_monitor=True)
        xfb.add_monitor("/test/test4.xml")
        fam.AddMonitor.assert_called_with("/test/test4.xml", xfb)
        self.assertIn("/test/test4.xml", xfb.extras)


class TestStructFile(TestXMLFileBacked):
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
        sf = StructFile("/test/test.xml")
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

    @patch("Bcfg2.Server.Plugin.StructFile._include_element")
    def test__match(self, mock_include):
        sf = StructFile("/test/test.xml")
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

    @patch("Bcfg2.Server.Plugin.StructFile._match")
    def test_Match(self, mock_match):
        sf = StructFile("/test/test.xml")
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
                          children.values() + subgroups.values())
        self.assertEqual(len(actual), len(expected))
        # easiest way to compare the values is actually to make
        # them into an XML document and let assertXMLEqual compare
        # them
        xactual = lxml.etree.Element("Container")
        xactual.extend(actual)
        xexpected = lxml.etree.Element("Container")
        xexpected.extend(expected)
        self.assertXMLEqual(xactual, xexpected)

    @patch("Bcfg2.Server.Plugin.StructFile._include_element")
    def test__xml_match(self, mock_include):
        sf = StructFile("/test/test.xml")
        metadata = Mock()
        
        (xdata, groups, subgroups, children, subchildren, standalone) = \
            self._get_test_data()

        mock_include.side_effect = \
            lambda x, _: (x.tag not in ['Client', 'Group'] or
                          x.get("include") == "true")

        actual = copy.deepcopy(xdata)
        for el in actual.getchildren():
            sf._xml_match(el, metadata)
        expected = lxml.etree.Element(xdata.tag, **xdata.attrib)
        expected.text = xdata.text
        expected.extend(reduce(lambda x, y: x + y,
                               children.values() + subchildren.values()))
        expected.extend(standalone)
        self.assertXMLEqual(actual, expected)

    @patch("Bcfg2.Server.Plugin.StructFile._xml_match")
    def test_Match(self, mock_xml_match):
        sf = StructFile("/test/test.xml")
        metadata = Mock()

        (sf.xdata, groups, subgroups, children, subchildren, standalone) = \
            self._get_test_data()

        sf.XMLMatch(metadata)
        actual = []
        for call in mock_xml_match.call_args_list:
            actual.append(call[0][0])
            self.assertEqual(call[0][1], metadata)
        expected = groups.values() + standalone
        # easiest way to compare the values is actually to make
        # them into an XML document and let assertXMLEqual compare
        # them
        xactual = lxml.etree.Element("Container")
        xactual.extend(actual)
        xexpected = lxml.etree.Element("Container")
        xexpected.extend(expected)
        self.assertXMLEqual(xactual, xexpected)


# INode.__init__ and INode._load_children() call each other
# recursively, which makes this class kind of a nightmare to test.  we
# have to first patch INode._load_children so that we can create an
# INode object with no children loaded, then we unpatch
# INode._load_children and patch INode.__init__ so that child objects
# aren't actually created.  but in order to test things atomically, we
# do this umpteen times in order to test with different data.  we
# write our own context manager to make this a little easier.  fun fun
# fun.
class patch_inode(object):
    def __init__(self, test_obj, data, idict):
        self.test_obj = test_obj
        self.data = data
        self.idict = idict
        self.patch_init = None
        self.inode = None

    def __enter__(self):
        with patch("Bcfg2.Server.Plugin.%s._load_children" %
                   self.test_obj.__name__):
            self.inode = self.test_obj(self.data, self.idict)
        self.patch_init = patch("Bcfg2.Server.Plugin.%s.__init__" %
                                self.inode.__class__.__name__,
                                new=Mock(return_value=None))
        self.patch_init.start()
        self.inode._load_children(self.data, self.idict)
        return (self.inode, self.patch_init.new)

    def __exit__(self, type, value, traceback):
        self.patch_init.stop()
        del self.patch_init
        del self.inode


class TestINode(Bcfg2TestCase):
    test_obj = INode

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

    @patch("Bcfg2.Server.Plugin.INode._load_children")
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
        with patch_inode(self.test_obj, data, idict) as (inode, mock_init):
            self.assertItemsEqual(mock_init.call_args_list,
                                  [call(child1, idict, inode),
                                   call(child2, idict, inode)])
            self.assertEqual(idict, dict())
            self.assertItemsEqual(inode.contents, dict())
            
        data = lxml.etree.Element("Parent")
        child1 = lxml.etree.SubElement(data, "Data", name="child1",
                                       attr="some attr")
        child1.text = "text"
        subchild1 = lxml.etree.SubElement(child1, "SubChild", name="subchild")
        child2 = lxml.etree.SubElement(data, "Group", name="bar", negate="true")
        idict = dict()
        with patch_inode(self.test_obj, data, idict) as (inode, mock_init):
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
        
        # test ignore.  no ignore is set on INode by default, so we
        # have to set one
        old_ignore = copy.copy(self.test_obj.ignore)
        self.test_obj.ignore.append("Data")
        idict = dict()
        with patch_inode(self.test_obj, data, idict) as (inode, mock_init):
            mock_init.assert_called_with(child2, idict, inode)
            self.assertEqual(idict, dict())
            self.assertItemsEqual(inode.contents, dict())
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
        

class TestEntrySet(Bcfg2TestCase):
    pass
