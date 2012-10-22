import os
import sys
import lxml.etree
import Bcfg2.Server
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugin.interfaces import *

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
from TestServer.TestPlugin.Testbase import TestPlugin


class TestGenerator(Bcfg2TestCase):
    test_obj = Generator

    def test_HandlesEntry(self):
        pass

    def test_HandleEntry(self):
        pass


class TestStructure(Bcfg2TestCase):
    test_obj = Structure

    def get_obj(self):
        return self.test_obj()

    def test_BuildStructures(self):
        s = self.get_obj()
        self.assertRaises(NotImplementedError,
                          s.BuildStructures, None)


class TestMetadata(Bcfg2TestCase):
    test_obj = Metadata

    def get_obj(self):
        return self.test_obj()

    def test_AuthenticateConnection(self):
        m = self.get_obj()
        self.assertRaises(NotImplementedError,
                          m.AuthenticateConnection,
                          None, None, None, (None, None))

    def test_get_initial_metadata(self):
        m = self.get_obj()
        self.assertRaises(NotImplementedError,
                          m.get_initial_metadata, None)

    def test_merge_additional_data(self):
        m = self.get_obj()
        self.assertRaises(NotImplementedError,
                          m.merge_additional_data, None, None, None)

    def test_merge_additional_groups(self):
        m = self.get_obj()
        self.assertRaises(NotImplementedError,
                          m.merge_additional_groups, None, None)


class TestConnector(Bcfg2TestCase):
    """ placeholder """
    def test_get_additional_groups(self):
        pass

    def test_get_additional_data(self):
        pass


class TestProbing(Bcfg2TestCase):
    test_obj = Probing

    def get_obj(self):
        return self.test_obj()

    def test_GetProbes(self):
        p = self.get_obj()
        self.assertRaises(NotImplementedError,
                          p.GetProbes, None)

    def test_ReceiveData(self):
        p = self.get_obj()
        self.assertRaises(NotImplementedError,
                          p.ReceiveData, None, None)


class TestStatistics(TestPlugin):
    test_obj = Statistics

    def get_obj(self, core=None):
        if core is None:
            core = Mock()
        return self.test_obj(core, datastore)

    def test_process_statistics(self):
        s = self.get_obj()
        self.assertRaises(NotImplementedError,
                          s.process_statistics, None, None)


class TestThreadedStatistics(TestStatistics):
    test_obj = ThreadedStatistics
    data = [("foo.example.com", "<foo/>"),
            ("bar.example.com", "<bar/>")]

    @patch("threading.Thread.start")
    def test__init(self, mock_start):
        core = Mock()
        ts = self.get_obj(core)
        mock_start.assert_any_call()

    @patch("%s.open" % builtins)
    @patch("%s.dump" % cPickle.__name__)
    @patch("Bcfg2.Server.Plugin.interfaces.ThreadedStatistics.run", Mock())
    def test_save(self, mock_dump, mock_open):
        core = Mock()
        ts = self.get_obj(core)
        queue = Mock()
        queue.empty = Mock(side_effect=Empty)
        ts.work_queue = queue

        mock_open.side_effect = IOError
        # test that save does _not_ raise an exception even when
        # everything goes pear-shaped
        ts._save()
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

        ts._save()
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
    @patch("%s.open" % builtins)
    @patch("lxml.etree.XML")
    @patch("%s.load" % cPickle.__name__)
    @patch("Bcfg2.Server.Plugin.interfaces.ThreadedStatistics.run", Mock())
    def test_load(self, mock_load, mock_XML, mock_open, mock_exists,
                  mock_unlink):
        core = Mock()
        core.terminate.isSet.return_value = False
        ts = self.get_obj(core)
        
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
        self.assertTrue(ts._load())
        mock_exists.assert_called_with(ts.pending_file)

        reset()
        mock_exists.return_value = True
        mock_open.side_effect = IOError
        self.assertFalse(ts._load())
        mock_exists.assert_called_with(ts.pending_file)
        mock_open.assert_called_with(ts.pending_file, 'r')

        reset()
        mock_open.side_effect = None
        mock_load.return_value = self.data
        ts.work_queue.put_nowait.side_effect = Full
        self.assertTrue(ts._load())
        mock_exists.assert_called_with(ts.pending_file)
        mock_open.assert_called_with(ts.pending_file, 'r')
        mock_open.return_value.close.assert_any_call()
        mock_load.assert_called_with(mock_open.return_value)

        reset()
        core.build_metadata.side_effect = lambda x: x
        mock_XML.side_effect = lambda x, parser=None: x
        ts.work_queue.put_nowait.side_effect = None
        self.assertTrue(ts._load())
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
    @patch("Bcfg2.Server.Plugin.interfaces.ThreadedStatistics._load")
    @patch("Bcfg2.Server.Plugin.interfaces.ThreadedStatistics._save")
    @patch("Bcfg2.Server.Plugin.interfaces.ThreadedStatistics.handle_statistic")
    def test_run(self, mock_handle, mock_save, mock_load):
        core = Mock()
        ts = self.get_obj(core)
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

        ts.work_queue.empty.return_value = False
        ts.run()
        mock_load.assert_any_call()
        self.assertGreaterEqual(ts.work_queue.get.call_count, len(self.data))
        self.assertItemsEqual(mock_handle.call_args_list,
                              [call(h, x) for h, x in self.data])
        mock_save.assert_any_call()

    @patch("copy.copy", Mock(side_effect=lambda x: x))
    @patch("Bcfg2.Server.Plugin.interfaces.ThreadedStatistics.run", Mock())
    def test_process_statistics(self):
        core = Mock()
        ts = self.get_obj(core)
        ts.work_queue = Mock()
        ts.process_statistics(*self.data[0])
        ts.work_queue.put_nowait.assert_called_with(self.data[0])

        ts.work_queue.reset_mock()
        ts.work_queue.put_nowait.side_effect = Full
        # test that no exception is thrown
        ts.process_statistics(*self.data[0])

    def test_handle_statistic(self):
        ts = self.get_obj()
        self.assertRaises(NotImplementedError,
                          ts.handle_statistic, None, None)
        

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
    test_obj = Decision
    
    def get_obj(self):
        return self.test_obj()

    def test_GetDecisions(self):
        d = self.get_obj()
        self.assertRaises(NotImplementedError,
                          d.GetDecisions, None, None)


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
    test_obj = Version
    
    def get_obj(self):
        return self.test_obj(datastore)

    def test_get_revision(self):
        d = self.get_obj()
        self.assertRaises(NotImplementedError, d.get_revision)


class TestClientRunHooks(Bcfg2TestCase):
    """ placeholder for future tests """
    pass
