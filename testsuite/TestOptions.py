import os, sys
import Bcfg2.Options

class TestOption(object):
    def test__init(self):
        o = Bcfg2.Options.Option('foo', False, cmd='-F')
        try:
            p = Bcfg2.Options.Option('foo', False, cmd='--F')
            assert False
        except Bcfg2.Options.OptionFailure:
            pass

    def test_parse(self):
        o = Bcfg2.Options.Option('foo', 'test4', cmd='-F', env='TEST2',
                                 odesc='bar', cf=('communication', 'password'))
        o.parse([], ['-F', 'test'])
        assert o.value == 'test'
        o.parse([('-F', 'test2')], [])
        assert o._value == 'test2'
        os.environ['TEST2'] = 'test3'
        o.parse([], [])
        assert o._value == 'test3'
        del os.environ['TEST2']
        o.parse([], [])
        print o._value
        assert o._value == 'foobat'
        o.cf = False
        o.parse([], [])
        assert o._value == 'test4'

    def test_cook(self):
        cooker = lambda x: 1
        o = Bcfg2.Options.Option('foo', 'test4', cook=cooker)
        o.parse([], [])
        assert o.value == 1
    

class TestOptionSet(object):
    def test_buildGetopt(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-G')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H', odesc='1'))]
        os = Bcfg2.Options.OptionSet(opts)
        res = os.buildGetopt()
        assert 'H:' in res and 'G' in res and len(res) == 3

    def test_parse(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-G')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H', odesc='1'))]
        os = Bcfg2.Options.OptionSet(opts)
        try:
            os.parse(['-G', '-H'])
            assert False
        except SystemExit:
            pass
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-h')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H', odesc='1'))]
        os2 = Bcfg2.Options.OptionSet(opts)
        try:
            os2.parse(['-h'])
            assert False
        except SystemExit:
            pass

class TestOptionParser(object):
    def test__init(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-h')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H', odesc='1'))]
        os1 = Bcfg2.Options.OptionParser(opts)
        assert Bcfg2.Options.Option.cfpath == '/etc/bcfg2.conf'
        sys.argv = ['foo', '-C', '/usr/local/etc/bcfg2.conf']
        os2 = Bcfg2.Options.OptionParser(opts)
        assert Bcfg2.Options.Option.cfpath == '/usr/local/etc/bcfg2.conf'
        sys.argv = []
        os3 = Bcfg2.Options.OptionParser(opts)
        assert Bcfg2.Options.Option.cfpath == '/etc/bcfg2.conf'
