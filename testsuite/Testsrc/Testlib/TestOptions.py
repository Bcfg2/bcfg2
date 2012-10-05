import os
import sys
from mock import Mock, MagicMock, patch
from Bcfg2.Options import *
from Bcfg2.Compat import ConfigParser

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

class TestDefaultConfigParser(Bcfg2TestCase):
    @patch("%s.ConfigParser.get" % ConfigParser.__name__)
    def test_get(self, mock_get):
        dcp = DefaultConfigParser()
        mock_get.return_value = "foo"
        self.assertEqual(dcp.get("section", "option"), "foo")
        mock_get.assert_called_with(dcp, "section", "option")
        
        mock_get.reset_mock()
        self.assertEqual(dcp.get("section", "option",
                                 default="bar", other="test"), "foo")
        mock_get.assert_called_with(dcp, "section", "option", other="test")

        for etype, err in [(ConfigParser.NoOptionError,
                            ConfigParser.NoOptionError(None, None)),
                           (ConfigParser.NoSectionError,
                            ConfigParser.NoSectionError(None))]:
            mock_get.side_effect = err
            mock_get.reset_mock()
            self.assertEqual(dcp.get("section", "option", default="bar"), "bar")
            mock_get.assert_called_with(dcp, "section", "option")

            mock_get.reset_mock()
            self.assertRaises(etype, dcp.get, "section", "option")
            mock_get.assert_called_with(dcp, "section", "option")

    @patch("%s.ConfigParser.getboolean" % ConfigParser.__name__)
    def test_getboolean(self, mock_getboolean):
        dcp = DefaultConfigParser()
        mock_getboolean.return_value = True
        self.assertEqual(dcp.getboolean("section", "option"), True)
        mock_getboolean.assert_called_with(dcp, "section", "option")
        
        mock_getboolean.reset_mock()
        self.assertEqual(dcp.getboolean("section", "option",
                                 default=False, other="test"), True)
        mock_getboolean.assert_called_with(dcp, "section", "option",
                                           other="test")

        for etype, err in [(ConfigParser.NoOptionError,
                            ConfigParser.NoOptionError(None, None)),
                           (ConfigParser.NoSectionError,
                            ConfigParser.NoSectionError(None))]:
            mock_getboolean.side_effect = err
            mock_getboolean.reset_mock()
            self.assertEqual(dcp.getboolean("section", "option", default=False),
                             False)
            mock_getboolean.assert_called_with(dcp, "section", "option")

            mock_getboolean.reset_mock()
            self.assertRaises(etype, dcp.getboolean, "section", "option")
            mock_getboolean.assert_called_with(dcp, "section", "option")
            

class TestOption(Bcfg2TestCase):
    def test__init(self):
        self.assertRaises(OptionFailure,
                          Option,
                          'foo', False, cmd='f')
        self.assertRaises(OptionFailure,
                          Option,
                          'foo', False, cmd='--f')
        self.assertRaises(OptionFailure,
                          Option,
                          'foo', False, cmd='-foo')
        self.assertRaises(OptionFailure,
                          Option,
                          'foo', False, cmd='-foo', long_arg=True)
        opt = Option('foo', False)
        self.assertTrue(opt.boolean)
        opt = Option('foo', False, odesc='<val>')
        self.assertFalse(opt.boolean)
        opt = Option('foo', False, cook=get_bool)
        self.assertFalse(opt.boolean)
        opt = Option('foo', "foo")
        self.assertFalse(opt.boolean)
        
    def test_get_cooked_value(self):
        opt = Option('foo', False)
        opt.boolean = True
        self.assertTrue(opt.get_cooked_value("anything"))

        opt = Option('foo', 'foo')
        opt.boolean = False
        opt.cook = False
        self.assertEqual("foo", opt.get_cooked_value("foo"))
        
        opt = Option('foo', 'foo')
        opt.boolean = False
        opt.cook = Mock()
        self.assertEqual(opt.cook.return_value, opt.get_cooked_value("foo"))
        opt.cook.assert_called_with("foo")

    def test_buildHelpMessage(self):
        opt = Option('foo', False)
        self.assertEqual(opt.buildHelpMessage(), '')

        opt = Option('foo', False, '-f')
        self.assertEqual(opt.buildHelpMessage().split(),
                         ["-f", "foo"])

        opt = Option('foo', False, cmd="--foo", long_arg=True)
        self.assertEqual(opt.buildHelpMessage().split(),
                         ["--foo", "foo"])

        opt = Option('foo', False, cmd="-f", odesc='<val>')
        self.assertEqual(opt.buildHelpMessage().split(),
                         ["-f", "<val>", "foo"])

        opt = Option('foo', False, cmd="--foo", long_arg=True, odesc='<val>')
        self.assertEqual(opt.buildHelpMessage().split(),
                         ["--foo=<val>", "foo"])

    def test_buildGetopt(self):
        opt = Option('foo', False)
        self.assertEqual(opt.buildGetopt(), '')

        opt = Option('foo', False, '-f')
        self.assertEqual(opt.buildGetopt(), "f")

        opt = Option('foo', False, cmd="--foo", long_arg=True)
        self.assertEqual(opt.buildGetopt(), '')

        opt = Option('foo', False, cmd="-f", odesc='<val>')
        self.assertEqual(opt.buildGetopt(), 'f:')

        opt = Option('foo', False, cmd="--foo", long_arg=True, odesc='<val>')
        self.assertEqual(opt.buildGetopt(), '')

    def test_buildLongGetopt(self):
        opt = Option('foo', False, cmd="--foo", long_arg=True)
        self.assertEqual(opt.buildLongGetopt(), 'foo')

        opt = Option('foo', False, cmd="--foo", long_arg=True, odesc='<val>')
        self.assertEqual(opt.buildLongGetopt(), 'foo=')

    def test_parse(self):
        cf = ('communication', 'password')
        o = Option('foo', default='test4', cmd='-F', env='TEST2',
                                 odesc='bar', cf=cf)
        o.parse([], ['-F', 'test'])
        self.assertEqual(o.value, 'test')
        o.parse([('-F', 'test2')], [])
        self.assertEqual(o.value, 'test2')

        os.environ['TEST2'] = 'test3'
        o.parse([], [])
        self.assertEqual(o.value, 'test3')
        del os.environ['TEST2']

        cfp = DefaultConfigParser()
        cfp.get = Mock()
        cfp.get.return_value = 'test5'
        o.parse([], [], configparser=cfp)
        cfp.get.assert_any_call(*cf)
        self.assertEqual(o.value, 'test5')

        o.cf = False
        o.parse([], [])
        assert o.value == 'test4'


class TestOptionSet(Bcfg2TestCase):
    def test_buildGetopt(self):
        opts = [('foo', Option('foo', 'test1', cmd='-G')),
                ('bar', Option('foo', 'test2')),
                ('baz', Option('foo', 'test1', cmd='-H',
                                             odesc='1'))]
        oset = OptionSet(opts)
        res = oset.buildGetopt()
        self.assertIn('H:', res)
        self.assertIn('G', res)
        self.assertEqual(len(res), 3)

    def test_buildLongGetopt(self):
        opts = [('foo', Option('foo', 'test1', cmd='-G')),
                ('bar', Option('foo', 'test2')),
                ('baz', Option('foo', 'test1', cmd='--H',
                                             odesc='1', long_arg=True))]
        oset = OptionSet(opts)
        res = oset.buildLongGetopt()
        self.assertIn('H=', res)
        self.assertEqual(len(res), 1)

    def test_parse(self):
        opts = [('foo', Option('foo', 'test1', cmd='-G')),
                ('bar', Option('foo', 'test2')),
                ('baz', Option('foo', 'test1', cmd='-H',
                                             odesc='1'))]
        oset = OptionSet(opts)
        self.assertRaises(SystemExit,
                          oset.parse,
                          ['-G', '-H'])
        oset2 = OptionSet(opts)
        self.assertRaises(SystemExit,
                          oset2.parse,
                          ['-h'])
        oset3 = OptionSet(opts)
        oset3.parse(['-G'])
        self.assertTrue(oset3['foo'])


class TestOptionParser(Bcfg2TestCase):
    def test__init(self):
        opts = [('foo', Option('foo', 'test1', cmd='-h')),
                ('bar', Option('foo', 'test2')),
                ('baz', Option('foo', 'test1', cmd='-H',
                                             odesc='1'))]
        oset1 = OptionParser(opts)
        self.assertEqual(oset1.cfile,
                         DEFAULT_CONFIG_LOCATION)
        sys.argv = ['foo', '-C', '/usr/local/etc/bcfg2.conf']
        oset2 = OptionParser(opts)
        self.assertEqual(oset2.cfile,
                         '/usr/local/etc/bcfg2.conf')
        sys.argv = []
        oset3 = OptionParser(opts)
        self.assertEqual(oset3.cfile,
                         DEFAULT_CONFIG_LOCATION)
