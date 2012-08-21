import os
import sys
import unittest
from functools import wraps

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
else:
    builtins = "__builtin__"

if hasattr(unittest.TestCase, "assertItemsEqual"):
    TestCase = unittest.TestCase
else:
    def assertion(predicate, default_msg=None):
        @wraps(predicate)
        def inner(*args, **kwargs):
            if 'msg' in kwargs:
                msg = kwargs['msg']
                del kwargs['msg']
            else:
                msg = default_msg % args
            assert predicate(*args, **kwargs), msg
        return inner

    class TestCase(unittest.TestCase):
        # versions of TestCase before python 2.7 lacked a lot of the
        # really handy convenience methods, so we provide them -- at
        # least the easy ones and the ones we use.
        assertIs = assertion(lambda a, b: a is b, "%s is not %s")
        assertIsNot = assertion(lambda a, b: a is not b, "%s is %s")
        assertIsNone = assertion(lambda x: x is None, "%s is not None")
        assertIsNotNone = assertion(lambda x: x is not None, "%s is None")
        assertIn = assertion(lambda a, b: a in b, "%s is not in %s")
        assertNotIn = assertion(lambda a, b: a not in b, "%s is in %s")
        assertIsInstance = assertion(isinstance, "%s is not %s")
        assertNotIsInstance = assertion(lambda a, b: not isinstance(a, b),
                                        "%s is %s")
        assertGreater = assertion(lambda a, b: a > b,
                                  "%s is not greater than %s")
        assertGreaterEqual = assertion(lambda a, b: a >= b,
                                       "%s is not greater than or equal to %s")
        assertLess = assertion(lambda a, b: a < b, "%s is not less than %s")
        assertLessEqual = assertion(lambda a, b: a <= b,
                                    "%s is not less than or equal to %s")
        assertItemsEqual = assertion(lambda a, b: sorted(a) == sorted(b),
                                     "Items do not match:\n%s\n%s")

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
            @wraps(func)
            def inner(*args, **kwargs):
                pass
            return inner
        return decorator

    def skipIf(condition, msg):
        def decorator(func):
            if condition:
                return func

            @wraps(func)
            def inner(*args, **kwargs):
                pass
            return inner
        return decorator

    def skipUnless(condition, msg):
        def decorator(func):
            if not condition:
                return func

            @wraps(func)
            def inner(*args, **kwargs):
                pass
            return inner
        return decorator


class Bcfg2TestCase(TestCase):
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

    @unittest.skipUnless(has_django, "Django not found, skipping")
    def test_syncdb(self):
        # create the test database
        setup_environ(Bcfg2.settings)
        from django.core.management.commands import syncdb
        cmd = syncdb.Command()
        cmd.handle_noargs(interactive=False)
        self.assertTrue(os.path.exists(Bcfg2.settings.DATABASE_NAME))

    @unittest.skipUnless(has_django, "Django not found, skipping")
    def test_cleandb(self):
        """ ensure that we a) can connect to the database; b) start with a
        clean database """
        for model in self.models:
            model.objects.all().delete()
            self.assertItemsEqual(list(model.objects.all()), [])


def syncdb(modeltest):
    inst = modeltest(methodName='test_syncdb')
    inst.test_syncdb()
    inst.test_cleandb()
