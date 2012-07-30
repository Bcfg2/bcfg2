import os
import copy
import time
import socket
import unittest
import lxml.etree
from mock import Mock, patch
import Bcfg2.Server
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Metadata import *

XI_NAMESPACE = "http://www.w3.org/2001/XInclude"
XI = "{%s}" % XI_NAMESPACE

clients_test_tree = lxml.etree.XML('''
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

groups_test_tree = lxml.etree.XML('''
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
</Groups>''').getroottree()

datastore = "/"

def get_metadata_object(core=None, watch_clients=False):
    if core is None:
        core = Mock()
    metadata = Metadata(core, datastore, watch_clients=watch_clients)
    return metadata


class TestXMLMetadataConfig(unittest.TestCase):
    groups_test_tree = groups_test_tree
    clients_test_tree = clients_test_tree

    def get_config_object(self, basefile="clients.xml", core=None,
                          watch_clients=False):
        self.metadata = get_metadata_object(core=core,
                                            watch_clients=watch_clients)
        return XMLMetadataConfig(self.metadata, watch_clients, basefile)

    def test_xdata(self):
        config = self.get_config_object()
        # we can't use assertRaises here because xdata is a property
        try:
            config.xdata
            assert False
        except MetadataRuntimeError:
            assert True
        except:
            assert False
        config.data = "<test/>"
        self.assertEqual(config.xdata, "<test/>")

    def test_base_xdata(self):
        config = self.get_config_object()
        # we can't use assertRaises here because base_xdata is a property
        try:
            config.base_xdata
            assert False
        except MetadataRuntimeError:
            assert True
        except:
            assert False
        config.basedata = "<test/>"
        self.assertEqual(config.base_xdata, "<test/>")

    def test_add_monitor(self):
        core = Mock()
        config = self.get_config_object(core=core)

        fname = "test.xml"
        fpath = os.path.join(self.metadata.data, fname)

        config.extras = []
        config.add_monitor(fpath, fname)
        self.assertFalse(core.fam.AddMonitor.called)
        self.assertEqual(config.extras, [fname])

        config = self.get_config_object(core=core, watch_clients=True)
        config.add_monitor(fpath, fname)
        core.fam.AddMonitor.assert_called_with(fpath, config.metadata)
        self.assertItemsEqual(config.extras, [fname])

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.add_monitor")
    @patch("lxml.etree.parse")
    def test_load_xml(self, mock_parse, mock_add_monitor):
        config = self.get_config_object("clients.xml")
        mock_parse.side_effect = lxml.etree.XMLSyntaxError(None, None, None,
                                                           None)
        config.load_xml()
        self.assertIsNone(config.data)
        self.assertIsNone(config.basedata)

        config.data = None
        config.basedata = None
        mock_parse.side_effect = None
        mock_parse.return_value.findall = Mock(return_value=[])
        config.load_xml()
        self.assertIsNotNone(config.data)
        self.assertIsNotNone(config.basedata)

        config.data = None
        config.basedata = None

        def side_effect(*args):
            def second_call(*args):
                return []
            mock_parse.return_value.findall.side_effect = second_call
            return [lxml.etree.Element(XI + "include", href="more.xml"),
                    lxml.etree.Element(XI + "include", href="evenmore.xml")]

        mock_parse.return_value.findall = Mock(side_effect=side_effect)
        config.load_xml()
        mock_add_monitor.assert_any_call("more.xml")
        mock_add_monitor.assert_any_call("evenmore.xml")

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.write_xml")
    def test_write(self, mock_write_xml):
        config = self.get_config_object("clients.xml")
        config.basedata = "<test/>"
        config.write()
        mock_write_xml.assert_called_with(os.path.join(self.metadata.data,
                                                       "clients.xml"),
                                          "<test/>")

    @patch('Bcfg2.Server.Plugins.Metadata.locked', Mock(return_value=False))
    @patch('fcntl.lockf', Mock())
    @patch('__builtin__.open')
    @patch('os.unlink')
    @patch('os.rename')
    @patch('os.path.islink')
    @patch('os.readlink')
    def test_write_xml(self, mock_readlink, mock_islink, mock_rename,
                       mock_unlink, mock_open):
        fname = "clients.xml"
        config = self.get_config_object(fname)
        fpath = os.path.join(self.metadata.data, fname)
        tmpfile = "%s.new" % fpath
        linkdest = os.path.join(self.metadata.data, "client-link.xml")

        mock_islink.return_value = False

        config.write_xml(fpath, self.clients_test_tree)
        mock_open.assert_called_with(tmpfile, "w")
        self.assertTrue(mock_open.return_value.write.called)
        mock_islink.assert_called_with(fpath)
        mock_rename.assert_called_with(tmpfile, fpath)

        mock_islink.return_value = True
        mock_readlink.return_value = linkdest
        config.write_xml(fpath, self.clients_test_tree)
        mock_rename.assert_called_with(tmpfile, linkdest)

        mock_rename.side_effect = OSError
        self.assertRaises(MetadataRuntimeError,
                          config.write_xml, fpath, self.clients_test_tree)

        mock_open.return_value.write.side_effect = IOError
        self.assertRaises(MetadataRuntimeError,
                          config.write_xml, fpath, self.clients_test_tree)
        mock_unlink.assert_called_with(tmpfile)

        mock_open.side_effect = IOError
        self.assertRaises(MetadataRuntimeError,
                          config.write_xml, fpath, self.clients_test_tree)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch('lxml.etree.parse')
    def test_find_xml_for_xpath(self, mock_parse):
        config = self.get_config_object("groups.xml")
        config.basedata = self.groups_test_tree
        xpath = "//Group[@name='group1']"
        self.assertItemsEqual(config.find_xml_for_xpath(xpath),
                              dict(filename=os.path.join(self.metadata.data,
                                                         "groups.xml"),
                                   xmltree=self.groups_test_tree,
                                   xquery=self.groups_test_tree.xpath(xpath)))

        self.assertEqual(config.find_xml_for_xpath("//boguselement"), dict())

        config.extras = ["foo.xml", "bar.xml", "clients.xml"]

        def parse_side_effect(fname, parser=Bcfg2.Server.XMLParser):
            if fname == os.path.join(self.metadata.data, "clients.xml"):
                return self.clients_test_tree
            else:
                return lxml.etree.XML("<null/>").getroottree()

        mock_parse.side_effect = parse_side_effect
        xpath = "//Client[@secure='true']"
        self.assertItemsEqual(config.find_xml_for_xpath(xpath),
                              dict(filename=os.path.join(self.metadata.data,
                                                         "clients.xml"),
                                   xmltree=self.clients_test_tree,
                                   xquery=self.clients_test_tree.xpath(xpath)))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml")
    def test_HandleEvent(self, mock_load_xml):
        config = self.get_config_object("groups.xml")
        evt = Mock()
        evt.filename = os.path.join(self.metadata.data, "groups.xml")
        evt.code2str = Mock(return_value="changed")
        self.assertTrue(config.HandleEvent(evt))
        mock_load_xml.assert_called_with()


class TestClientMetadata(unittest.TestCase):
    def test_inGroup(self):
        cm = ClientMetadata("client1", "group1", ["group1", "group2"],
                            ["bundle1"], [], [], [], None, None, None, None)
        self.assertTrue(cm.inGroup("group1"))
        self.assertFalse(cm.inGroup("group3"))


class TestMetadata(unittest.TestCase):
    groups_test_tree = groups_test_tree
    clients_test_tree = clients_test_tree

    def get_metadata_object(self, core=None, watch_clients=False):
        return get_metadata_object(core=core, watch_clients=watch_clients)

    def get_nonexistent_client(self, metadata, prefix="client"):
        if metadata is None:
            metadata = self.load_clients_data()
        i = 0
        client_name = "%s%s" % (prefix, i)
        while client_name in metadata.clients:
            i += 1
            client_name = "%s%s" % (prefix, i)
        return client_name

    def test__init(self):
        # test with watch_clients=False
        core = Mock()
        metadata = self.get_metadata_object(core=core)
        self.assertIsInstance(metadata, Bcfg2.Server.Plugin.Plugin)
        self.assertIsInstance(metadata, Bcfg2.Server.Plugin.Metadata)
        self.assertIsInstance(metadata, Bcfg2.Server.Plugin.Statistics)
        self.assertIsInstance(metadata.clients_xml, XMLMetadataConfig)
        self.assertIsInstance(metadata.groups_xml, XMLMetadataConfig)
        self.assertIsInstance(metadata.query, MetadataQuery)
        self.assertEqual(metadata.states, dict())

        # test with watch_clients=True
        core.fam = Mock()
        metadata = self.get_metadata_object(core=core, watch_clients=True)
        self.assertEqual(len(metadata.states), 2)
        core.fam.AddMonitor.assert_any_call(os.path.join(metadata.data,
                                                         "groups.xml"),
                                            metadata)
        core.fam.AddMonitor.assert_any_call(os.path.join(metadata.data,
                                                         "clients.xml"),
                                            metadata)

        core.fam.reset_mock()
        core.fam.AddMonitor = Mock(side_effect=IOError)
        self.assertRaises(Bcfg2.Server.Plugin.PluginInitError,
                          self.get_metadata_object,
                          core=core, watch_clients=True)

    @patch('os.makedirs', Mock())
    @patch('__builtin__.open')
    def test_init_repo(self, mock_open):
        Metadata.init_repo(datastore,
                           groups_xml="groups", clients_xml="clients")
        mock_open.assert_any_call(os.path.join(datastore, "Metadata",
                                               "groups.xml"), "w")
        mock_open.assert_any_call(os.path.join(datastore, "Metadata",
                                               "clients.xml"), "w")

    def test_search_xdata(self):
        # test finding a node with the proper name
        metadata = self.get_metadata_object()
        tree = self.groups_test_tree
        res = metadata._search_xdata("Group", "group1", tree)
        self.assertIsInstance(res, lxml.etree._Element)
        self.assertEqual(res.get("name"), "group1")

        # test finding a node with the wrong name but correct alias
        metadata = self.get_metadata_object()
        tree = self.clients_test_tree
        res = metadata._search_xdata("Client", "alias3", tree, alias=True)
        self.assertIsInstance(res, lxml.etree._Element)
        self.assertNotEqual(res.get("name"), "alias3")

        # test failure finding a node
        metadata = self.get_metadata_object()
        tree = self.clients_test_tree
        res = metadata._search_xdata("Client",
                                     self.get_nonexistent_client(metadata),
                                     tree, alias=True)
        self.assertIsNone(res)

    def search_xdata(self, tag, name, tree, alias=False):
        metadata = self.get_metadata_object()
        res = metadata._search_xdata(tag, name, tree, alias=alias)
        self.assertIsInstance(res, lxml.etree._Element)
        if not alias:
            self.assertEqual(res.get("name"), name)

    def test_search_group(self):
        # test finding a group with the proper name
        tree = self.groups_test_tree
        self.search_xdata("Group", "group1", tree)

    def test_search_bundle(self):
        # test finding a bundle with the proper name
        tree = self.groups_test_tree
        self.search_xdata("Bundle", "bundle1", tree)

    def test_search_client(self):
        # test finding a client with the proper name
        tree = self.clients_test_tree
        self.search_xdata("Client", "client1", tree, alias=True)
        self.search_xdata("Client", "alias1", tree, alias=True)

    def test_add_group(self):
        metadata = self.get_metadata_object()
        metadata.groups_xml.write = Mock()
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
        self.assertRaises(MetadataConsistencyError,
                          metadata.add_group,
                          "test1", dict())
        self.assertFalse(metadata.groups_xml.write.called)

    def test_update_group(self):
        metadata = self.get_metadata_object()
        metadata.groups_xml.write_xml = Mock()
        metadata.groups_xml.data = copy.deepcopy(self.groups_test_tree)
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.update_group("group1", dict(foo="bar"))
        grp = metadata.search_group("group1", metadata.groups_xml.base_xdata)
        self.assertIsNotNone(grp)
        self.assertIn("foo", grp.attrib)
        self.assertEqual(grp.get("foo"), "bar")
        self.assertTrue(metadata.groups_xml.write_xml.called)

        self.assertRaises(MetadataConsistencyError,
                          metadata.update_group,
                          "bogus_group", dict())

    def test_remove_group(self):
        metadata = self.get_metadata_object()
        metadata.groups_xml.write_xml = Mock()
        metadata.groups_xml.data = copy.deepcopy(self.groups_test_tree)
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.remove_group("group5")
        grp = metadata.search_group("group5", metadata.groups_xml.base_xdata)
        self.assertIsNone(grp)
        self.assertTrue(metadata.groups_xml.write_xml.called)

        self.assertRaises(MetadataConsistencyError,
                          metadata.remove_group,
                          "bogus_group")

    def test_add_bundle(self):
        metadata = self.get_metadata_object()
        metadata.groups_xml.write = Mock()
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
        self.assertRaises(MetadataConsistencyError,
                          metadata.add_bundle,
                          "bundle1")
        self.assertFalse(metadata.groups_xml.write.called)

    def test_remove_bundle(self):
        metadata = self.get_metadata_object()
        metadata.groups_xml.write_xml = Mock()
        metadata.groups_xml.data = copy.deepcopy(self.groups_test_tree)
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)

        metadata.remove_bundle("bundle1")
        grp = metadata.search_bundle("bundle1", metadata.groups_xml.base_xdata)
        self.assertIsNone(grp)
        self.assertTrue(metadata.groups_xml.write_xml.called)

        self.assertRaises(MetadataConsistencyError,
                          metadata.remove_bundle,
                          "bogus_bundle")

    def test_add_client(self):
        metadata = self.get_metadata_object()
        metadata.clients_xml.write = Mock()
        metadata.clients_xml.data = lxml.etree.XML('<Clients/>').getroottree()
        metadata.clients_xml.basedata = copy.copy(metadata.clients_xml.data)

        new1 = self.get_nonexistent_client(metadata)
        metadata.add_client(new1, dict())
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
        self.assertRaises(MetadataConsistencyError,
                          metadata.add_client,
                          new1, dict())
        self.assertFalse(metadata.clients_xml.write.called)

    def test_update_client(self):
        metadata = self.get_metadata_object()
        metadata.clients_xml.write_xml = Mock()
        metadata.clients_xml.data = copy.deepcopy(self.clients_test_tree)
        metadata.clients_xml.basedata = copy.copy(metadata.clients_xml.data)

        metadata.update_client("client1", dict(foo="bar"))
        grp = metadata.search_client("client1", metadata.clients_xml.base_xdata)
        self.assertIsNotNone(grp)
        self.assertIn("foo", grp.attrib)
        self.assertEqual(grp.get("foo"), "bar")
        self.assertTrue(metadata.clients_xml.write_xml.called)

        new = self.get_nonexistent_client(metadata)
        self.assertRaises(MetadataConsistencyError,
                          metadata.update_client,
                          new, dict())

    def load_clients_data(self, metadata=None, xdata=None):
        if metadata is None:
            metadata = self.get_metadata_object()
        metadata.clients_xml.data = xdata or copy.deepcopy(self.clients_test_tree)
        metadata.clients_xml.basedata = copy.copy(metadata.clients_xml.data)
        evt = Mock()
        evt.filename = os.path.join(datastore, "Metadata", "clients.xml")
        evt.code2str = Mock(return_value="changed")
        metadata.HandleEvent(evt)
        return metadata

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml")
    def test_clients_xml_event(self, mock_load_xml):
        metadata = self.get_metadata_object()
        metadata.profiles = ["group1", "group2"]
        self.load_clients_data(metadata=metadata)
        mock_load_xml.assert_any_call()
        self.assertItemsEqual(metadata.clients,
                              dict([(c.get("name"), c.get("profile"))
                                    for c in self.clients_test_tree.findall("//Client")]))
        aliases = dict([(a.get("name"), a.getparent().get("name"))
                        for a in self.clients_test_tree.findall("//Alias")])
        self.assertItemsEqual(metadata.aliases, aliases)

        raliases = dict([(c.get("name"), set())
                         for c in self.clients_test_tree.findall("//Client")])
        for alias in self.clients_test_tree.findall("//Alias"):
            raliases[alias.getparent().get("name")].add(alias.get("name"))
        self.assertItemsEqual(metadata.raliases, raliases)

        self.assertEqual(metadata.secure,
                         [c.get("name")
                          for c in self.clients_test_tree.findall("//Client[@secure='true']")])
        self.assertEqual(metadata.floating, ["client1", "client10"])

        addresses = dict([(c.get("address"), [])
                           for c in self.clients_test_tree.findall("//*[@address]")])
        raddresses = dict()
        for client in self.clients_test_tree.findall("//Client[@address]"):
            addresses[client.get("address")].append(client.get("name"))
            try:
                raddresses[client.get("name")].append(client.get("address"))
            except KeyError:
                raddresses[client.get("name")] = [client.get("address")]
        for alias in self.clients_test_tree.findall("//Alias[@address]"):
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
            metadata = self.get_metadata_object()
        metadata.groups_xml.data = xdata or copy.deepcopy(self.groups_test_tree)
        metadata.groups_xml.basedata = copy.copy(metadata.groups_xml.data)
        evt = Mock()
        evt.filename = os.path.join(datastore, "Metadata", "groups.xml")
        evt.code2str = Mock(return_value="changed")
        metadata.HandleEvent(evt)
        return metadata

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml")
    def test_groups_xml_event(self, mock_load_xml):
        dup_data = copy.deepcopy(self.groups_test_tree)
        lxml.etree.SubElement(dup_data.getroot(),
                              "Group", name="group1")
        metadata = self.load_groups_data(xdata=dup_data)
        mock_load_xml.assert_any_call()
        self.assertTrue(metadata.states['groups.xml'])
        self.assertTrue(metadata.groups['group1'].is_public)
        self.assertTrue(metadata.groups['group2'].is_public)
        self.assertFalse(metadata.groups['group3'].is_public)
        self.assertFalse(metadata.groups['group1'].is_private)
        self.assertFalse(metadata.groups['group2'].is_private)
        self.assertTrue(metadata.groups['group3'].is_private)
        self.assertTrue(metadata.groups['group1'].is_profile)
        self.assertTrue(metadata.groups['group2'].is_profile)
        self.assertFalse(metadata.groups['group3'].is_profile)
        self.assertItemsEqual(metadata.groups.keys(),
                              set(g.get("name")
                                  for g in self.groups_test_tree.findall("//Group")))
        self.assertEqual(metadata.groups['group1'].category, 'category1')
        self.assertEqual(metadata.groups['group2'].category, 'category1')
        self.assertEqual(metadata.groups['group3'].category, 'category2')
        self.assertEqual(metadata.groups['group4'].category, 'category1')
        self.assertEqual(metadata.default, "group1")

        all_groups = []
        negated_groups = []
        for group in dup_data.xpath("//Groups/Client//*") + \
                dup_data.xpath("//Groups/Group//*"):
            if group.tag == 'Group' and not group.getchildren():
                if group.get("negate", "false").lower() == 'true':
                    negated_groups.append(group.get("name"))
                else:
                    all_groups.append(group.get("name"))
        self.assertItemsEqual([g.name
                               for g in metadata.group_membership.values()],
                              all_groups)
        self.assertItemsEqual([g.name
                               for g in metadata.negated_groups.values()],
                              negated_groups)
        
    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata._set_profile")
    def test_set_profile(self, mock_set_profile, inherited_set_profile=None):
        if inherited_set_profile:
            # allow a subclass of TestMetadata to patch a different
            # _set_profile object and pass it in.  this probably isn't
            # the best way to accomplish that, but it seems to work.
            mock_set_profile = inherited_set_profile
        metadata = self.get_metadata_object()
        if 'clients.xml' in metadata.states:
            metadata.states['clients.xml'] = False
            self.assertRaises(MetadataRuntimeError,
                              metadata.set_profile,
                              None, None, None)

        self.load_groups_data(metadata=metadata)
        self.load_clients_data(metadata=metadata)

        self.assertRaises(MetadataConsistencyError,
                          metadata.set_profile,
                          "client1", "group5", None)

        self.assertRaises(MetadataConsistencyError,
                          metadata.set_profile,
                          "client1", "group3", None)

        metadata.set_profile("client1", "group5", None, force=True)
        mock_set_profile.assert_called_with("client1", "group5", None)

        metadata.set_profile("client1", "group3", None, force=True)
        mock_set_profile.assert_called_with("client1", "group3", None)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.add_client")
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata.update_client")
    def test__set_profile(self, mock_update_client, mock_add_client):
        metadata = self.get_metadata_object()
        self.load_groups_data(metadata=metadata)
        self.load_clients_data(metadata=metadata)

        metadata.clients_xml.write = Mock()
        metadata._set_profile("client1", "group2", None)
        mock_update_client.assert_called_with("client1", dict(profile="group2"))
        metadata.clients_xml.write.assert_any_call()
        self.assertEqual(metadata.clientgroups["client1"], ["group2"])

        metadata.clients_xml.write.reset_mock()
        new1 = self.get_nonexistent_client(metadata)
        metadata._set_profile(new1, "group1", None)
        mock_add_client.assert_called_with(new1, dict(profile="group1"))
        metadata.clients_xml.write.assert_any_call()
        self.assertEqual(metadata.clientgroups[new1], ["group1"])

        metadata.clients_xml.write.reset_mock()
        new2 = self.get_nonexistent_client(metadata)
        metadata.session_cache[('1.2.3.6', None)] = (None, new2)
        metadata._set_profile("uuid_new", "group1", ('1.2.3.6', None))
        mock_add_client.assert_called_with(new2,
                                           dict(uuid='uuid_new',
                                                profile="group1",
                                                address='1.2.3.6'))
        metadata.clients_xml.write.assert_any_call()
        self.assertEqual(metadata.clientgroups["uuid_new"], ["group1"])

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("socket.gethostbyaddr")
    def test_resolve_client(self, mock_gethostbyaddr):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        metadata.session_cache[('1.2.3.3', None)] = (time.time(), 'client3')
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None)), 'client3')

        self.assertRaises(MetadataConsistencyError,
                          metadata.resolve_client,
                          ('1.2.3.2', None))
        self.assertEqual(metadata.resolve_client(('1.2.3.1', None)), 'client1')

        metadata.session_cache[('1.2.3.3', None)] = (time.time() - 100,
                                                     'client3')
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None)), 'client3')
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None),
                                                 cleanup_cache=True), 'client3')
        self.assertEqual(metadata.session_cache, dict())

        mock_gethostbyaddr.return_value = ('client6', [], ['1.2.3.6'])
        self.assertEqual(metadata.resolve_client(('1.2.3.6', None)), 'client6')
        mock_gethostbyaddr.assert_called_with('1.2.3.6')

        mock_gethostbyaddr.reset_mock()
        mock_gethostbyaddr.return_value = ('alias3', [], ['1.2.3.7'])
        self.assertEqual(metadata.resolve_client(('1.2.3.7', None)), 'client4')
        mock_gethostbyaddr.assert_called_with('1.2.3.7')

        mock_gethostbyaddr.reset_mock()
        mock_gethostbyaddr.return_value = None
        mock_gethostbyaddr.side_effect = socket.herror
        self.assertRaises(MetadataConsistencyError,
                          metadata.resolve_client,
                          ('1.2.3.8', None))
        mock_gethostbyaddr.assert_called_with('1.2.3.8')

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.write_xml", Mock())
    @patch("Bcfg2.Server.Plugins.Metadata.ClientMetadata")
    def test_get_initial_metadata(self, mock_clientmetadata):
        metadata = self.get_metadata_object()
        if 'clients.xml' in metadata.states:
            metadata.states['clients.xml'] = False
            self.assertRaises(MetadataRuntimeError,
                              metadata.get_initial_metadata, None)

        self.load_groups_data(metadata=metadata)
        self.load_clients_data(metadata=metadata)

        # test address, password
        metadata.get_initial_metadata("client1")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client1", "group1", set(["group1"]), set(), set(),
                          set(["1.2.3.1"]), dict(category1='group1'), None,
                          'password2'))

        # test address, bundles, category suppression
        metadata.get_initial_metadata("client2")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client2", "group2", set(["group2"]),
                          set(["bundle1", "bundle2"]), set(),
                          set(["1.2.3.2"]), dict(category1="group2"),
                          None, None))

        # test aliases, address, uuid, password
        imd = metadata.get_initial_metadata("alias1")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client3", "group1", set(["group1"]), set(),
                          set(['alias1']), set(["1.2.3.3"]),
                          dict(category1="group1"), 'uuid1', 'password2'))

        # test new client creation
        new1 = self.get_nonexistent_client(metadata)
        imd = metadata.get_initial_metadata(new1)
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         (new1, "group1", set(["group1"]), set(),
                          set(), set(), dict(category1="group1"), None, None))

        # test nested groups, address, per-client groups
        imd = metadata.get_initial_metadata("client8")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client8", "group1",
                          set(["group1", "group8", "group9", "group10"]), set(),
                          set(), set(["1.2.3.5"]), dict(category1="group1"),
                          None, None))

        # test setting per-client groups, group negation, nested groups
        imd = metadata.get_initial_metadata("client9")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client9", "group2",
                          set(["group2", "group8", "group11"]),
                          set(["bundle1", "bundle2"]), set(), set(),
                          dict(category1="group2"), None, "password3"))

        # test new client with no default profile
        metadata.default = None
        new2 = self.get_nonexistent_client(metadata)
        self.assertRaises(MetadataConsistencyError,
                          metadata.get_initial_metadata, new2)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_merge_groups(self):
        metadata = self.get_metadata_object()        
        self.load_groups_data(metadata=metadata)
        self.load_clients_data(metadata=metadata)

        imd = metadata.get_initial_metadata("client1")
        self.assertEqual(metadata._merge_groups(imd, imd.groups,
                                                categories=imd.categories),
                         (imd.groups, imd.categories))

        imd = metadata.get_initial_metadata("client8")
        self.assertEqual(metadata._merge_groups(imd, imd.groups,
                                                categories=imd.categories),
                         (imd.groups.union(['group10']), imd.categories))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_get_all_group_names(self):
        metadata = self.load_groups_data()
        self.assertItemsEqual(metadata.get_all_group_names(),
                              set([g.get("name")
                                   for g in self.groups_test_tree.findall("//Group")]))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_get_all_groups_in_category(self):
        metadata = self.load_groups_data()
        self.assertItemsEqual(metadata.get_all_groups_in_category("category1"),
                              set([g.get("name")
                                   for g in self.groups_test_tree.findall("//Group[@category='category1']")]))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    def test_get_client_names_by_profiles(self):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        self.assertItemsEqual(metadata.get_client_names_by_profiles(["group2"]),
                              [c.get("name")
                               for c in self.clients_test_tree.findall("//Client[@profile='group2']")])

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
                               for c in self.clients_test_tree.findall("//Client[@profile='group2']")])

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

        # test adding multiple groups
        imd = metadata.get_initial_metadata("client2")
        oldgroups = imd.groups
        metadata.merge_additional_groups(imd, ["group6", "group8"])
        self.assertItemsEqual(imd.groups,
                              oldgroups.union(["group6", "group8", "group9"]))

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

        mock_resolve_client.side_effect = MetadataConsistencyError
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
    def test_process_statistics(self, mock_update_client):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        md = Mock()
        md.hostname = "client6"
        metadata.process_statistics(md, None)
        mock_update_client.assert_called_with(md.hostname,
                                              dict(auth='cert'))

        mock_update_client.reset_mock()
        md.hostname = "client5"
        metadata.process_statistics(md, None)
        self.assertFalse(mock_update_client.called)

    def test_viz(self):
        pass
