import os
import unittest

__all__ = ['call', 'datastore', 'Bcfg2TestCase', 'DBModelTestCase', 'syncdb',
           'XI', 'XI_NAMESPACE']

datastore = "/"

XI_NAMESPACE = "http://www.w3.org/2001/XInclude"
XI = "{%s}" % XI_NAMESPACE

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


class Bcfg2TestCase(unittest.TestCase):
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
