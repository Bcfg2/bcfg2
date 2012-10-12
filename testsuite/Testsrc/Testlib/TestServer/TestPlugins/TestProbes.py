import os
import sys
import time
import lxml.etree
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
from Bcfg2.Server.Plugins.Probes import *
from TestPlugin import TestEntrySet, TestProbing, TestConnector, \
    TestDatabaseBacked

# test data for JSON and YAML tests
test_data = dict(a=1, b=[1, 2, 3], c="test")


class FakeList(list):
    pass


class TestProbesDB(DBModelTestCase):
    if HAS_DJANGO:
        models = [ProbesGroupsModel, ProbesDataModel]


class TestClientProbeDataSet(Bcfg2TestCase):
    def test__init(self):
        ds = ClientProbeDataSet()
        self.assertLessEqual(ds.timestamp, time.time())
        self.assertIsInstance(ds, dict)
        self.assertNotIn("timestamp", ds)

        ds = ClientProbeDataSet(timestamp=123)
        self.assertEqual(ds.timestamp, 123)
        self.assertNotIn("timestamp", ds)


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
        data = ProbeData(lxml.etree.tostring(xdata,
                                             xml_declaration=False).decode('UTF-8'))
        self.assertIsNotNone(data.xdata)
        self.assertIsNotNone(data.xdata.find("test2"))

    @skipUnless(HAS_JSON, "JSON libraries not found, skipping JSON tests")
    def test_json(self):
        jdata = json.dumps(test_data)
        data = ProbeData(jdata)
        self.assertIsNotNone(data.json)
        self.assertItemsEqual(test_data, data.json)
        
    @skipUnless(HAS_YAML, "YAML libraries not found, skipping YAML tests")
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

    def get_obj(self, path=datastore, fam=None, encoding=None,
                plugin_name="Probes", basename=None):
        # get_obj() accepts the basename argument, accepted by the
        # parent get_obj() method, and just throws it away, since
        # ProbeSet uses a regex for the "basename"
        if fam is None:
            fam = Mock()
        rv = self.test_obj(path, fam, encoding, plugin_name)
        rv.entry_type = MagicMock()
        return rv

    def test__init(self):
        fam = Mock()
        ps = self.get_obj(fam=fam)
        self.assertEqual(ps.plugin_name, "Probes")
        fam.AddMonitor.assert_called_with(datastore, ps)
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


class TestProbes(TestProbing, TestConnector, TestDatabaseBacked):
    test_obj = Probes

    def get_obj(self, core=None):
        if core is None:
            core = MagicMock()
        return self.test_obj(core, datastore)

    def get_test_probedata(self):
        test_xdata = lxml.etree.Element("test")
        lxml.etree.SubElement(test_xdata, "test", foo="foo")
        rv = dict()
        rv["foo.example.com"] = ClientProbeDataSet(timestamp=time.time())
        rv["foo.example.com"]["xml"] = \
            ProbeData(lxml.etree.tostring(test_xdata,
                                          xml_declaration=False).decode('UTF-8'))
        rv["foo.example.com"]["text"] = ProbeData("freeform text")
        rv["foo.example.com"]["multiline"] = ProbeData("""multiple
lines
of
freeform
text
""")
        rv["bar.example.com"] = ClientProbeDataSet(timestamp=time.time())
        rv["bar.example.com"]["empty"] = ProbeData("")
        if HAS_JSON:
            rv["bar.example.com"]["json"] = ProbeData(json.dumps(test_data))
        if HAS_YAML:
            rv["bar.example.com"]["yaml"] = ProbeData(yaml.dump(test_data))
        return rv

    def get_test_cgroups(self):
        return {"foo.example.com": ["group", "group with spaces",
                                    "group-with-dashes"],
                "bar.example.com": []}

    def get_probes_object(self, use_db=False, load_data=None):
        core = MagicMock()
        core.setup.cfp.getboolean = Mock()
        core.setup.cfp.getboolean.return_value = use_db
        if load_data is None:
            load_data = MagicMock()
        # we have to patch load_data() in a funny way because
        # different versions of Mock have different scopes for
        # patching.  in some versions, a patch applied to
        # get_probes_object() would only apply to that function, while
        # in others it would also apply to the calling function (e.g.,
        # test__init(), which relies on being able to check the calls
        # of load_data(), and thus on load_data() being consistently
        # mocked)
        @patch("Bcfg2.Server.Plugins.Probes.Probes.load_data", new=load_data)
        def inner():
            return Probes(core, datastore)

        return inner()

    def test__init(self):
        mock_load_data = Mock()
        probes = self.get_probes_object(load_data=mock_load_data)
        probes.core.fam.AddMonitor.assert_called_with(os.path.join(datastore,
                                                                   probes.name),
                                                      probes.probes)
        mock_load_data.assert_any_call()
        self.assertEqual(probes.probedata, ClientProbeDataSet())
        self.assertEqual(probes.cgroups, dict())

    @patch("Bcfg2.Server.Plugins.Probes.Probes.load_data", Mock())
    def test__use_db(self):
        probes = self.get_probes_object()
        self.assertFalse(probes._use_db)
        probes.core.setup.cfp.getboolean.assert_called_with("probes",
                                                            "use_database",
                                                            default=False)

    @skipUnless(HAS_DJANGO, "Django not found, skipping")
    @patch("Bcfg2.Server.Plugins.Probes.Probes._write_data_db", Mock())
    @patch("Bcfg2.Server.Plugins.Probes.Probes._write_data_xml", Mock())
    def test_write_data_xml(self):
        probes = self.get_probes_object(use_db=False)
        probes.write_data("test")
        probes._write_data_xml.assert_called_with("test")
        self.assertFalse(probes._write_data_db.called)

    @skipUnless(HAS_DJANGO, "Django not found, skipping")
    @patch("Bcfg2.Server.Plugins.Probes.Probes._write_data_db", Mock())
    @patch("Bcfg2.Server.Plugins.Probes.Probes._write_data_xml", Mock())
    def test_write_data_db(self):
        probes = self.get_probes_object(use_db=True)
        probes.write_data("test")
        probes._write_data_db.assert_called_with("test")
        self.assertFalse(probes._write_data_xml.called)

    @patch("%s.open" % builtins)
    def test__write_data_xml(self, mock_open):
        probes = self.get_probes_object(use_db=False)
        probes.probedata = self.get_test_probedata()
        probes.cgroups = self.get_test_cgroups()
        probes._write_data_xml(None)

        mock_open.assert_called_with(os.path.join(datastore, probes.name,
                                                  "probed.xml"), "w")
        data = lxml.etree.XML(mock_open.return_value.write.call_args[0][0])
        self.assertEqual(len(data.xpath("//Client")), 2)

        foodata = data.find("Client[@name='foo.example.com']")
        self.assertIsNotNone(foodata)
        self.assertIsNotNone(foodata.get("timestamp"))
        self.assertEqual(len(foodata.findall("Probe")),
                         len(probes.probedata['foo.example.com']))
        self.assertEqual(len(foodata.findall("Group")),
                         len(probes.cgroups['foo.example.com']))
        xml = foodata.find("Probe[@name='xml']")
        self.assertIsNotNone(xml)
        self.assertIsNotNone(xml.get("value"))
        xdata = lxml.etree.XML(xml.get("value"))
        self.assertIsNotNone(xdata)
        self.assertIsNotNone(xdata.find("test"))
        self.assertEqual(xdata.find("test").get("foo"), "foo")
        text = foodata.find("Probe[@name='text']")
        self.assertIsNotNone(text)
        self.assertIsNotNone(text.get("value"))
        multiline = foodata.find("Probe[@name='multiline']")
        self.assertIsNotNone(multiline)
        self.assertIsNotNone(multiline.get("value"))
        self.assertGreater(len(multiline.get("value").splitlines()), 1)

        bardata = data.find("Client[@name='bar.example.com']")
        self.assertIsNotNone(bardata)
        self.assertIsNotNone(bardata.get("timestamp"))
        self.assertEqual(len(bardata.findall("Probe")),
                         len(probes.probedata['bar.example.com']))
        self.assertEqual(len(bardata.findall("Group")),
                         len(probes.cgroups['bar.example.com']))
        empty = bardata.find("Probe[@name='empty']")
        self.assertIsNotNone(empty)
        self.assertIsNotNone(empty.get("value"))
        self.assertEqual(empty.get("value"), "")
        if HAS_JSON:
            jdata = bardata.find("Probe[@name='json']")
            self.assertIsNotNone(jdata)
            self.assertIsNotNone(jdata.get("value"))
            self.assertItemsEqual(test_data, json.loads(jdata.get("value")))
        if HAS_YAML:
            ydata = bardata.find("Probe[@name='yaml']")
            self.assertIsNotNone(ydata)
            self.assertIsNotNone(ydata.get("value"))
            self.assertItemsEqual(test_data, yaml.load(ydata.get("value")))

    @skipUnless(HAS_DJANGO, "Django not found, skipping")
    def test__write_data_db(self):
        syncdb(TestProbesDB)
        probes = self.get_probes_object(use_db=True)
        probes.probedata = self.get_test_probedata()
        probes.cgroups = self.get_test_cgroups()

        for cname in ["foo.example.com", "bar.example.com"]:
            client = Mock()
            client.hostname = cname
            probes._write_data_db(client)

            pdata = ProbesDataModel.objects.filter(hostname=cname).all()
            self.assertEqual(len(pdata), len(probes.probedata[cname]))

            for probe in pdata:
                self.assertEqual(probe.hostname, client.hostname)
                self.assertIsNotNone(probe.data)
                if probe.probe == "xml":
                    xdata = lxml.etree.XML(probe.data)
                    self.assertIsNotNone(xdata)
                    self.assertIsNotNone(xdata.find("test"))
                    self.assertEqual(xdata.find("test").get("foo"), "foo")
                elif probe.probe == "text":
                    pass
                elif probe.probe == "multiline":
                    self.assertGreater(len(probe.data.splitlines()), 1)
                elif probe.probe == "empty":
                    self.assertEqual(probe.data, "")
                elif probe.probe == "yaml":
                    self.assertItemsEqual(test_data, yaml.load(probe.data))
                elif probe.probe == "json":
                    self.assertItemsEqual(test_data, json.loads(probe.data))
                else:
                    assert False, "Strange probe found in _write_data_db data"

            pgroups = ProbesGroupsModel.objects.filter(hostname=cname).all()
            self.assertEqual(len(pgroups), len(probes.cgroups[cname]))

        # test that old probe data is removed properly
        cname = 'foo.example.com'
        del probes.probedata[cname]['text']
        probes.cgroups[cname].pop()
        client = Mock()
        client.hostname = cname
        probes._write_data_db(client)
        
        pdata = ProbesDataModel.objects.filter(hostname=cname).all()
        self.assertEqual(len(pdata), len(probes.probedata[cname]))
        pgroups = ProbesGroupsModel.objects.filter(hostname=cname).all()
        self.assertEqual(len(pgroups), len(probes.cgroups[cname]))

    @skipUnless(HAS_DJANGO, "Django not found, skipping")
    @patch("Bcfg2.Server.Plugins.Probes.Probes._load_data_db", Mock())
    @patch("Bcfg2.Server.Plugins.Probes.Probes._load_data_xml", Mock())
    def test_load_data_xml(self):
        probes = self.get_probes_object(use_db=False)
        probes.load_data()
        probes._load_data_xml.assert_any_call()
        self.assertFalse(probes._load_data_db.called)

    @skipUnless(HAS_DJANGO, "Django not found, skipping")
    @patch("Bcfg2.Server.Plugins.Probes.Probes._load_data_db", Mock())
    @patch("Bcfg2.Server.Plugins.Probes.Probes._load_data_xml", Mock())
    def test_load_data_db(self):
        probes = self.get_probes_object(use_db=True)
        probes.load_data()
        probes._load_data_db.assert_any_call()
        self.assertFalse(probes._load_data_xml.called)

    @patch("%s.open" % builtins)
    @patch("lxml.etree.parse")
    def test__load_data_xml(self, mock_parse, mock_open):
        probes = self.get_probes_object(use_db=False)
        # to get the value for lxml.etree.parse to parse, we call
        # _write_data_xml, mock the open() call, and grab the data
        # that gets "written" to probed.xml
        probes.probedata = self.get_test_probedata()
        probes.cgroups = self.get_test_cgroups()
        probes._write_data_xml(None)
        xdata = \
            lxml.etree.XML(str(mock_open.return_value.write.call_args[0][0]))
        mock_parse.return_value = xdata.getroottree()
        probes.probedata = dict()
        probes.cgroups = dict()

        probes._load_data_xml()
        mock_parse.assert_called_with(os.path.join(datastore, probes.name,
                                                   'probed.xml'),
                                      parser=Bcfg2.Server.XMLParser)
        self.assertItemsEqual(probes.probedata, self.get_test_probedata())
        self.assertItemsEqual(probes.cgroups, self.get_test_cgroups())

    @skipUnless(HAS_DJANGO, "Django not found, skipping")
    def test__load_data_db(self):
        syncdb(TestProbesDB)
        probes = self.get_probes_object(use_db=True)
        probes.probedata = self.get_test_probedata()
        probes.cgroups = self.get_test_cgroups()
        for cname in probes.probedata.keys():
            client = Mock()
            client.hostname = cname
            probes._write_data_db(client)

        probes.probedata = dict()
        probes.cgroups = dict()
        probes._load_data_db()
        self.assertItemsEqual(probes.probedata, self.get_test_probedata())
        # the db backend does not store groups at all if a client has
        # no groups set, so we can't just use assertItemsEqual here,
        # because loading saved data may _not_ result in the original
        # data if some clients had no groups set.
        test_cgroups = self.get_test_cgroups()
        for cname, groups in test_cgroups.items():
            if cname in probes.cgroups:
                self.assertEqual(groups, probes.cgroups[cname])
            else:
                self.assertEqual(groups, [])

    @patch("Bcfg2.Server.Plugins.Probes.ProbeSet.get_probe_data")
    def test_GetProbes(self, mock_get_probe_data):
        probes = self.get_probes_object()
        metadata = Mock()
        probes.GetProbes(metadata)
        mock_get_probe_data.assert_called_with(metadata)

    @patch("Bcfg2.Server.Plugins.Probes.Probes.write_data")
    @patch("Bcfg2.Server.Plugins.Probes.Probes.ReceiveDataItem")
    def test_ReceiveData(self, mock_ReceiveDataItem, mock_write_data):
        # we use a simple (read: bogus) datalist here to make this
        # easy to test
        datalist = ["a", "b", "c"]
        
        probes = self.get_probes_object()
        probes.core.metadata_cache_mode = 'off'
        client = Mock()
        client.hostname = "foo.example.com"
        probes.ReceiveData(client, datalist)
        
        self.assertItemsEqual(mock_ReceiveDataItem.call_args_list,
                              [call(client, "a"), call(client, "b"),
                               call(client, "c")])
        mock_write_data.assert_called_with(client)
        self.assertFalse(probes.core.metadata_cache.expire.called)

        # change the datalist, ensure that the cache is cleared
        probes.cgroups[client.hostname] = datalist
        probes.core.metadata_cache_mode = 'aggressive'
        probes.ReceiveData(client, ['a', 'b', 'd'])
        
        mock_write_data.assert_called_with(client)
        probes.core.metadata_cache.expire.assert_called_with(client.hostname)

    def test_ReceiveDataItem(self):
        probes = self.get_probes_object()
        for cname, cdata in self.get_test_probedata().items():
            client = Mock()
            client.hostname = cname
            for pname, pdata in cdata.items():
                dataitem = lxml.etree.Element("Probe", name=pname)
                if pname == "text":
                    # add some groups to the plaintext test to test
                    # group parsing
                    data = [pdata]
                    for group in self.get_test_cgroups()[cname]:
                        data.append("group:%s" % group)
                    dataitem.text = "\n".join(data)
                else:
                    dataitem.text = str(pdata)

                probes.ReceiveDataItem(client, dataitem)
                
                self.assertIn(client.hostname, probes.probedata)
                self.assertIn(pname, probes.probedata[cname])
                self.assertEqual(pdata, probes.probedata[cname][pname])
            self.assertIn(client.hostname, probes.cgroups)
            self.assertEqual(probes.cgroups[cname],
                             self.get_test_cgroups()[cname])

    def test_get_additional_groups(self):
        TestConnector.test_get_additional_groups(self)

        probes = self.get_probes_object()
        test_cgroups = self.get_test_cgroups()
        probes.cgroups = self.get_test_cgroups()
        for cname in test_cgroups.keys():
            metadata = Mock()
            metadata.hostname = cname
            self.assertEqual(test_cgroups[cname],
                             probes.get_additional_groups(metadata))
        # test a non-existent client
        metadata = Mock()
        metadata.hostname = "nonexistent"
        self.assertEqual(probes.get_additional_groups(metadata),
                         list())

    def test_get_additional_data(self):
        TestConnector.test_get_additional_data(self)

        probes = self.get_probes_object()
        test_probedata = self.get_test_probedata()
        probes.probedata = self.get_test_probedata()
        for cname in test_probedata.keys():
            metadata = Mock()
            metadata.hostname = cname
            self.assertEqual(test_probedata[cname],
                             probes.get_additional_data(metadata))
        # test a non-existent client
        metadata = Mock()
        metadata.hostname = "nonexistent"
        self.assertEqual(probes.get_additional_data(metadata),
                         ClientProbeDataSet())
        
        
