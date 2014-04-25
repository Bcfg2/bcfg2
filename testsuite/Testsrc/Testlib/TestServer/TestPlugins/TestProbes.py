import os
import re
import sys
import shutil
import tempfile
import lxml.etree
import Bcfg2.version
import Bcfg2.Server
import Bcfg2.Server.Plugin
from mock import Mock, MagicMock, patch

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import *
from Bcfg2.Server.Plugins.Probes import load_django_models
from TestPlugin import TestEntrySet, TestPlugin, \
    TestDatabaseBacked

load_django_models()
from Bcfg2.Server.Plugins.Probes import *

if HAS_JSON:
    json = json

if HAS_YAML:
    yaml = yaml

# test data for JSON and YAML tests
test_data = dict(a=1, b=[1, 2, 3], c="test",
                 d=dict(a=1, b=dict(a=1), c=(1, "2", 3)))


class FakeList(list):
    pass


class TestProbesDB(DBModelTestCase):
    if HAS_DJANGO:
        models = [ProbesGroupsModel,
                  ProbesDataModel]


class TestProbeData(Bcfg2TestCase):
    def test_str(self):
        # a value that is not valid XML, JSON, or YAML
        val = "'test"

        # test string behavior
        data = ProbeData(val)
        self.assertIsInstance(data, str)
        self.assertEqual(data, val)
        # test 1.2.0-1.2.2 broken behavior
        self.assertEqual(data.data, val)
        # test that formatted data accessors return None
        self.assertIsNone(data.xdata)
        self.assertIsNone(data.yaml)
        self.assertIsNone(data.json)

    def test_xdata(self):
        xdata = lxml.etree.Element("test")
        lxml.etree.SubElement(xdata, "test2")
        data = ProbeData(
            lxml.etree.tostring(xdata,
                                xml_declaration=False).decode('UTF-8'))
        self.assertIsNotNone(data.xdata)
        self.assertIsNotNone(data.xdata.find("test2"))

    @skipUnless(HAS_JSON,
                "JSON libraries not found, skipping JSON tests")
    def test_json(self):
        jdata = json.dumps(test_data)
        data = ProbeData(jdata)
        self.assertIsNotNone(data.json)
        self.assertItemsEqual(test_data, data.json)

    @skipUnless(HAS_YAML,
                "YAML libraries not found, skipping YAML tests")
    def test_yaml(self):
        jdata = yaml.dump(test_data)
        data = ProbeData(jdata)
        self.assertIsNotNone(data.yaml)
        self.assertItemsEqual(test_data, data.yaml)


class TestProbeSet(TestEntrySet):
    test_obj = ProbeSet
    basenames = ["test", "_test", "test-test"]
    ignore = ["foo~", ".#foo", ".foo.swp", ".foo.swx", "probed.xml"]
    bogus_names = ["test.py"]

    def get_obj(self, path=datastore, encoding=None,
                plugin_name="Probes", basename=None):
        # get_obj() accepts the basename argument, accepted by the
        # parent get_obj() method, and just throws it away, since
        # ProbeSet uses a regex for the "basename"
        rv = self.test_obj(path, plugin_name)
        rv.entry_type = MagicMock()
        return rv

    @patch("Bcfg2.Server.FileMonitor.get_fam")
    def test__init(self, mock_get_fam):
        ps = self.get_obj()
        self.assertEqual(ps.plugin_name, "Probes")
        mock_get_fam.return_value.AddMonitor.assert_called_with(datastore, ps)
        TestEntrySet.test__init(self)

    def test_HandleEvent(self):
        ps = self.get_obj()
        ps.handle_event = Mock()

        # test that events on the data store itself are skipped
        evt = Mock()
        evt.filename = datastore
        ps.HandleEvent(evt)
        self.assertFalse(ps.handle_event.called)

        # test that events on probed.xml are skipped
        evt.reset_mock()
        evt.filename = "probed.xml"
        ps.HandleEvent(evt)
        self.assertFalse(ps.handle_event.called)

        # test that other events are processed appropriately
        evt.reset_mock()
        evt.filename = "fooprobe"
        ps.HandleEvent(evt)
        ps.handle_event.assert_called_with(evt)

    @patch("%s.list" % builtins, FakeList)
    def test_get_probe_data(self):
        ps = self.get_obj()

        # build some fairly complex test data for this.  in the end,
        # we want the probe data to include only the most specific
        # version of a given probe, and by basename only, not full
        # (specific) name. We don't fully test the specificity stuff,
        # we just check to make sure sort() is called and trust that
        # sort() does the right thing on Specificity objects.  (I.e.,
        # trust that Specificity is well-tested. Hah!)  We also test
        # to make sure the interpreter is determined correctly.
        ps.get_matching = Mock()
        matching = FakeList()
        matching.sort = Mock()

        p1 = Mock()
        p1.specific = Bcfg2.Server.Plugin.Specificity(group=True, prio=10)
        p1.name = "fooprobe.G10_foogroup"
        p1.data = """#!/bin/bash
group-specific"""
        matching.append(p1)

        p2 = Mock()
        p2.specific = Bcfg2.Server.Plugin.Specificity(all=True)
        p2.name = "fooprobe"
        p2.data = "#!/bin/bash"
        matching.append(p2)

        p3 = Mock()
        p3.specific = Bcfg2.Server.Plugin.Specificity(all=True)
        p3.name = "barprobe"
        p3.data = "#! /usr/bin/env python"
        matching.append(p3)

        p4 = Mock()
        p4.specific = Bcfg2.Server.Plugin.Specificity(all=True)
        p4.name = "bazprobe"
        p4.data = ""
        matching.append(p4)

        ps.get_matching.return_value = matching

        metadata = Mock()
        metadata.version_info = \
            Bcfg2.version.Bcfg2VersionInfo(Bcfg2.version.__version__)
        pdata = ps.get_probe_data(metadata)
        ps.get_matching.assert_called_with(metadata)
        # we can't create a matching operator.attrgetter object, and I
        # don't feel the need to mock that out -- this is a good
        # enough check
        self.assertTrue(matching.sort.called)

        self.assertEqual(len(pdata), 3,
                         "Found: %s" % [p.get("name") for p in pdata])
        for probe in pdata:
            if probe.get("name") == "fooprobe":
                self.assertIn("group-specific", probe.text)
                self.assertEqual(probe.get("interpreter"), "/bin/bash")
            elif probe.get("name") == "barprobe":
                self.assertEqual(probe.get("interpreter"),
                                 "/usr/bin/env python")
            elif probe.get("name") == "bazprobe":
                self.assertIsNotNone(probe.get("interpreter"))
            else:
                assert False, "Strange probe found in get_probe_data() return"


class TestProbes(TestPlugin):
    test_obj = Probes

    test_xdata = lxml.etree.Element("test")
    lxml.etree.SubElement(test_xdata, "test", foo="foo")
    test_xdoc = lxml.etree.tostring(test_xdata,
                                    xml_declaration=False).decode('UTF-8')

    data = dict()
    data['xml'] = "group:group\n" + test_xdoc
    data['text'] = "freeform text"
    data['multiline'] = """multiple
lines
of
freeform
text
group:group-with-dashes
group:      group:with:colons
"""
    data['empty'] = ''
    data['almost_empty'] = 'group: other_group'
    if HAS_JSON:
        data['json'] = json.dumps(test_data)
    if HAS_YAML:
        data['yaml'] = yaml.dump(test_data)

    def setUp(self):
        Bcfg2TestCase.setUp(self)
        set_setup_default("probes_db")
        set_setup_default("probes_allowed_groups", [re.compile(".*")])
        self.datastore = None
        Bcfg2.Server.Cache.expire("Probes")

    def tearDown(self):
        Bcfg2.Server.Cache.expire("Probes")
        if self.datastore is not None:
            shutil.rmtree(self.datastore)
            self.datastore = None
            Bcfg2.Options.setup.repository = datastore

    def get_obj(self):
        if not Bcfg2.Options.setup.probes_db:
            # actually use a real datastore so we can read and write
            # probed.xml
            if self.datastore is None:
                self.datastore = tempfile.mkdtemp()
                Bcfg2.Options.setup.repository = self.datastore
                datadir = os.path.join(self.datastore, self.test_obj.name)
                if not os.path.exists(datadir):
                    os.makedirs(datadir)
        return TestPlugin.get_obj(self)

    def test__init(self):
        if Bcfg2.Options.setup.probes_db:
            TestPlugin.test__init(self)

    def test_GetProbes(self):
        p = self.get_obj()
        p.probes = Mock()
        metadata = Mock()
        p.GetProbes(metadata)
        p.probes.get_probe_data.assert_called_with(metadata)

    def additionalDataEqual(self, actual, expected):
        self.assertItemsEqual(
            dict([(k, str(d)) for k, d in actual.items()]),
            expected)

    def test_probes_xml(self):
        """ Set and retrieve probe data with database disabled """
        Bcfg2.Options.setup.probes_db = False
        self._perform_tests()

    @skipUnless(HAS_DJANGO, "Django not found")
    def test_probes_db(self):
        """ Set and retrieve probe data with database enabled """
        Bcfg2.Options.setup.probes_db = True
        syncdb(TestProbesDB)
        self._perform_tests()

    def test_allowed_cgroups(self):
        """ Test option to only allow probes to set certain groups """
        probes = self.get_obj()

        test_text = """a couple lines
of freeform text
"""
        test_groups = ["group", "group2", "group-with-dashes"]
        test_probe_data = lxml.etree.Element("Probe", name="test")
        test_probe_data.text = test_text
        for group in test_groups:
            test_probe_data.text += "group:%s\n" % group

        client = Mock()
        groups, data = probes.ReceiveDataItem(client, test_probe_data)
        self.assertItemsEqual(groups, test_groups)
        self.assertEqual(data, test_text)

        old_allowed_groups = Bcfg2.Options.setup.probes_allowed_groups
        Bcfg2.Options.setup.probes_allowed_groups = [re.compile(r'^group.?$')]
        groups, data = probes.ReceiveDataItem(client, test_probe_data)
        self.assertItemsEqual(groups, ['group', 'group2'])
        self.assertEqual(data, test_text)
        Bcfg2.Options.setup.probes_allowed_groups = old_allowed_groups

    def _perform_tests(self):
        p = self.get_obj()

        # first, sanity checks
        foo_md = Mock(hostname="foo.example.com")
        bar_md = Mock(hostname="bar.example.com")
        self.assertItemsEqual(p.get_additional_groups(foo_md), [])
        self.assertItemsEqual(p.get_additional_data(foo_md), dict())
        self.assertItemsEqual(p.get_additional_groups(bar_md), [])
        self.assertItemsEqual(p.get_additional_data(bar_md), dict())

        # next, set some initial probe data
        foo_datalist = []
        for key in ['xml', 'text', 'multiline']:
            pdata = lxml.etree.Element("Probe", name=key)
            pdata.text = self.data[key]
            foo_datalist.append(pdata)
        foo_addl_data = dict(xml=self.test_xdoc,
                             text="freeform text",
                             multiline="""multiple
lines
of
freeform
text""")
        bar_datalist = []
        for key in ['empty', 'almost_empty', 'json', 'yaml']:
            if key in self.data:
                pdata = lxml.etree.Element("Probe", name=key)
                pdata.text = self.data[key]
                bar_datalist.append(pdata)
        bar_addl_data = dict(empty="", almost_empty="")
        if HAS_JSON:
            bar_addl_data['json'] = self.data['json']
        if HAS_YAML:
            bar_addl_data['yaml'] = self.data['yaml']

        p.ReceiveData(foo_md, foo_datalist)
        self.assertItemsEqual(p.get_additional_groups(foo_md),
                              ["group", "group-with-dashes",
                               "group:with:colons"])
        self.additionalDataEqual(p.get_additional_data(foo_md), foo_addl_data)

        p.ReceiveData(bar_md, bar_datalist)
        self.assertItemsEqual(p.get_additional_groups(foo_md),
                              ["group", "group-with-dashes",
                               "group:with:colons"])
        self.additionalDataEqual(p.get_additional_data(foo_md), foo_addl_data)
        self.assertItemsEqual(p.get_additional_groups(bar_md), ['other_group'])
        self.additionalDataEqual(p.get_additional_data(bar_md), bar_addl_data)

        # instantiate a new Probes object and clear Probes caches to
        # imitate a server restart
        p = self.get_obj()
        Bcfg2.Server.Cache.expire("Probes")

        self.assertItemsEqual(p.get_additional_groups(foo_md),
                              ["group", "group-with-dashes",
                               "group:with:colons"])
        self.additionalDataEqual(p.get_additional_data(foo_md), foo_addl_data)
        self.assertItemsEqual(p.get_additional_groups(bar_md), ['other_group'])
        self.additionalDataEqual(p.get_additional_data(bar_md), bar_addl_data)

        # set new data (and groups) for foo
        foo_datalist = []
        pdata = lxml.etree.Element("Probe", name='xml')
        pdata.text = self.data['xml']
        foo_datalist.append(pdata)
        foo_addl_data = dict(xml=self.test_xdoc)

        p.ReceiveData(foo_md, foo_datalist)
        self.assertItemsEqual(p.get_additional_groups(foo_md), ["group"])
        self.additionalDataEqual(p.get_additional_data(foo_md), foo_addl_data)
        self.assertItemsEqual(p.get_additional_groups(bar_md), ['other_group'])
        self.additionalDataEqual(p.get_additional_data(bar_md), bar_addl_data)

        # instantiate a new Probes object and clear Probes caches to
        # imitate a server restart
        p = self.get_obj()
        Bcfg2.Server.Cache.expire("Probes")

        self.assertItemsEqual(p.get_additional_groups(foo_md), ["group"])
        self.additionalDataEqual(p.get_additional_data(foo_md), foo_addl_data)
        self.assertItemsEqual(p.get_additional_groups(bar_md), ['other_group'])
        self.additionalDataEqual(p.get_additional_data(bar_md), bar_addl_data)
