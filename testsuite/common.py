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
import lxml.etree
import Bcfg2.Options
import Bcfg2.Utils
try:
    from mock.mock import patch, MagicMock, _patch, DEFAULT
except ImportError:
    from mock import patch, MagicMock, _patch, DEFAULT
try:
    from unittest2 import skip, skipIf, skipUnless, TestCase
except ImportError:
    from unittest import skip, skipIf, skipUnless, TestCase

#: The XInclude namespace name
XI_NAMESPACE = "http://www.w3.org/2001/XInclude"

#: The XInclude namespace in a format suitable for use in XPath
#: expressions
XI = "{%s}" % XI_NAMESPACE

#: Whether or not the tests are being run on Python 3.
inPy3k = False
if sys.hexversion >= 0x03000000:
    inPy3k = True


#: A function to set a default config option if it's not already set
def set_setup_default(option, value=None):
    if not hasattr(Bcfg2.Options.setup, option):
        setattr(Bcfg2.Options.setup, option, value)

# these two variables do slightly different things for unit tests; the
# former skips config file reading, while the latter sends option
# debug logging to stdout so it can be captured. These are separate
# because we want to enable config file reading in order to test
# option parsing.
Bcfg2.Options.Parser.unit_test = True
Bcfg2.Options.Options.unit_test = True

try:
    import django.conf
    has_django = True

    set_setup_default("db_engine", "sqlite3")
    set_setup_default("db_name",
                      os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "test.sqlite"))
    set_setup_default("db_user")
    set_setup_default("db_password")
    set_setup_default("db_host")
    set_setup_default("db_port")
    set_setup_default("db_opts", dict())
    set_setup_default("db_schema")
    set_setup_default("time_zone")
    set_setup_default("web_debug", False)
    set_setup_default("web_prefix")
    set_setup_default("django_settings")

    import Bcfg2.DBSettings
    Bcfg2.DBSettings.finalize_django_config()
except ImportError:
    has_django = False

#: The path to the Bcfg2 specification root for the tests.  Using the
#: root directory exposes a lot of potential problems with building
#: paths.
datastore = "/"

set_setup_default("repository", datastore)

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


class MockExecutor(object):
    """mock object for :class:`Bcfg2.Utils.Executor` objects."""
    def __init__(self, timeout=None):
        self.timeout = timeout

        # variables that can be set to control the result returned
        self.stdout = ''
        self.stderr = ''
        self.retval = 0

        # variables that record how run() was called
        self.calls = []

    def run(self, command, inputdata=None, timeout=None, **kwargs):
        self.calls.append({"command": command,
                           "inputdata": inputdata,
                           "timeout": timeout or self.timeout,
                           "kwargs": kwargs})

        return Bcfg2.Utils.ExecutorResult(self.stdout, self.stderr,
                                          self.retval)


class Bcfg2TestCase(TestCase):
    """ Base TestCase class that inherits from
    :class:`unittest.TestCase`.  This class adds
    :func:`assertXMLEqual`, a useful assertion method given all the
    XML used by Bcfg2.
    """
    capture_stderr = True

    @classmethod
    def setUpClass(cls):
        cls._stderr = sys.stderr
        if cls.capture_stderr:
            sys.stderr = sys.stdout

    @classmethod
    def tearDownClass(cls):
        if cls.capture_stderr:
            sys.stderr = cls._stderr

    if hasattr(TestCase, "assertCountEqual"):
        assertItemsEqual = assertCountEqual

    def assertXMLEqual(self, el1, el2, msg=None):
        """ Test that the two XML trees given are equal. """
        if msg is None:
            msg = "XML trees are not equal: %s"
        else:
            msg += ": %s"
        msg += "\n%s"
        fullmsg = "First:  %s" % lxml.etree.tostring(el1) + \
            "\nSecond: %s" % lxml.etree.tostring(el2)

        self.assertEqual(el1.tag, el2.tag, msg=msg % ("Tags differ", fullmsg))
        if el1.text is not None and el2.text is not None:
            self.assertEqual(el1.text.strip(), el2.text.strip(),
                             msg=msg % ("Text content differs", fullmsg))
        else:
            self.assertEqual(el1.text, el2.text,
                             msg=msg % ("Text content differs", fullmsg))
        self.assertItemsEqual(el1.attrib.items(), el2.attrib.items(),
                              msg=msg % ("Attributes differ", fullmsg))
        self.assertEqual(len(el1.getchildren()),
                         len(el2.getchildren()),
                         msg=msg % ("Different numbers of children", fullmsg))
        matched = []
        for child1 in el1.getchildren():
            for child2 in el2.xpath(child1.tag):
                if child2 in matched:
                    continue
                try:
                    self.assertXMLEqual(child1, child2)
                    matched.append(child2)
                    break
                except AssertionError:
                    continue
            else:
                assert False, \
                    msg % ("Element %s is missing from second" %
                               lxml.etree.tostring(child1), fullmsg)
        self.assertItemsEqual(el2.getchildren(), matched,
                              msg=msg % ("Second has extra element(s)", fullmsg))


class DBModelTestCase(Bcfg2TestCase):
    """ Test case class for Django database models """
    models = []
    __test__ = False

    @skipUnless(has_django, "Django not found, skipping")
    def test_syncdb(self):
        """ Create the test database and sync the schema """
        if self.models:
            import django
            import django.core.management

            if django.VERSION[0] == 1 and django.VERSION[1] < 7:
                django.core.management.call_command('syncdb', interactive=False,
                                                    verbosity=0)

            django.core.management.call_command('migrate', interactive=False,
                                                verbosity=0)
            self.assertTrue(
                os.path.exists(
                    django.conf.settings.DATABASES['default']['NAME']))

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
