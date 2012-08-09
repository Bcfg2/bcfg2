import os
import copy
import logging
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugin import *
import Bcfg2.Server
import Bcfg2.Server.Plugins.Metadata

datastore = '/'

def call(*args, **kwargs):
    """ the Mock call object is a fairly recent addition, but it's
    very very useful, so we create our own function to create Mock
    calls """
    return (args, kwargs)


class TestFunctions(unittest.TestCase):
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


class TestPluginInitError(unittest.TestCase):
    """ placeholder for future tests """
    pass


class TestPluginExecutionError(unittest.TestCase):
    """ placeholder for future tests """
    pass


class TestDebuggable(unittest.TestCase):
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


class TestPlugin(unittest.TestCase):
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


class TestDatabaseBacked(unittest.TestCase):
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


class TestPluginDatabaseModel(unittest.TestCase):
    """ placeholder for future tests """
    pass


class TestGenerator(unittest.TestCase):
    def test_HandleEntry(self):
        g = Generator()
        self.assertRaises(NotImplementedError,
                          g.HandleEntry, None, None)


class TestStructure(unittest.TestCase):
    def test_BuildStructures(self):
        s = Structure()
        self.assertRaises(NotImplementedError,
                          s.BuildStructures, None)


class TestMetadata(unittest.TestCase):
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


class TestConnector(unittest.TestCase):
    """ placeholder """
    pass


class TestProbing(unittest.TestCase):
    """ placeholder """
    pass


class TestStatistics(unittest.TestCase):
    """ placeholder """
    pass


class TestThreadedStatistics(unittest.TestCase):
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
        

class TestPullSource(unittest.TestCase):
    def test_GetCurrentEntry(self):
        ps = PullSource()
        self.assertRaises(NotImplementedError,
                          ps.GetCurrentEntry, None, None, None)


class TestPullTarget(unittest.TestCase):
    def test_AcceptChoices(self):
        pt = PullTarget()
        self.assertRaises(NotImplementedError,
                          pt.AcceptChoices, None, None)

    def test_AcceptPullData(self):
        pt = PullTarget()
        self.assertRaises(NotImplementedError,
                          pt.AcceptPullData, None, None, None)


class TestDecision(unittest.TestCase):
    """ placeholder for future tests """
    pass


class TestValidationError(unittest.TestCase):
    """ placeholder for future tests """
    pass


class TestStructureValidator(unittest.TestCase):
    def test_validate_structures(self):
        sv = StructureValidator()
        self.assertRaises(NotImplementedError,
                          sv.validate_structures, None, None)


class TestGoalValidator(unittest.TestCase):
    def test_validate_goals(self):
        gv = GoalValidator()
        self.assertRaises(NotImplementedError,
                          gv.validate_goals, None, None)


class TestVersion(unittest.TestCase):
    """ placeholder for future tests """
    pass


class TestClientRunHooks(unittest.TestCase):
    """ placeholder for future tests """
    pass


class TestFileBacked(unittest.TestCase):
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

