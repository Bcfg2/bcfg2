import os
import re
import sys
import unittest
from mock import patch, MagicMock, _patch, DEFAULT
from Bcfg2.Compat import wraps

datastore = "/"

XI_NAMESPACE = "http://www.w3.org/2001/XInclude"
XI = "{%s}" % XI_NAMESPACE

if sys.hexversion >= 0x03000000:
    inPy3k = True
else:
    inPy3k = False

try:
    from django.core.management import setup_environ
    has_django = True

    os.environ['DJANGO_SETTINGS_MODULE'] = "Bcfg2.settings"

    import Bcfg2.settings
    Bcfg2.settings.DATABASE_NAME = \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.sqlite")
    Bcfg2.settings.DATABASES['default']['NAME'] = Bcfg2.settings.DATABASE_NAME
except ImportError:
    has_django = False


try:
    from mock import call
except ImportError:
    def call(*args, **kwargs):
        """ the Mock call object is a fairly recent addition, but it's
        very very useful, so we create our own function to create Mock
        calls """
        return (args, kwargs)

if inPy3k:
    builtins = "builtins"

    def u(x):
        return x
else:
    builtins = "__builtin__"

    import codecs
    def u(x):
        return codecs.unicode_escape_decode(x)[0]


if hasattr(unittest, "skip"):
    can_skip = True
    skip = unittest.skip
    skipIf = unittest.skipIf
    skipUnless = unittest.skipUnless
else:
    # we can't actually skip tests, we just make them pass
    can_skip = False

    def skip(msg):
        def decorator(func):
            return lambda *args, **kwargs: None
        return decorator

    def skipIf(condition, msg):
        if not condition:
            return lambda f: f
        else:
            return skip(msg)

    def skipUnless(condition, msg):
        if condition:
            return lambda f: f
        else:
            return skip(msg)


def _count_diff_all_purpose(actual, expected):
    '''Returns list of (cnt_act, cnt_exp, elem) triples where the
    counts differ'''
    # elements need not be hashable
    s, t = list(actual), list(expected)
    m, n = len(s), len(t)
    NULL = object()
    result = []
    for i, elem in enumerate(s):
        if elem is NULL:
            continue
        cnt_s = cnt_t = 0
        for j in range(i, m):
            if s[j] == elem:
                cnt_s += 1
                s[j] = NULL
        for j, other_elem in enumerate(t):
            if other_elem == elem:
                cnt_t += 1
                t[j] = NULL
        if cnt_s != cnt_t:
            diff = (cnt_s, cnt_t, elem)
            result.append(diff)

    for i, elem in enumerate(t):
        if elem is NULL:
            continue
        cnt_t = 0
        for j in range(i, n):
            if t[j] == elem:
                cnt_t += 1
                t[j] = NULL
        diff = (0, cnt_t, elem)
        result.append(diff)
    return result

def _assertion(predicate, default_msg=None):
    @wraps(predicate)
    def inner(self, *args, **kwargs):
        if 'msg' in kwargs:
            msg = kwargs['msg']
            del kwargs['msg']
        else:
            try:
                msg = default_msg % args
            except TypeError:
                # message passed as final (non-keyword) argument?
                msg = args[-1]
                args = args[:-1]
        assert predicate(*args, **kwargs), msg
    return inner

def _regex_matches(val, regex):
    if hasattr(regex, 'search'):
        return regex.search(val)
    else:
        return re.search(regex, val)


class Bcfg2TestCase(unittest.TestCase):
    if not hasattr(unittest.TestCase, "assertItemsEqual"):
        # TestCase in Py3k lacks assertItemsEqual, but has the other
        # convenience methods.  this code is (mostly) cribbed from the
        # py2.7 unittest library
        def assertItemsEqual(self, expected_seq, actual_seq, msg=None):
            first_seq, second_seq = list(actual_seq), list(expected_seq)
            differences = _count_diff_all_purpose(first_seq, second_seq)

            if differences:
                standardMsg = 'Element counts were not equal:\n'
                lines = ['First has %d, Second has %d:  %r' % diff
                         for diff in differences]
                diffMsg = '\n'.join(lines)
                standardMsg = self._truncateMessage(standardMsg, diffMsg)
                msg = self._formatMessage(msg, standardMsg)
                self.fail(msg)

    if not hasattr(unittest.TestCase, "assertRegexpMatches"):
        # Some versions of TestCase in Py3k seem to lack
        # assertRegexpMatches, but have the other convenience methods.
        assertRegexpMatches = _assertion(lambda s, r: _regex_matches(s, r),
                                         "%s does not contain /%s/")

    if not hasattr(unittest.TestCase, "assertNotRegexpMatches"):
        # Some versions of TestCase in Py3k seem to lack
        # assertNotRegexpMatches even though they have
        # assertRegexpMatches
        assertNotRegexpMatches = \
            _assertion(lambda s, r: not _regex_matches(s, r),
                       "%s contains /%s/")

    if not hasattr(unittest.TestCase, "assertIn"):
        # versions of TestCase before python 2.7 and python 3.1 lacked
        # a lot of the really handy convenience methods, so we provide
        # them -- at least the easy ones and the ones we use.
        assertIs = _assertion(lambda a, b: a is b, "%s is not %s")
        assertIsNot = _assertion(lambda a, b: a is not b, "%s is %s")
        assertIsNone = _assertion(lambda x: x is None, "%s is not None")
        assertIsNotNone = _assertion(lambda x: x is not None, "%s is None")
        assertIn = _assertion(lambda a, b: a in b, "%s is not in %s")
        assertNotIn = _assertion(lambda a, b: a not in b, "%s is in %s")
        assertIsInstance = _assertion(isinstance, "%s is not instance of %s")
        assertNotIsInstance = _assertion(lambda a, b: not isinstance(a, b),
                                         "%s is instance of %s")
        assertGreater = _assertion(lambda a, b: a > b,
                                   "%s is not greater than %s")
        assertGreaterEqual = _assertion(lambda a, b: a >= b,
                                        "%s is not greater than or equal to %s")
        assertLess = _assertion(lambda a, b: a < b, "%s is not less than %s")
        assertLessEqual = _assertion(lambda a, b: a <= b,
                                     "%s is not less than or equal to %s")

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


class DBModelTestCase(Bcfg2TestCase):
    models = []

    @skipUnless(has_django, "Django not found, skipping")
    def test_syncdb(self):
        # create the test database
        setup_environ(Bcfg2.settings)
        import django.core.management
        django.core.management.call_command("syncdb", interactive=False,
                                            verbosity=0)
        self.assertTrue(os.path.exists(Bcfg2.settings.DATABASE_NAME))

    @skipUnless(has_django, "Django not found, skipping")
    def test_cleandb(self):
        # ensure that we a) can connect to the database; b) start with
        # a clean database
        for model in self.models:
            model.objects.all().delete()
            self.assertItemsEqual(list(model.objects.all()), [])


def syncdb(modeltest):
    inst = modeltest(methodName='test_syncdb')
    inst.test_syncdb()
    inst.test_cleandb()


# in order for patchIf() to decorate a function in the same way as
# patch(), we override the default behavior of __enter__ and __exit__
# on the _patch() object to basically be noops.
class _noop_patch(_patch):
    def __enter__(self):
        return MagicMock(name=self.attribute)

    def __exit__(self, *args):
        pass


class patchIf(object):
    """ perform conditional patching.  this is necessary because some
    libraries might not be installed (e.g., selinux, pylibacl), and
    patching will barf on that.  Other workarounds are not available
    to us; e.g., context managers aren't in python 2.4, and using
    inner functions doesn't work because python 2.6 applies all
    decorators at compile-time, not at run-time, so decorating inner
    functions does not prevent the decorators from being run. """
    def __init__(self, condition, target, new=DEFAULT, spec=None, create=False,
                 spec_set=None):
        self.condition = condition
        self.target = target

        self.patch_args = dict(new=new, spec=spec, create=create,
                               spec_set=spec_set)

    def __call__(self, func):
        if self.condition:
            return patch(self.target, **self.patch_args)(func)
        else:
            args = [lambda: True,
                    self.target.rsplit('.', 1)[-1],
                    self.patch_args['new'], self.patch_args['spec'],
                    self.patch_args['create'], None,
                    self.patch_args['spec_set']]
            try:
                # in older versions of mock, _patch() takes 8 args
                return _noop_patch(*args)(func)
            except TypeError:
                # in some intermediate versions of mock, _patch
                # takes 11 args
                args.extend([None, None, None])
                try:
                    return _noop_patch(*args)(func)
                except TypeError:
                    # in the latest versions of mock, _patch() takes
                    # 10 args -- mocksignature has been removed
                    args.pop(5)
                    return _noop_patch(*args)(func)
