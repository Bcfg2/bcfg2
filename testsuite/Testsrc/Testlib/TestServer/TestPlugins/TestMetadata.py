import os
import sys
import copy
import time
import socket
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
from Bcfg2.Server.Plugins.Metadata import load_django_models
from TestPlugin import TestXMLFileBacked, TestMetadata as _TestMetadata, \
    TestClientRunHooks, TestDatabaseBacked

load_django_models()
from Bcfg2.Server.Plugins.Metadata import *


def get_clients_test_tree():
    return lxml.etree.XML('''
<Clients>
  <Client name="client1" address="1.2.3.1" auth="cert"
          location="floating" password="password2" profile="group1"/>
  <Client name="client2" address="1.2.3.2" secure="true" profile="group2"/>
  <Client name="client3" address="1.2.3.3" uuid="uuid1" profile="group1"
          password="password2">
    <Alias name="alias1"/>
  </Client>
  <Client name="client4" profile="group1">
    <Alias name="alias2" address="1.2.3.2"/>
    <Alias name="alias3"/>
  </Client>
  <Client name="client5" profile="group1"/>
  <Client name="client6" profile="group1" auth="bootstrap"/>
  <Client name="client7" profile="group1" auth="cert" address="1.2.3.4"/>
  <Client name="client8" profile="group1" auth="cert+password"
          address="1.2.3.5"/>
  <Client name="client9" profile="group2" secure="true" password="password3"/>
  <Client name="client10" profile="group1" floating="true"/>
</Clients>''').getroottree()


def get_groups_test_tree():
    return lxml.etree.XML('''
<Groups xmlns:xi="http://www.w3.org/2001/XInclude">
  <Client name="client8">
    <Group name="group8"/>
  </Client>
  <Client name="client9">
    <Group name="group8"/>
  </Client>

  <Group name="group1" default="true" profile="true" public="true"
         category="category1"/>
  <Group name="group2" profile="true" public="true" category="category1">
    <Bundle name="bundle1"/>
    <Bundle name="bundle2"/>
    <Group name="group1"/>
    <Group name="group4"/>
  </Group>
  <Group name="group3" category="category2" public="false"/>
  <Group name="group4" category="category1">
    <Group name="group1"/>
    <Group name="group6"/>
  </Group>
  <Group name="group5"/>
  <Group name="group7">
    <Bundle name="bundle3"/>
  </Group>
  <Group name="group8">
    <Group name="group9"/>
    <Client name="client9">
      <Group name="group11"/>
      <Group name="group9" negate="true"/>
    </Client>
    <Group name="group1">
      <Group name="group10"/>
    </Group>
  </Group>
  <Group name="group12" category="category3" public="false"/>
</Groups>''').getroottree()


def get_metadata_object(core=None):
    if core is None:
        core = Mock()
        core.metadata_cache = MagicMock()

    set_setup_default("password")
    @patchIf(not isinstance(os.makedirs, Mock), "os.makedirs", Mock())
    @patchIf(not isinstance(lxml.etree.Element, Mock),
             "lxml.etree.Element", Mock())

    def inner():
        return Metadata(core)
    return inner()


class TestMetadataDB(DBModelTestCase):
    if HAS_DJANGO:
        models = [MetadataClientModel]


class TestClientVersions(TestDatabaseBacked):
    test_clients = dict(client1="1.2.0",
                        client2="1.2.2",
                        client3="1.3.0pre1",
                        client4="1.1.0",
                        client5=None,
                        client6=None)

    @skipUnless(HAS_DJANGO, "Django not found")
    def setUp(self):
        TestDatabaseBacked.setUp(self)
        self.test_obj = ClientVersions
        syncdb(TestMetadataDB)
        for client, version in self.test_clients.items():
            MetadataClientModel(hostname=client, version=version).save()

    def test__contains(self):
        v = self.get_obj()
        self.assertIn("client1", v)
        self.assertIn("client5", v)
        self.assertNotIn("client__contains", v)

    def test_keys(self):
        v = self.get_obj()
        self.assertItemsEqual(self.test_clients.keys(), v.keys())

    def test__setitem(self):
        v = self.get_obj()

        # test setting version of existing client
        v["client1"] = "1.2.3"
        self.assertIn("client1", v)
        self.assertEqual(v['client1'], "1.2.3")
        client = MetadataClientModel.objects.get(hostname="client1")
        self.assertEqual(client.version, "1.2.3")

        # test adding new client
        new = "client__setitem"
        v[new] = "1.3.0"
        self.assertIn(new, v)
        self.assertEqual(v[new], "1.3.0")
        client = MetadataClientModel.objects.get(hostname=new)
        self.assertEqual(client.version, "1.3.0")

        # test adding new client with no version
        new2 = "client__setitem_2"
        v[new2] = None
        self.assertIn(new2, v)
        self.assertEqual(v[new2], None)
        client = MetadataClientModel.objects.get(hostname=new2)
        self.assertEqual(client.version, None)

    def test__getitem(self):
        v = self.get_obj()

        # test getting existing client
        self.assertEqual(v['client2'], "1.2.2")
        self.assertIsNone(v['client5'])

        # test exception on nonexistent client
        expected = KeyError
        try:
            v['clients__getitem']
        except expected:
            pass
        except:
            err = sys.exc_info()[1]
            self.assertFalse(True, "%s raised instead of %s" %
                             (err.__class__.__name__,
                              expected.__class__.__name__))
        else:
            self.assertFalse(True,
                             "%s not raised" % expected.__class__.__name__)

    def test__len(self):
        v = self.get_obj()
        self.assertEqual(len(v), MetadataClientModel.objects.count())

    def test__iter(self):
        v = self.get_obj()
        self.assertItemsEqual([h for h in iter(v)], v.keys())

    def test__delitem(self):
        v = self.get_obj()

        # test adding new client
        new = "client__delitem"
        v[new] = "1.3.0"

        del v[new]
        self.assertIn(new, v)
        self.assertIsNone(v[new])


class TestXMLMetadataConfig(TestXMLFileBacked):
    test_obj = XMLMetadataConfig
    path = os.path.join(datastore, 'Metadata', 'clients.xml')

    def get_obj(self, basefile="clients.xml", core=None):
        self.metadata = get_metadata_object(core=core)
        @patchIf(not isinstance(lxml.etree.Element, Mock),
                 "lxml.etree.Element", Mock())
        def inner():
            return XMLMetadataConfig(self.metadata, basefile)
        return inner()

    @patch("Bcfg2.Server.FileMonitor.get_fam", Mock())
    def test__init(self):
        xmc = self.get_obj()
        self.assertNotIn(call(xmc.basefile),
                         xmc.fam.AddMonitor.call_args_list)

    def test_xdata(self):
        config = self.get_obj()
        expected = Bcfg2.Server.Plugin.MetadataRuntimeError
        try:
            config.xdata
        except expected:
            pass
        except:
            err = sys.exc_info()[1]
            self.assertFalse(True, "%s raised instead of %s" %
                             (err.__class__.__name__,
                              expected.__class__.__name__))
        else:
            self.assertFalse(True,
                             "%s not raised" % expected.__class__.__name__)
            pass

        config.data = "<test/>"
        self.assertEqual(config.xdata, "<test/>")

    def test_base_xdata(self):
        config = self.get_obj()
        # we can't use assertRaises here because base_xdata is a property
        expected = Bcfg2.Server.Plugin.MetadataRuntimeError
        try:
            config.base_xdata
        except expected:
            pass
        except:
            err = sys.exc_info()[1]
            self.assertFalse(True, "%s raised instead of %s" %
                             (err.__class__.__name__,
                              expected.__class__.__name__))
        else:
            self.assertFalse(True,
                             "%s not raised" % expected.__class__.__name__)
            pass

        config.basedata = "<test/>"
        self.assertEqual(config.base_xdata, "<test/>")

    def test_add_monitor(self):
        config = self.get_obj()
        config.fam = Mock()

        fname = "test.xml"
        fpath = os.path.join(self.metadata.data, fname)

        config.extras = []
        config.add_monitor(fpath)
        config.fam.AddMonitor.assert_called_with(fpath, config.metadata)
        self.assertItemsEqual(config.extras, [fpath])

    def test_Index(self):
        # Index() isn't used on XMLMetadataConfig objects
        pass

    @patch("lxml.etree.parse")
    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig._follow_xincludes")
    def test_load_xml(self, mock_follow, mock_parse):
        config = self.get_obj("clients.xml")

        def reset():
            mock_parse.reset_mock()
            mock_follow.reset_mock()
            config.data = None
            config.basedata = None

        reset()
        config.load_xml()
        mock_follow.assert_called_with(xdata=mock_parse.return_value)
        mock_parse.assert_called_with(os.path.join(config.basedir,
                                                   "clients.xml"),
                                      parser=Bcfg2.Server.XMLParser)
        self.assertFalse(mock_parse.return_value.xinclude.called)
        self.assertEqual(config.data, mock_parse.return_value)
        self.assertIsNotNone(config.basedata)

        reset()
        mock_parse.side_effect = lxml.etree.XMLSyntaxError(None, None, None,
                                                           None)
        config.load_xml()
        mock_parse.assert_called_with(os.path.join(config.basedir,
                                                   "clients.xml"),
                                      parser=Bcfg2.Server.XMLParser)
        self.assertIsNone(config.data)
        self.assertIsNone(config.basedata)

        reset()
        mock_parse.side_effect = None
        def follow_xincludes(xdata=None):
            config.extras = [Mock(), Mock()]
        mock_follow.side_effect = follow_xincludes
        config.load_xml()
        mock_follow.assert_called_with(xdata=mock_parse.return_value)
        mock_parse.assert_called_with(os.path.join(config.basedir,
                                                   "clients.xml"),
                                      parser=Bcfg2.Server.XMLParser)
        mock_parse.return_value.xinclude.assert_any_call()
        self.assertEqual(config.data, mock_parse.return_value)
        self.assertIsNotNone(config.basedata)


    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.write_xml")
    def test_write(self, mock_write_xml):
        config = self.get_obj("clients.xml")
        config.basedata = "<test/>"
        config.write()
        mock_write_xml.assert_called_with(os.path.join(self.metadata.data,
                                                       "clients.xml"),
                                          "<test/>")

    @patch('Bcfg2.Utils.locked', Mock(return_value=False))
    @patch('fcntl.lockf', Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml")
    @patch('os.open')
    @patch('os.fdopen')
    @patch('os.unlink')
    @patch('os.rename')
    @patch('os.path.islink')
    @patch('os.readlink')
    def test_write_xml(self, mock_readlink, mock_islink, mock_rename,
                       mock_unlink, mock_fdopen, mock_open, mock_load_xml):
        fname = "clients.xml"
        config = self.get_obj(fname)
        fpath = os.path.join(self.metadata.data, fname)
        tmpfile = "%s.new" % fpath
        linkdest = os.path.join(self.metadata.data, "client-link.xml")

        def reset():
            mock_readlink.reset_mock()
            mock_islink.reset_mock()
            mock_rename.reset_mock()
            mock_unlink.reset_mock()
            mock_fdopen.reset_mock()
            mock_open.reset_mock()
            mock_load_xml.reset_mock()

        mock_islink.return_value = False

        # basic test - everything works
        config.write_xml(fpath, get_clients_test_tree())
        mock_open.assert_called_with(tmpfile,
                                     os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        mock_fdopen.assert_called_with(mock_open.return_value, 'w')
        self.assertTrue(mock_fdopen.return_value.write.called)
        mock_islink.assert_called_with(fpath)
        mock_rename.assert_called_with(tmpfile, fpath)
        mock_load_xml.assert_called_with()

        # test: clients.xml.new is locked the first time we write it
        def rv(fname, mode):
            mock_open.side_effect = None
            raise OSError(17, fname)

        reset()
        mock_open.side_effect = rv
        config.write_xml(fpath, get_clients_test_tree())
        self.assertItemsEqual(mock_open.call_args_list,
                              [call(tmpfile,
                                    os.O_CREAT | os.O_EXCL | os.O_WRONLY),
                               call(tmpfile,
                                    os.O_CREAT | os.O_EXCL | os.O_WRONLY)])
        mock_fdopen.assert_called_with(mock_open.return_value, 'w')
        self.assertTrue(mock_fdopen.return_value.write.called)
        mock_islink.assert_called_with(fpath)
        mock_rename.assert_called_with(tmpfile, fpath)
        mock_load_xml.assert_called_with()

        # test writing a symlinked clients.xml
        reset()
        mock_open.side_effect = None
        mock_islink.return_value = True
        mock_readlink.return_value = linkdest
        config.write_xml(fpath, get_clients_test_tree())
        mock_rename.assert_called_with(tmpfile, linkdest)
        mock_load_xml.assert_called_with()

        # test failure of os.rename()
        reset()
        mock_rename.side_effect = OSError
        self.assertRaises(Bcfg2.Server.Plugin.MetadataRuntimeError,
                          config.write_xml, fpath, get_clients_test_tree())
        mock_unlink.assert_called_with(tmpfile)

        # test failure of file.write()
        reset()
        mock_open.return_value.write.side_effect = IOError
        self.assertRaises(Bcfg2.Server.Plugin.MetadataRuntimeError,
                          config.write_xml, fpath, get_clients_test_tree())
        mock_unlink.assert_called_with(tmpfile)

        # test failure of os.open() (other than EEXIST)
        reset()
        mock_open.side_effect = OSError
        self.assertRaises(Bcfg2.Server.Plugin.MetadataRuntimeError,
                          config.write_xml, fpath, get_clients_test_tree())

        # test failure of os.fdopen()
        reset()
        mock_fdopen.side_effect = OSError
        self.assertRaises(Bcfg2.Server.Plugin.MetadataRuntimeError,
                          config.write_xml, fpath, get_clients_test_tree())

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch('lxml.etree.parse')
    def test_find_xml_for_xpath(self, mock_parse):
        config = self.get_obj("groups.xml")
        config.basedata = get_groups_test_tree()
        xpath = "//Group[@name='group1']"
        self.assertItemsEqual(config.find_xml_for_xpath(xpath),
                              dict(filename=os.path.join(self.metadata.data,
                                                         "groups.xml"),
                                   xmltree=get_groups_test_tree(),
                                   xquery=get_groups_test_tree().xpath(xpath)))

        self.assertEqual(config.find_xml_for_xpath("//boguselement"), dict())

        config.extras = [os.path.join(self.metadata.data, p)
                         for p in ["foo.xml", "bar.xml", "clients.xml"]]

        def parse_side_effect(fname, parser=Bcfg2.Server.XMLParser):
            if fname == os.path.join(self.metadata.data, "clients.xml"):
                return get_clients_test_tree()
            else:
                return lxml.etree.XML("<null/>").getroottree()

        mock_parse.side_effect = parse_side_effect
        xpath = "//Client[@secure='true']"
        self.assertItemsEqual(config.find_xml_for_xpath(xpath),
                              dict(filename=os.path.join(self.metadata.data,
                                                         "clients.xml"),
                                   xmltree=get_clients_test_tree(),
                                   xquery=get_clients_test_tree().xpath(xpath)))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml")
    def test_HandleEvent(self, mock_load_xml):
        config = self.get_obj("groups.xml")
        evt = Mock()
        evt.filename = os.path.join(self.metadata.data, "groups.xml")
        evt.code2str = Mock(return_value="changed")
        self.assertTrue(config.HandleEvent(evt))
        mock_load_xml.assert_called_with()


class TestClientMetadata(Bcfg2TestCase):
    def test_inGroup(self):
        cm = ClientMetadata("client1", "group1", ["group1", "group2"],
                            ["bundle1"], [], [], [], None, None, None, None)
        self.assertTrue(cm.inGroup("group1"))
        self.assertFalse(cm.inGroup("group3"))


class TestMetadata(_TestMetadata, TestClientRunHooks, TestDatabaseBacked):
    test_obj = Metadata

    def setUp(self):
        _TestMetadata.setUp(self)
        TestClientRunHooks.setUp(self)
        TestDatabaseBacked.setUp(self)
        Bcfg2.Options.setup.metadata_db = False
        Bcfg2.Options.setup.authentication = "cert+password"

    def get_obj(self, core=None):
        return get_metadata_object(core=core)

    @skipUnless(HAS_DJANGO, "Django not found")
    def test__use_db(self):
        # with the way we've set up our metadata tests, it's unweildy
        # to test _use_db.  however, given the way get_obj works, if
        # there was a bug in _use_db it'd be almost certain to shake
        # out in the rest of the testing.
        pass

    def get_nonexistent_client(self, metadata, prefix="newclient"):
        if metadata is None:
            metadata = self.load_clients_data()
        i = 0
        client_name = "%s%s" % (prefix, i)
        while client_name in metadata.clients:
            i += 1
            client_name = "%s%s" % (prefix, i)
        return client_name

    @patch("Bcfg2.Server.FileMonitor.get_fam")
    def test__init(self, mock_get_fam):
        core = MagicMock()
        metadata = self.get_obj(core=core)
        self.assertEqual(len(metadata.states), 2)
        mock_get_fam.return_value.AddMonitor.assert_any_call(
            os.path.join(metadata.data, "groups.xml"),
            metadata)
        mock_get_fam.return_value.AddMonitor.assert_any_call(
            os.path.join(metadata.data, "clients.xml"),
            metadata)

    @patch('os.makedirs', Mock())
    @patch('%s.open' % builtins)
    def test_init_repo(self, mock_open):
        Metadata.init_repo(datastore,
                           groups_xml="groups", clients_xml="clients")
        mock_open.assert_any_call(os.path.join(datastore, "Metadata",
                                               "groups.xml"), "w")
        mock_open.assert_any_call(os.path.join(datastore, "Metadata",
                                               "clients.xml"), "w")

    def test_search_xdata(self):
        # test finding a node with the proper name
        metadata = self.get_obj()
        tree = get_groups_test_tree()
        res = metadata._search_xdata("Group", "group1", tree)
        self.assertIsInstance(res, lxml.etree._Element)
        self.assertEqual(res.get("name"), "group1")

        # test finding a node with the wrong name but correct alias
        metadata = self.get_obj()
        tree = get_clients_test_tree()
        res = metadata._search_xdata("Client", "alias3", tree, alias=True)
        self.assertIsInstance(res, lxml.etree._Element)
        self.assertNotEqual(res.get("name"), "alias3")

        # test failure finding a node
        metadata = self.get_obj()
        tree = get_clients_test_tree()
        res = metadata._search_xdata("Client",
                                     self.get_nonexistent_client(metadata),
                                     tree, alias=True)
        self.assertIsNone(res)

    def search_xdata(self, tag, name, tree, alias=False):
        metadata = self.get_obj()
        res = metadata._search_xdata(tag, name, tree, alias=alias)
        self.assertIsInstance(res, lxml.etree._Element)
        if not alias:
            self.assertEqual(res.get("name"), name)

    def test_search_group(self):
        # test finding a group with the proper name
        tree = get_groups_test_tree()
        self.search_xdata("Group", "group1", tree)

    def test_search_bundle(self):
        # test finding a bundle with the proper name
        tree = get_groups_test_tree()
        self.search_xdata("Bundle", "bundle1", tree)

    def test_search_client(self):
        # test finding a client with the proper name
        tree = get_clients_test_tree()
        self.search_xdata("Client", "client1", tree, alias=True)
        self.search_xdata("Client", "alias1", tree, alias=True)

    def test_add_group(self):
        metadata = self.get_obj()
        metadata.groups_xml.write = Mock()
        metadata.groups_xml.load_xml = Mock()
        metadata.groups_xml.data = lxml.etree.XML('<Groups/>').getroottree()
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.add_group("test1", dict())
        metadata.groups_xml.write.assert_any_call()
        grp = metadata.search_group("test1", metadata.groups_xml.base_xdata)
        self.assertIsNotNone(grp)
        self.assertEqual(grp.attrib, dict(name='test1'))

        # have to call this explicitly -- usually load_xml does this
        # on FAM events
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.add_group("test2", dict(foo='bar'))
        metadata.groups_xml.write.assert_any_call()
        grp = metadata.search_group("test2", metadata.groups_xml.base_xdata)
        self.assertIsNotNone(grp)
        self.assertEqual(grp.attrib, dict(name='test2', foo='bar'))

        # have to call this explicitly -- usually load_xml does this
        # on FAM events
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.groups_xml.write.reset_mock()
        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.add_group,
                          "test1", dict())
        self.assertFalse(metadata.groups_xml.write.called)

    def test_update_group(self):
        metadata = self.get_obj()
        metadata.groups_xml.write_xml = Mock()
        metadata.groups_xml.load_xml = Mock()
        metadata.groups_xml.data = copy.deepcopy(get_groups_test_tree())
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.update_group("group1", dict(foo="bar"))
        grp = metadata.search_group("group1", metadata.groups_xml.base_xdata)
        self.assertIsNotNone(grp)
        self.assertIn("foo", grp.attrib)
        self.assertEqual(grp.get("foo"), "bar")
        self.assertTrue(metadata.groups_xml.write_xml.called)

        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.update_group,
                          "bogus_group", dict())

    def test_remove_group(self):
        metadata = self.get_obj()
        metadata.groups_xml.write_xml = Mock()
        metadata.groups_xml.load_xml = Mock()
        metadata.groups_xml.data = copy.deepcopy(get_groups_test_tree())
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.remove_group("group5")
        grp = metadata.search_group("group5", metadata.groups_xml.base_xdata)
        self.assertIsNone(grp)
        self.assertTrue(metadata.groups_xml.write_xml.called)

        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.remove_group,
                          "bogus_group")

    def test_add_bundle(self):
        metadata = self.get_obj()
        metadata.groups_xml.write = Mock()
        metadata.groups_xml.load_xml = Mock()
        metadata.groups_xml.data = lxml.etree.XML('<Groups/>').getroottree()
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.add_bundle("bundle1")
        metadata.groups_xml.write.assert_any_call()
        bundle = metadata.search_bundle("bundle1",
                                        metadata.groups_xml.base_xdata)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle.attrib, dict(name='bundle1'))

        # have to call this explicitly -- usually load_xml does this
        # on FAM events
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.groups_xml.write.reset_mock()
        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.add_bundle,
                          "bundle1")
        self.assertFalse(metadata.groups_xml.write.called)

    def test_remove_bundle(self):
        metadata = self.get_obj()
        metadata.groups_xml.write_xml = Mock()
        metadata.groups_xml.load_xml = Mock()
        metadata.groups_xml.data = copy.deepcopy(get_groups_test_tree())
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.remove_bundle("bundle1")
        grp = metadata.search_bundle("bundle1", metadata.groups_xml.base_xdata)
        self.assertIsNone(grp)
        self.assertTrue(metadata.groups_xml.write_xml.called)

        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.remove_bundle,
                          "bogus_bundle")

    def test_add_client(self):
        metadata = self.get_obj()
        metadata.clients_xml.write = Mock()
        metadata.clients_xml.load_xml = Mock()
        metadata.clients_xml.data = lxml.etree.XML('<Clients/>').getroottree()
        metadata.clients_xml.basedata = copy.copy(metadata.clients_xml.data)

        new1 = self.get_nonexistent_client(metadata)
        new1_client = metadata.add_client(new1, dict())
        metadata.clients_xml.write.assert_any_call()
        grp = metadata.search_client(new1, metadata.clients_xml.base_xdata)
        self.assertIsNotNone(grp)
        self.assertEqual(grp.attrib, dict(name=new1))

        # have to call this explicitly -- usually load_xml does this
        # on FAM events
        metadata.clients_xml.basedata = copy.copy(metadata.clients_xml.data)
        metadata._handle_clients_xml_event(Mock())

        new2 = self.get_nonexistent_client(metadata)
        metadata.add_client(new2, dict(foo='bar'))
        metadata.clients_xml.write.assert_any_call()
        grp = metadata.search_client(new2, metadata.clients_xml.base_xdata)
        self.assertIsNotNone(grp)
        self.assertEqual(grp.attrib, dict(name=new2, foo='bar'))

        # have to call this explicitly -- usually load_xml does this
        # on FAM events
        metadata.clients_xml.basedata = copy.copy(metadata.clients_xml.data)

        metadata.clients_xml.write.reset_mock()
        self.assertXMLEqual(metadata.add_client(new1, dict()),
                            new1_client)
        self.assertFalse(metadata.clients_xml.write.called)

    def test_update_client(self):
        metadata = self.get_obj()
        metadata.clients_xml.write_xml = Mock()
        metadata.clients_xml.load_xml = Mock()
        metadata.clients_xml.data = copy.deepcopy(get_clients_test_tree())
        metadata.clients_xml.basedata = copy.copy(metadata.clients_xml.data)

        metadata.update_client("client1", dict(foo="bar"))
        grp = metadata.search_client("client1", metadata.clients_xml.base_xdata)
        self.assertIsNotNone(grp)
        self.assertIn("foo", grp.attrib)
        self.assertEqual(grp.get("foo"), "bar")
        self.assertTrue(metadata.clients_xml.write_xml.called)

        new = self.get_nonexistent_client(metadata)
        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.update_client,
                          new, dict())

    def load_clients_data(self, metadata=None, xdata=None):
        if metadata is None:
            metadata = self.get_obj()
        metadata.clients_xml.data = \
            xdata or copy.deepcopy(get_clients_test_tree())
        metadata.clients_xml.basedata = copy.copy(metadata.clients_xml.data)
        evt = Mock()
        evt.filename = os.path.join(datastore, "Metadata", "clients.xml")
        evt.code2str = Mock(return_value="changed")
        metadata.HandleEvent(evt)
        return metadata

    def test_handle_clients_xml_event(self):
        metadata = self.get_obj()
        metadata.profiles = ["group1", "group2"]

        metadata.clients_xml = Mock()
        metadata.clients_xml.xdata = copy.deepcopy(get_clients_test_tree())
        metadata._handle_clients_xml_event(Mock())

        if not Bcfg2.Options.setup.metadata_db:
            self.assertItemsEqual(metadata.clients,
                                  dict([(c.get("name"), c.get("profile"))
                                        for c in get_clients_test_tree().findall("//Client")]))
        aliases = dict([(a.get("name"), a.getparent().get("name"))
                        for a in get_clients_test_tree().findall("//Alias")])
        self.assertItemsEqual(metadata.aliases, aliases)

        raliases = dict([(c.get("name"), set())
                         for c in get_clients_test_tree().findall("//Client")])
        for alias in get_clients_test_tree().findall("//Alias"):
            raliases[alias.getparent().get("name")].add(alias.get("name"))
        self.assertItemsEqual(metadata.raliases, raliases)

        self.assertEqual(metadata.secure,
                         [c.get("name")
                          for c in get_clients_test_tree().findall("//Client[@secure='true']")])
        self.assertEqual(metadata.floating, ["client1", "client10"])

        addresses = dict([(c.get("address"), [])
                           for c in get_clients_test_tree().findall("//*[@address]")])
        raddresses = dict()
        for client in get_clients_test_tree().findall("//Client[@address]"):
            addresses[client.get("address")].append(client.get("name"))
            try:
                raddresses[client.get("name")].append(client.get("address"))
            except KeyError:
                raddresses[client.get("name")] = [client.get("address")]
        for alias in get_clients_test_tree().findall("//Alias[@address]"):
            addresses[alias.get("address")].append(alias.getparent().get("name"))
            try:
                raddresses[alias.getparent().get("name")].append(alias.get("address"))
            except KeyError:
                raddresses[alias.getparent().get("name")] = alias.get("address")

        self.assertItemsEqual(metadata.addresses, addresses)
        self.assertItemsEqual(metadata.raddresses, raddresses)
        self.assertTrue(metadata.states['clients.xml'])

    def load_groups_data(self, metadata=None, xdata=None):
        if metadata is None:
            metadata = self.get_obj()
        metadata.groups_xml.data = \
            xdata or copy.deepcopy(get_groups_test_tree())
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)
        evt = Mock()
        evt.filename = os.path.join(datastore, "Metadata", "groups.xml")
        evt.code2str = Mock(return_value="changed")
        metadata.HandleEvent(evt)
        return metadata

    def test_handle_groups_xml_event(self):
        metadata = self.get_obj()
        metadata.groups_xml = Mock()
        metadata.groups_xml.xdata = get_groups_test_tree()
        metadata._handle_groups_xml_event(Mock())

        self.assertTrue(metadata.states['groups.xml'])
        self.assertTrue(metadata.groups['group1'].is_public)
        self.assertTrue(metadata.groups['group2'].is_public)
        self.assertFalse(metadata.groups['group3'].is_public)
        self.assertTrue(metadata.groups['group1'].is_profile)
        self.assertTrue(metadata.groups['group2'].is_profile)
        self.assertFalse(metadata.groups['group3'].is_profile)
        self.assertItemsEqual(metadata.groups.keys(),
                              set(g.get("name")
                                  for g in get_groups_test_tree().findall("//Group")))
        self.assertEqual(metadata.groups['group1'].category, 'category1')
        self.assertEqual(metadata.groups['group2'].category, 'category1')
        self.assertEqual(metadata.groups['group3'].category, 'category2')
        self.assertEqual(metadata.groups['group4'].category, 'category1')
        self.assertEqual(metadata.default, "group1")

        all_groups = set()
        negated_groups = set()
        for group in get_groups_test_tree().xpath("//Groups/Client//*") + \
                get_groups_test_tree().xpath("//Groups/Group//*"):
            if group.tag == 'Group' and not group.getchildren():
                if group.get("negate", "false").lower() == 'true':
                    negated_groups.add(group.get("name"))
                else:
                    all_groups.add(group.get("name"))
        self.assertItemsEqual(metadata.ordered_groups, all_groups)
        self.assertItemsEqual(metadata.group_membership.keys(), all_groups)
        self.assertItemsEqual(metadata.negated_groups.keys(), negated_groups)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_set_profile(self):
        metadata = self.get_obj()
        if 'clients.xml' in metadata.states:
            metadata.states['clients.xml'] = False
            self.assertRaises(Bcfg2.Server.Plugin.MetadataRuntimeError,
                              metadata.set_profile,
                              None, None, None)

        self.load_groups_data(metadata=metadata)
        self.load_clients_data(metadata=metadata)

        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.set_profile,
                          "client1", "group5", None)

        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.set_profile,
                          "client1", "group3", None)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_set_profile_db(self):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        if metadata._use_db:
            profile = "group1"
            client_name = self.get_nonexistent_client(metadata)
            metadata.set_profile(client_name, profile, None)
            self.assertIn(client_name, metadata.clients)
            self.assertRaises(Bcfg2.Server.Plugin.PluginExecutionError,
                              metadata.set_profile,
                              client_name, profile, None)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.add_client")
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.update_client")
    def test_set_profile_xml(self, mock_update_client, mock_add_client):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        if not metadata._use_db:
            metadata.clients_xml.write = Mock()
            metadata.core.build_metadata = Mock()
            metadata.core.build_metadata.side_effect = \
                lambda c: metadata.get_initial_metadata(c)

            metadata.set_profile("client1", "group2", None)
            mock_update_client.assert_called_with("client1",
                                                  dict(profile="group2"))
            self.assertEqual(metadata.clientgroups["client1"], ["group2"])

            metadata.clients_xml.write.reset_mock()
            new1 = self.get_nonexistent_client(metadata)
            metadata.set_profile(new1, "group1", None)
            mock_add_client.assert_called_with(new1, dict(profile="group1"))
            metadata.clients_xml.write.assert_any_call()
            self.assertEqual(metadata.clientgroups[new1], ["group1"])

            metadata.clients_xml.write.reset_mock()
            new2 = self.get_nonexistent_client(metadata)
            metadata.session_cache[('1.2.3.6', None)] = (None, new2)
            metadata.set_profile("uuid_new", "group1", ('1.2.3.6', None))
            mock_add_client.assert_called_with(new2,
                                               dict(uuid='uuid_new',
                                                    profile="group1",
                                                    address='1.2.3.6'))
            metadata.clients_xml.write.assert_any_call()
            self.assertEqual(metadata.clientgroups["uuid_new"], ["group1"])

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("socket.getnameinfo")
    def test_resolve_client(self, mock_getnameinfo):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        metadata.session_cache[('1.2.3.3', None)] = (time.time(), 'client3')
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None)), 'client3')

        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.resolve_client,
                          ('1.2.3.2', None))
        self.assertEqual(metadata.resolve_client(('1.2.3.1', None)), 'client1')

        metadata.session_cache[('1.2.3.3', None)] = (time.time() - 100,
                                                     'client3')
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None)), 'client3')
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None),
                                                 cleanup_cache=True), 'client3')
        self.assertEqual(metadata.session_cache, dict())

        mock_getnameinfo.return_value = ('client6', [], ['1.2.3.6'])
        self.assertEqual(metadata.resolve_client(('1.2.3.6', 6789)), 'client6')
        mock_getnameinfo.assert_called_with(('1.2.3.6', 6789), socket.NI_NAMEREQD)

        mock_getnameinfo.reset_mock()
        mock_getnameinfo.return_value = ('alias3', [], ['1.2.3.7'])
        self.assertEqual(metadata.resolve_client(('1.2.3.7', 6789)), 'client4')
        mock_getnameinfo.assert_called_with(('1.2.3.7', 6789), socket.NI_NAMEREQD)

        mock_getnameinfo.reset_mock()
        mock_getnameinfo.return_value = None
        mock_getnameinfo.side_effect = socket.herror
        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.resolve_client,
                          ('1.2.3.8', 6789))
        mock_getnameinfo.assert_called_with(('1.2.3.8', 6789), socket.NI_NAMEREQD)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.write_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.ClientMetadata")
    def test_get_initial_metadata(self, mock_clientmetadata):
        metadata = self.get_obj()
        if 'clients.xml' in metadata.states:
            metadata.states['clients.xml'] = False
            self.assertRaises(Bcfg2.Server.Plugin.MetadataRuntimeError,
                              metadata.get_initial_metadata, None)

        self.load_groups_data(metadata=metadata)
        self.load_clients_data(metadata=metadata)

        # test address, password
        metadata.get_initial_metadata("client1")
        mock_clientmetadata.assert_called_with("client1", "group1",
                                               set(["group1"]), set(), set(),
                                               set(["1.2.3.1"]),
                                               dict(category1='group1'), None,
                                               'password2', None,
                                               metadata.query)

        # test address, bundles, category suppression
        metadata.get_initial_metadata("client2")
        mock_clientmetadata.assert_called_with("client2", "group2",
                                               set(["group2"]),
                                               set(["bundle1", "bundle2"]),
                                               set(), set(["1.2.3.2"]),
                                               dict(category1="group2"),
                                               None, None, None,
                                               metadata.query)

        # test aliases, address, uuid, password
        imd = metadata.get_initial_metadata("alias1")
        mock_clientmetadata.assert_called_with("client3", "group1",
                                               set(["group1"]), set(),
                                               set(['alias1']),
                                               set(["1.2.3.3"]),
                                               dict(category1="group1"),
                                               'uuid1', 'password2', None,
                                               metadata.query)

        # test new client creation
        new1 = self.get_nonexistent_client(metadata)
        imd = metadata.get_initial_metadata(new1)
        mock_clientmetadata.assert_called_with(new1, "group1", set(["group1"]),
                                               set(), set(), set(),
                                               dict(category1="group1"), None,
                                               None, None, metadata.query)

        # test nested groups, address, per-client groups
        imd = metadata.get_initial_metadata("client8")
        mock_clientmetadata.assert_called_with("client8", "group1",
                                               set(["group1", "group8",
                                                    "group9", "group10"]),
                                               set(),
                                               set(), set(["1.2.3.5"]),
                                               dict(category1="group1"),
                                               None, None, None, metadata.query)

        # test setting per-client groups, group negation, nested groups
        imd = metadata.get_initial_metadata("client9")
        mock_clientmetadata.assert_called_with("client9", "group2",
                                               set(["group2", "group8",
                                                    "group11"]),
                                               set(["bundle1", "bundle2"]),
                                               set(), set(),
                                               dict(category1="group2"), None,
                                               "password3", None,
                                               metadata.query)

        # test new client with no default profile
        metadata.default = None
        new2 = self.get_nonexistent_client(metadata)
        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.get_initial_metadata, new2)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_merge_groups(self):
        metadata = self.get_obj()
        self.load_groups_data(metadata=metadata)
        self.load_clients_data(metadata=metadata)

        self.assertEqual(metadata._merge_groups("client1", set(["group1"]),
                                                categories=dict(group1="category1")),
                         (set(["group1"]), dict(group1="category1")))

        self.assertEqual(metadata._merge_groups("client8",
                                                set(["group1", "group8", "group9"]),
                                                categories=dict(group1="category1")),
                         (set(["group1", "group8", "group9", "group10"]),
                          dict(group1="category1")))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_get_all_group_names(self):
        metadata = self.load_groups_data()
        self.assertItemsEqual(metadata.get_all_group_names(),
                              set([g.get("name")
                                   for g in get_groups_test_tree().findall("//Group")]))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_get_all_groups_in_category(self):
        metadata = self.load_groups_data()
        self.assertItemsEqual(metadata.get_all_groups_in_category("category1"),
                              set([g.get("name")
                                   for g in get_groups_test_tree().findall("//Group[@category='category1']")]))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_get_client_names_by_profiles(self):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        metadata.core.build_metadata = Mock()
        metadata.core.build_metadata.side_effect = \
            lambda c: metadata.get_initial_metadata(c)
        self.assertItemsEqual(metadata.get_client_names_by_profiles(["group2"]),
                              [c.get("name")
                               for c in get_clients_test_tree().findall("//Client[@profile='group2']")])

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_get_client_names_by_groups(self):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        # this is not the best test in the world, since we mock
        # core.build_metadata to just build _initial_ metadata, which
        # is not at all the same thing.  it turns out that mocking
        # this out without starting a Bcfg2 server is pretty
        # non-trivial, so this works-ish
        metadata.core.build_metadata = Mock()
        metadata.core.build_metadata.side_effect = \
            lambda c: metadata.get_initial_metadata(c)
        self.assertItemsEqual(metadata.get_client_names_by_groups(["group2"]),
                              [c.get("name")
                               for c in get_clients_test_tree().findall("//Client[@profile='group2']")])

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_merge_additional_groups(self):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        imd = metadata.get_initial_metadata("client2")

        # test adding a group excluded by categories
        oldgroups = imd.groups
        metadata.merge_additional_groups(imd, ["group4"])
        self.assertEqual(imd.groups, oldgroups)

        # test adding a private group
        oldgroups = imd.groups
        metadata.merge_additional_groups(imd, ["group3"])
        self.assertEqual(imd.groups, oldgroups)

        # test adding groups with bundles
        oldgroups = imd.groups
        oldbundles = imd.bundles
        metadata.merge_additional_groups(imd, ["group7"])
        self.assertEqual(imd.groups, oldgroups.union(["group7"]))
        self.assertEqual(imd.bundles, oldbundles.union(["bundle3"]))

        # test adding groups with categories
        oldgroups = imd.groups
        metadata.merge_additional_groups(imd, ["group12"])
        self.assertEqual(imd.groups, oldgroups.union(["group12"]))
        self.assertIn("category3", imd.categories)
        self.assertEqual(imd.categories["category3"], "group12")

        # test adding multiple groups
        imd = metadata.get_initial_metadata("client2")
        oldgroups = imd.groups
        metadata.merge_additional_groups(imd, ["group6", "group8"])
        self.assertItemsEqual(imd.groups,
                              oldgroups.union(["group6", "group8", "group9"]))

        # test adding a group that is not defined in groups.xml
        imd = metadata.get_initial_metadata("client2")
        oldgroups = imd.groups
        metadata.merge_additional_groups(imd, ["group6", "newgroup"])
        self.assertItemsEqual(imd.groups,
                              oldgroups.union(["group6", "newgroup"]))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_merge_additional_data(self):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        imd = metadata.get_initial_metadata("client1")

        # we need to use a unique attribute name for this test.  this
        # is probably overkill, but it works
        pattern = "connector%d"
        for i in range(0, 100):
            connector = pattern % i
            if not hasattr(imd, connector):
                break
        self.assertFalse(hasattr(imd, connector),
                         "Could not find unique connector name to test "
                         "merge_additional_data()")

        metadata.merge_additional_data(imd, connector, "test data")
        self.assertEqual(getattr(imd, connector), "test data")
        self.assertIn(connector, imd.connectors)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.resolve_client")
    def test_validate_client_address(self, mock_resolve_client):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        self.assertTrue(metadata.validate_client_address("client1",
                                                         (None, None)))
        self.assertTrue(metadata.validate_client_address("client2",
                                                         ("1.2.3.2", None)))
        self.assertFalse(metadata.validate_client_address("client2",
                                                          ("1.2.3.8", None)))
        self.assertTrue(metadata.validate_client_address("client4",
                                                         ("1.2.3.2", None)))
        # this is upper case to ensure that case is folded properly in
        # validate_client_address()
        mock_resolve_client.return_value = "CLIENT4"
        self.assertTrue(metadata.validate_client_address("client4",
                                                         ("1.2.3.7", None)))
        mock_resolve_client.assert_called_with(("1.2.3.7", None))

        mock_resolve_client.reset_mock()
        self.assertFalse(metadata.validate_client_address("client5",
                                                         ("1.2.3.5", None)))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.validate_client_address")
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.resolve_client")
    def test_AuthenticateConnection(self, mock_resolve_client,
                                    mock_validate_client_address):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        metadata.password = "password1"

        cert = dict(subject=[[("commonName", "client1")]])
        mock_validate_client_address.return_value = False
        self.assertFalse(metadata.AuthenticateConnection(cert, "root", None,
                                                         "1.2.3.1"))
        mock_validate_client_address.return_value = True
        self.assertTrue(metadata.AuthenticateConnection(cert, "root", None,
                                                        "1.2.3.1"))
        # floating cert-auth clients add themselves to the cache
        self.assertIn("1.2.3.1", metadata.session_cache)
        self.assertEqual(metadata.session_cache["1.2.3.1"][1], "client1")

        cert = dict(subject=[[("commonName", "client7")]])
        self.assertTrue(metadata.AuthenticateConnection(cert, "root", None,
                                                        "1.2.3.4"))
        # non-floating cert-auth clients do not add themselves to the cache
        self.assertNotIn("1.2.3.4", metadata.session_cache)

        cert = dict(subject=[[("commonName", "client8")]])

        mock_resolve_client.return_value = "client5"
        self.assertTrue(metadata.AuthenticateConnection(None, "root",
                                                        "password1", "1.2.3.8"))

        mock_resolve_client.side_effect = \
            Bcfg2.Server.Plugin.MetadataConsistencyError
        self.assertFalse(metadata.AuthenticateConnection(None, "root",
                                                         "password1",
                                                         "1.2.3.8"))

        # secure mode, no password
        self.assertFalse(metadata.AuthenticateConnection(None, 'client2', None,
                                                         "1.2.3.2"))

        self.assertTrue(metadata.AuthenticateConnection(None, 'uuid1',
                                                        "password1", "1.2.3.3"))
        # non-root, non-cert clients populate session cache
        self.assertIn("1.2.3.3", metadata.session_cache)
        self.assertEqual(metadata.session_cache["1.2.3.3"][1], "client3")

        # use alternate password
        self.assertTrue(metadata.AuthenticateConnection(None, 'client3',
                                                        "password2", "1.2.3.3"))

        # test secure mode
        self.assertFalse(metadata.AuthenticateConnection(None, 'client9',
                                                         "password1",
                                                         "1.2.3.9"))
        self.assertTrue(metadata.AuthenticateConnection(None, 'client9',
                                                        "password3", "1.2.3.9"))

        self.assertFalse(metadata.AuthenticateConnection(None, "client5",
                                                         "password2",
                                                         "1.2.3.7"))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.update_client")
    def test_end_statistics(self, mock_update_client):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        md = Mock()
        md.hostname = "client6"
        metadata.end_statistics(md)
        mock_update_client.assert_called_with(md.hostname, dict(auth='cert'))

        mock_update_client.reset_mock()
        md.hostname = "client5"
        metadata.end_statistics(md)
        self.assertFalse(mock_update_client.called)

    def test_viz(self):
        pass


class TestMetadataBase(TestMetadata):
    """ base test object for testing Metadata with database enabled """
    __test__ = False

    @skipUnless(HAS_DJANGO, "Django not found")
    def setUp(self):
        _TestMetadata.setUp(self)
        TestClientRunHooks.setUp(self)
        TestDatabaseBacked.setUp(self)
        Bcfg2.Options.setup.metadata_db = True
        syncdb(TestMetadataDB)

    def load_clients_data(self, metadata=None, xdata=None):
        if metadata is None:
            metadata = get_obj()
        for client in get_clients_test_tree().findall("Client"):
            metadata.add_client(client.get("name"))
        return metadata

    def get_nonexistent_client(self, _, prefix="newclient"):
        clients = [o.hostname for o in MetadataClientModel.objects.all()]
        i = 0
        client_name = "%s%s" % (prefix, i)
        while client_name in clients:
            i += 1
            client_name = "%s%s" % (prefix, i)
        return client_name

    @patch('os.path.exists')
    @patch('Bcfg2.Server.FileMonitor.get_fam')
    def test__init(self, mock_get_fam, mock_exists):
        mock_exists.return_value = False
        metadata = self.get_obj()
        self.assertIsInstance(metadata, Bcfg2.Server.Plugin.DatabaseBacked)
        mock_get_fam.return_value.AddMonitor.assert_called_with(
            os.path.join(metadata.data, "groups.xml"),
            metadata)

        mock_exists.return_value = True
        mock_get_fam.reset_mock()
        metadata = self.get_obj()
        mock_get_fam.return_value.AddMonitor.assert_any_call(
            os.path.join(metadata.data, "groups.xml"),
            metadata)
        mock_get_fam.return_value.AddMonitor.assert_any_call(
            os.path.join(metadata.data, "clients.xml"),
            metadata)

    def test_add_group(self):
        pass

    def test_add_bundle(self):
        pass

    def test_add_client(self):
        metadata = self.get_obj()
        hostname = self.get_nonexistent_client(metadata)
        client = metadata.add_client(hostname)
        self.assertIsInstance(client, MetadataClientModel)
        self.assertEqual(client.hostname, hostname)
        self.assertIn(hostname, metadata.clients)
        self.assertIn(hostname, metadata.list_clients())
        self.assertItemsEqual(metadata.clients,
                              [c.hostname
                               for c in MetadataClientModel.objects.all()])

    def test_update_group(self):
        pass

    def test_update_bundle(self):
        pass

    def test_update_client(self):
        pass

    def test_list_clients(self):
        metadata = self.get_obj()
        self.assertItemsEqual(metadata.list_clients(),
                              [c.hostname
                               for c in MetadataClientModel.objects.all()])

    def test_remove_group(self):
        pass

    def test_remove_bundle(self):
        pass

    def test_remove_client(self):
        metadata = self.get_obj()
        client_name = self.get_nonexistent_client(metadata)

        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.remove_client,
                          client_name)

        metadata.add_client(client_name)
        metadata.remove_client(client_name)
        self.assertNotIn(client_name, metadata.clients)
        self.assertNotIn(client_name, metadata.list_clients())
        self.assertItemsEqual(metadata.clients,
                              [c.hostname
                               for c in MetadataClientModel.objects.all()])

    def test_process_statistics(self):
        pass


class TestMetadata_NoClientsXML(TestMetadataBase):
    """ test Metadata without a clients.xml. we have to disable or
    override tests that rely on client options """
    __test__ = True

    def load_groups_data(self, metadata=None, xdata=None):
        if metadata is None:
            metadata = self.get_obj()
        if not xdata:
            xdata = copy.deepcopy(get_groups_test_tree())
            for client in get_clients_test_tree().findall("Client"):
                newclient = \
                    lxml.etree.SubElement(xdata.getroot(),
                                          "Client", name=client.get("name"))
                lxml.etree.SubElement(newclient, "Group",
                                      name=client.get("profile"))
        metadata.groups_xml.data = xdata
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)
        evt = Mock()
        evt.filename = os.path.join(datastore, "Metadata", "groups.xml")
        evt.code2str = Mock(return_value="changed")
        metadata.HandleEvent(evt)
        return metadata

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.write_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.ClientMetadata")
    def test_get_initial_metadata(self, mock_clientmetadata):
        metadata = self.get_obj()
        if 'clients.xml' in metadata.states:
            metadata.states['clients.xml'] = False
            self.assertRaises(Bcfg2.Server.Plugin.MetadataRuntimeError,
                              metadata.get_initial_metadata, None)

        self.load_groups_data(metadata=metadata)
        self.load_clients_data(metadata=metadata)

        # test basic client metadata
        metadata.get_initial_metadata("client1")
        mock_clientmetadata.assert_called_with("client1", "group1",
                                               set(["group1"]), set(), set(),
                                               set(), dict(category1='group1'),
                                               None, None, None, metadata.query)

        # test bundles, category suppression
        metadata.get_initial_metadata("client2")
        mock_clientmetadata.assert_called_with("client2", "group2",
                                               set(["group2"]),
                                               set(["bundle1", "bundle2"]),
                                               set(), set(),
                                               dict(category1="group2"), None,
                                               None, None, metadata.query)

        # test new client creation
        new1 = self.get_nonexistent_client(metadata)
        imd = metadata.get_initial_metadata(new1)
        mock_clientmetadata.assert_called_with(new1, "group1", set(["group1"]),
                                               set(), set(), set(),
                                               dict(category1="group1"), None,
                                               None, None, metadata.query)

        # test nested groups, per-client groups
        imd = metadata.get_initial_metadata("client8")
        mock_clientmetadata.assert_called_with("client8", "group1",
                                               set(["group1", "group8",
                                                    "group9", "group10"]),
                                               set(), set(), set(),
                                               dict(category1="group1"), None,
                                               None, None, metadata.query)

        # test per-client groups, group negation, nested groups
        imd = metadata.get_initial_metadata("client9")
        mock_clientmetadata.assert_called_with("client9", "group2",
                                               set(["group2", "group8",
                                                    "group11"]),
                                               set(["bundle1", "bundle2"]),
                                               set(), set(),
                                               dict(category1="group2"), None,
                                               None, None, metadata.query)

        # test exception on new client with no default profile
        metadata.default = None
        new2 = self.get_nonexistent_client(metadata)
        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.get_initial_metadata,
                          new2)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.resolve_client")
    def test_validate_client_address(self, mock_resolve_client):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        # this is upper case to ensure that case is folded properly in
        # validate_client_address()
        mock_resolve_client.return_value = "CLIENT4"
        self.assertTrue(metadata.validate_client_address("client4",
                                                         ("1.2.3.7", None)))
        mock_resolve_client.assert_called_with(("1.2.3.7", None))

        mock_resolve_client.reset_mock()
        self.assertFalse(metadata.validate_client_address("client5",
                                                         ("1.2.3.5", None)))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.validate_client_address")
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.resolve_client")
    def test_AuthenticateConnection(self, mock_resolve_client,
                                    mock_validate_client_address):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        metadata.password = "password1"

        cert = dict(subject=[[("commonName", "client1")]])
        mock_validate_client_address.return_value = False
        self.assertFalse(metadata.AuthenticateConnection(cert, "root", None,
                                                         "1.2.3.1"))
        mock_validate_client_address.return_value = True
        self.assertTrue(metadata.AuthenticateConnection(cert, "root",
                                                        metadata.password,
                                                        "1.2.3.1"))

        cert = dict(subject=[[("commonName", "client8")]])

        mock_resolve_client.return_value = "client5"
        self.assertTrue(metadata.AuthenticateConnection(None, "root",
                                                        "password1", "1.2.3.8"))

        mock_resolve_client.side_effect = \
            Bcfg2.Server.Plugin.MetadataConsistencyError
        self.assertFalse(metadata.AuthenticateConnection(None, "root",
                                                         "password1",
                                                         "1.2.3.8"))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("socket.getnameinfo")
    def test_resolve_client(self, mock_getnameinfo):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        metadata.session_cache[('1.2.3.3', None)] = (time.time(), 'client3')
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None)), 'client3')

        metadata.session_cache[('1.2.3.3', None)] = (time.time() - 100,
                                                     'client3')
        mock_getnameinfo.return_value = ("client3", [], ['1.2.3.3'])
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None),
                                                 cleanup_cache=True), 'client3')
        self.assertEqual(metadata.session_cache, dict())

        mock_getnameinfo.return_value = ('client6', [], ['1.2.3.6'])
        self.assertEqual(metadata.resolve_client(('1.2.3.6', 6789), socket.NI_NAMEREQD), 'client6')
        mock_getnameinfo.assert_called_with(('1.2.3.6', 6789), socket.NI_NAMEREQD)

        mock_getnameinfo.reset_mock()
        mock_getnameinfo.return_value = None
        mock_getnameinfo.side_effect = socket.herror
        self.assertRaises(Bcfg2.Server.Plugin.MetadataConsistencyError,
                          metadata.resolve_client,
                          ('1.2.3.8', 6789), socket.NI_NAMEREQD)
        mock_getnameinfo.assert_called_with(('1.2.3.8', 6789), socket.NI_NAMEREQD)

    def test_handle_clients_xml_event(self):
        pass

    def test_end_statistics(self):
        # bootstrap mode, which is what is being tested here, doesn't
        # work without clients.xml
        pass

class TestMetadata_ClientsXML(TestMetadataBase):
    """ test Metadata with a clients.xml.  """
    __test__ = True

    def load_clients_data(self, metadata=None, xdata=None):
        if metadata is None:
            metadata = self.get_obj()
        fam = Bcfg2.Server.FileMonitor._FAM
        Bcfg2.Server.FileMonitor._FAM = MagicMock()
        @patchIf(not isinstance(lxml.etree.Element, Mock),
                 "lxml.etree.Element", Mock())
        def inner():
            metadata.clients_xml = metadata._handle_file("clients.xml")
        inner()
        metadata = TestMetadata.load_clients_data(self, metadata=metadata,
                                                  xdata=xdata)
        rv = TestMetadataBase.load_clients_data(self, metadata=metadata,
                                                xdata=xdata)
        Bcfg2.Server.FileMonitor._FAM = fam
        return rv
