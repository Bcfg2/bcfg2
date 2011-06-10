import lxml.etree

import Bcfg2.Client.Frame
import Bcfg2.Client.Tools

c1 = lxml.etree.XML("<Configuration><Bundle name='foo'><Configfile name='/tmp/test12' owner='root' group='root' empty='true' perms='644'/></Bundle></Configuration>")

c2 = lxml.etree.XML("<Configuration><Bundle name='foo'><Configfile name='/tmp/test12' owner='root' group='root' empty='true' perms='644'/><Configfile name='/tmp/test12' owner='root' group='root' empty='true' perms='644'/></Bundle></Configuration>")


class DriverInitFail(object):
    def __init__(self, *args):
        raise Bcfg2.Client.Tools.toolInstantiationError


class DriverInventoryFail(object):
    __name__ = 'dif'

    def __init__(self, logger, setup, config):
        self.config = config
        self.handled = []
        self.modified = []
        self.extra = []

    def Inventory(self):
        raise Error


class TestFrame(object):
    def test__init(self):
        setup = {}
        times = {}
        config = lxml.etree.Element('Configuration')
        frame = Bcfg2.Client.Frame.Frame(config, setup, times, [], False)
        assert frame.tools == []

    def test__init2(self):
        setup = {}
        times = {}
        frame2 = Bcfg2.Client.Frame.Frame(c1, setup, times, ['POSIX'], False)
        assert len(frame2.tools) == 1

    def test__init3(self):
        setup = {}
        times = {}
        frame3 = Bcfg2.Client.Frame.Frame(c2, setup, times, ['foo'], False)
        assert len(frame3.tools) == 0

    def test__init4(self):
        setup = {}
        times = {}
        frame = Bcfg2.Client.Frame.Frame(c2, setup, times, [DriverInitFail], False)
        assert len(frame.tools) == 0

    def test__Decide_Inventory(self):
        setup = {'remove': 'none',
                 'bundle': [],
                 'interactive': False}
        times = {}
        frame = Bcfg2.Client.Frame.Frame(c2, setup, times,
                                         [DriverInventoryFail], False)
        assert len(frame.tools) == 1
        frame.Inventory()
        assert len([x for x in list(frame.states.values()) if x]) == 0
        frame.Decide()
        assert len(frame.whitelist)

    def test__Decide_Bundle(self):
        setup = {'remove': 'none',
                 'bundle': ['bar'],
                 'interactive': False}
        times = {}
        frame = Bcfg2.Client.Frame.Frame(c2, setup, times,
                                         [DriverInventoryFail], False)
        assert len(frame.tools) == 1
        frame.Inventory()
        assert len([x for x in list(frame.states.values()) if x]) == 0
        frame.Decide()
        assert len(frame.whitelist) == 0

    def test__Decide_Dryrun(self):
        setup = {'remove': 'none',
                 'bundle': [],
                 'interactive': False}
        times = {}
        frame = Bcfg2.Client.Frame.Frame(c2, setup, times,
                                         [DriverInventoryFail], True)
        assert len(frame.tools) == 1
        frame.Inventory()
        assert len([x for x in list(frame.states.values()) if x]) == 0
        frame.Decide()
        assert len(frame.whitelist) == 0

    def test__GenerateStats(self):
        setup = {'remove': 'none',
                 'bundle': [],
                 'interactive': False}
        times = {}
        frame = Bcfg2.Client.Frame.Frame(c2, setup, times,
                                         [DriverInventoryFail], False)
        frame.Inventory()
        frame.Decide()
        stats = frame.GenerateStats()
        assert len(stats.findall('.//Bad')[0].getchildren()) != 0
