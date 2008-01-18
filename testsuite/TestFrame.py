import lxml.etree

import Bcfg2.Client.Frame, Bcfg2.Client.Tools

c1 = lxml.etree.XML("<Configuration><Bundle name='foo'><Configfile name='/tmp/test12' owner='root' group='root' empty='true' perms='644'/></Bundle></Configuration>")

c2 = lxml.etree.XML("<Configuration><Bundle name='foo'><Configfile name='/tmp/test12' owner='root' group='root' empty='true' perms='644'/><Configfile name='/tmp/test12' owner='root' group='root' empty='true' perms='644'/></Bundle></Configuration>")

class DriverInitFail(object):
    def __init__(self, *args):
        raise Bcfg2.Client.Tools.toolInstantiationError

class TestFrame(object):
    def test__init(self):
        config = lxml.etree.Element('Configuration')
        setup = {}
        times = {}
        drivers = []
        frame = Bcfg2.Client.Frame.Frame(config, setup, times, drivers, False)
        assert frame.tools == []
        frame2 = Bcfg2.Client.Frame.Frame(c1, setup, times, ['POSIX'], False)
        assert len(frame2.tools) == 1
        frame3 = Bcfg2.Client.Frame.Frame(c2, setup, times, ['foo'], False)
        assert len(frame3.tools) == 0
        frame4 = Bcfg2.Client.Frame.Frame(c2, setup, times, [DriverInitFail], False)
