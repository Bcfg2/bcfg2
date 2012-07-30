import os
import sys
import unittest
from mock import Mock, patch
import Bcfg2.Options


class TestOption(unittest.TestCase):
    def test__init(self):
        self.assertRaises(Bcfg2.Options.OptionFailure,
                          Bcfg2.Options.Option,
                          'foo', False, cmd='f')
        self.assertRaises(Bcfg2.Options.OptionFailure,
                          Bcfg2.Options.Option,
                          'foo', False, cmd='--f')
        self.assertRaises(Bcfg2.Options.OptionFailure,
                          Bcfg2.Options.Option,
                          'foo', False, cmd='-foo')
        self.assertRaises(Bcfg2.Options.OptionFailure,
                          Bcfg2.Options.Option,
                          'foo', False, cmd='-foo', long_arg=True)

    @patch('Bcfg2.Options.DefaultConfigParser')
    @patch('__builtin__.open')
    def test_get(self, mock_open, mock_cp):
        mock_cp.return_value = Mock()
        o = Bcfg2.Options.Option('foo', False, cmd='-f')
        self.assertFalse(o.cf)
        c = Bcfg2.Options.DefaultConfigParser()
        c.get('foo', False, cmd='-f')
        mock_cp.assert_any_call()
        mock_open.assert_any_call(Bcfg2.Options.DEFAULT_CONFIG_LOCATION)
        print(mock_cp.return_value.get.called)
        self.assertTrue(mock_cp.return_value.get.called)

    @patch('Bcfg2.Options.DefaultConfigParser')
    def test_parse(self, mock_cfp):
        cf = ('communication', 'password')
        o = Bcfg2.Options.Option('foo', default='test4', cmd='-F', env='TEST2',
                                 odesc='bar', cf=cf)
        o.parse([], ['-F', 'test'])
        self.assertEqual(o.value, 'test')
        o.parse([('-F', 'test2')], [])
        self.assertEqual(o.value, 'test2')

        os.environ['TEST2'] = 'test3'
        o.parse([], [])
        self.assertEqual(o.value, 'test3')
        del os.environ['TEST2']

        mock_cfp.get = Mock()
        mock_cfp.get.return_value = 'test5'
        o.parse([], [], configparser=mock_cfp)
        mock_cfp.get.assert_any_call(*cf)
        self.assertEqual(o.value, 'test5')

        o.cf = False
        o.parse([], [])
        assert o.value == 'test4'

    def test_cook(self):
        # check that default value isn't cooked
        o1 = Bcfg2.Options.Option('foo', 'test4', cook=Bcfg2.Options.get_bool)
        o1.parse([], [])
        assert o1.value == 'test4'
        o2 = Bcfg2.Options.Option('foo', False, cmd='-F')
        o2.parse([('-F', '')], [])
        assert o2.value == True


class TestOptionSet(unittest.TestCase):
    def test_buildGetopt(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-G')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H',
                                             odesc='1'))]
        oset = Bcfg2.Options.OptionSet(opts)
        res = oset.buildGetopt()
        self.assertIn('H:', res)
        self.assertIn('G', res)
        self.assertEqual(len(res), 3)

    def test_buildLongGetopt(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-G')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='--H',
                                             odesc='1', long_arg=True))]
        oset = Bcfg2.Options.OptionSet(opts)
        res = oset.buildLongGetopt()
        self.assertIn('H=', res)
        self.assertEqual(len(res), 1)

    def test_parse(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-G')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H',
                                             odesc='1'))]
        oset = Bcfg2.Options.OptionSet(opts)
        self.assertRaises(SystemExit,
                          oset.parse,
                          ['-G', '-H'])
        oset2 = Bcfg2.Options.OptionSet(opts)
        self.assertRaises(SystemExit,
                          oset2.parse,
                          ['-h'])
        oset3 = Bcfg2.Options.OptionSet(opts)
        oset3.parse(['-G'])
        self.assertTrue(oset3['foo'])


class TestOptionParser(unittest.TestCase):
    def test__init(self):
        opts = [('foo', Bcfg2.Options.Option('foo', 'test1', cmd='-h')),
                ('bar', Bcfg2.Options.Option('foo', 'test2')),
                ('baz', Bcfg2.Options.Option('foo', 'test1', cmd='-H',
                                             odesc='1'))]
        oset1 = Bcfg2.Options.OptionParser(opts)
        self.assertEqual(oset1.cfile,
                         Bcfg2.Options.DEFAULT_CONFIG_LOCATION)
        sys.argv = ['foo', '-C', '/usr/local/etc/bcfg2.conf']
        oset2 = Bcfg2.Options.OptionParser(opts)
        self.assertEqual(oset2.cfile,
                         '/usr/local/etc/bcfg2.conf')
        sys.argv = []
        oset3 = Bcfg2.Options.OptionParser(opts)
        self.assertEqual(oset3.cfile,
                         Bcfg2.Options.DEFAULT_CONFIG_LOCATION)
