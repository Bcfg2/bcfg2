""" In order to make testing easier and more consistent, we provide a
number of convenience functions, variables, and classes, for a wide
variety of reasons. To import this module, first set up
:ref:`development-unit-testing-relative-imports` and then simply do:

.. code-block:: python

    from common import *
"""

import os
import re
import sys
import codecs
import unittest
from mock import patch, MagicMock, _patch, DEFAULT
from Bcfg2.Compat import wraps

#: The path to the Bcfg2 specification root for the tests.  Using the
#: root directory exposes a lot of potential problems with building
#: paths.
datastore = "/"

#: The XInclude namespace name
XI_NAMESPACE = "http://www.w3.org/2001/XInclude"

#: The XInclude namespace in a format suitable for use in XPath
#: expressions
XI = "{%s}" % XI_NAMESPACE

#: Whether or not the tests are being run on Python 3.
inPy3k = False
if sys.hexversion >= 0x03000000:
    inPy3k = True

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
        """ Analog to the Mock call object, which is a fairly recent
        addition, but it's very very useful, so we create our own
        function to create Mock calls"""
        return (args, kwargs)

#: The name of the builtin module, for mocking Python builtins.  In
#: Python 2, this is ``__builtin__``, in Python 3 ``builtins``.  To
#: patch a builtin, you must do something like:
#:
#: .. code-block:: python
#:
#:     @patch("%s.open" % open)
#:     def test_something(self, mock_open):
#:         ...
builtins = "__builtin__"


if inPy3k:
    builtins = "builtins"

    def u(s):
        """ Get a unicode string, whatever that means.  In Python 2,
        returns a unicode object; in Python 3, returns a str object.

        :param s: The string to unicode-ify.
        :type s: str
        :returns: str or unicode """
        return s
else:
    def u(s):
        """ Get a unicode string, whatever that means.  In Python 2,
        returns a unicode object; in Python 3, returns a str object.

        :param s: The string to unicode-ify.
        :type s: str
        :returns: str or unicode """
        return codecs.unicode_escape_decode(s)[0]


#: Whether or not skipping tests is natively supported by
#: :mod:`unittest`.  If it isn't, then we have to make tests that
#: would be skipped succeed instead.
can_skip = False

if hasattr(unittest, "skip"):
    can_skip = True

    #: skip decorator from :func:`unittest.skip`
    skip = unittest.skip

    #: skipIf decorator from :func:`unittest.skipIf`
    skipIf = unittest.skipIf

    #: skipUnless decorator from :func:`unittest.skipUnless`
    skipUnless = unittest.skipUnless
else:
    # we can't actually skip tests, we just make them pass
    can_skip = False

    def skip(msg):
        """ skip decorator used when :mod:`unittest` doesn't support
        skipping tests.  Replaces the decorated function with a
        no-op. """
        def decorator(func):
            return lambda *args, **kwargs: None
        return decorator

    def skipIf(condition, msg):
        """ skipIf decorator used when :mod:`unittest` doesn't support
        skipping tests """
        if not condition:
            return lambda f: f
        else:
            return skip(msg)

    def skipUnless(condition, msg):
        """ skipUnless decorator used when :mod:`unittest` doesn't
        support skipping tests """
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
    """ Base TestCase class that inherits from
    :class:`unittest.TestCase`.  This class does a few things:

    * Adds :func:`assertXMLEqual`, a useful assertion method given all
      the XML used by Bcfg2;

    * Defines convenience methods that were (mostly) added in Python
      2.7.
    """
    if not hasattr(unittest.TestCase, "assertItemsEqual"):
        # TestCase in Py3k lacks assertItemsEqual, but has the other
        # convenience methods.  this code is (mostly) cribbed from the
        # py2.7 unittest library
        def assertItemsEqual(self, expected_seq, actual_seq, msg=None):
            """ Implementation of
            :func:`unittest.TestCase.assertItemsEqual` for python
            versions that lack it """
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
        """ Test that the two XML trees given are equal.  Both
        elements and all children are expected to have ``name``
        attributes. """
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
    """ Test case class for Django database models """
    models = []

    @skipUnless(has_django, "Django not found, skipping")
    def test_syncdb(self):
        """ Create the test database and sync the schema """
        setup_environ(Bcfg2.settings)
        import django.core.management
        django.core.management.call_command("syncdb", interactive=False,
                                            verbosity=0)
        self.assertTrue(os.path.exists(Bcfg2.settings.DATABASE_NAME))

    @skipUnless(has_django, "Django not found, skipping")
    def test_cleandb(self):
        """ Ensure that we a) can connect to the database; b) start
        with a clean database """
        for model in self.models:
            model.objects.all().delete()
            self.assertItemsEqual(list(model.objects.all()), [])


def syncdb(modeltest):
    """ Given an instance of a :class:`DBModelTestCase` object, sync
    and clean the database """
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
    """ Decorator class to perform conditional patching.  This is
    necessary because some libraries might not be installed (e.g.,
    selinux, pylibacl), and patching will barf on that.  Other
    workarounds are not available to us; e.g., context managers aren't
    in python 2.4, and using inner functions doesn't work because
    python 2.6 parses all decorators at compile-time, not at run-time,
    so decorating inner functions does not prevent the decorators from
    being run. """

    def __init__(self, condition, target, new=DEFAULT, spec=None, create=False,
                 spec_set=None):
        """
        :param condition: The condition to evaluate to decide if the
                          patch will be applied.
        :type condition: bool
        :param target: The name of the target object to patch
        :type target: str
        :param new: The new object to replace the target with.  If
                    this is omitted, a new :class:`mock.MagicMock` is
                    created and passed as an extra argument to the
                    decorated function.
        :type new: any
        :param spec: Spec passed to the MagicMock object if
                     ``patchIf`` is creating one for you.
        :type spec: List of strings or existing object
        :param create: Tell patch to create attributes on the fly.
                       See the documentation for :func:`mock.patch`
                       for more details on this.
        :type create: bool
        :param spec_set: Spec set passed to the MagicMock object if
                         ``patchIf`` is creating one for you.
        :type spec_set: List of strings or existing object
        """
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


#: The type of compiled regular expression objects
re_type = None
try:
    re_type = re._pattern_type
except AttributeError:
    re_type = type(re.compile(""))

