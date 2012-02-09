import os
import sys

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
        assert o.value == 'test2'
        os.environ['TEST2'] = 'test3'
        o.parse([], [])
        assert o.value == 'test3'
        del os.environ['TEST2']
        o.parse([], [])
        print(o.value)
        assert o.value == 'foobat'
        o.cf = ('communication', 'pwd')
        o.parse([], [])
        print(o.value)
        assert o.value == 'test4'
        o.cf = False
        o.parse([], [])
        assert o.value == 'test4'

    def test_cook(self):
        # check that default value isn't cooked
        o1 = Bcfg2.Options.Option('foo', 'test4', cook=Bcfg2.Options.bool_cook)
        o1.parse([], [])
        assert o1.value == 'test4'
        o2 = Bcfg2.Options.Option('foo', False, cmd='-F')
        o2.parse([('-F', '')], [])
        assert o2.value == True


class TestOptionSet(object):
    def test_buildGetopt(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-G')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H',
                                             odesc='1'))]
        os = Bcfg2.Options.OptionSet(opts)
        res = os.buildGetopt()
        assert 'H:' in res and 'G' in res and len(res) == 3

    def test_buildLongGetopt(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-G')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='--H',
                                             odesc='1', long_arg=True))]
        os = Bcfg2.Options.OptionSet(opts)
        res = os.buildLongGetopt()
        print(res)
        assert 'H=' in res and len(res) == 1

    def test_parse(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-G')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H',
                                             odesc='1'))]
        os = Bcfg2.Options.OptionSet(opts)
        try:
            os.parse(['-G', '-H'])
            assert False
        except SystemExit:
            pass
        os2 = Bcfg2.Options.OptionSet(opts)
        try:
            os2.parse(['-h'])
            assert False
        except SystemExit:
            pass
        os3 = Bcfg2.Options.OptionSet(opts)
        os3.parse(['-G'])
        assert os3['foo'] == True
