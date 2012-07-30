import os
import sys
import unittest
import lxml.etree
from mock import Mock, patch
from django.core.management import setup_environ

os.environ['DJANGO_SETTINGS_MODULE'] = "Bcfg2.settings"

import Bcfg2.settings
Bcfg2.settings.DATABASE_NAME = \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.sqlite")
Bcfg2.settings.DATABASES['default']['NAME'] = Bcfg2.settings.DATABASE_NAME

import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.DBMetadata import *

from TestMetadata import datastore, groups_test_tree, clients_test_tree, \
    TestMetadata

def test_syncdb():
    # create the test database
    setup_environ(Bcfg2.settings)
    from django.core.management.commands import syncdb
    cmd = syncdb.Command()
    cmd.handle_noargs(interactive=False)
    assert os.path.exists(Bcfg2.settings.DATABASE_NAME)

    # ensure that we a) can connect to the database; b) start with a
    # clean database
    MetadataClientModel.objects.all().delete()
    assert list(MetadataClientModel.objects.all()) == []


class TestClientVersions(unittest.TestCase):
    test_clients = dict(client1="1.2.0",
                        client2="1.2.2",
                        client3="1.3.0pre1",
                        client4="1.1.0",
                        client5=None,
                        client6=None)

    def setUp(self):
        test_syncdb()
        for client, version in self.test_clients.items():
            MetadataClientModel(hostname=client, version=version).save()

    def test__contains(self):
        v = ClientVersions()
        self.assertIn("client1", v)
        self.assertIn("client5", v)
        self.assertNotIn("client__contains", v)

    def test_keys(self):
        v = ClientVersions()
        self.assertItemsEqual(self.test_clients.keys(), v.keys())

    def test__setitem(self):
        v = ClientVersions()

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
        v = ClientVersions()
        
        # test getting existing client
        self.assertEqual(v['client2'], "1.2.2")
        self.assertIsNone(v['client5'])

        # test exception on nonexistent client. can't use assertRaises
        # for this because assertRaises requires a callable
        try:
            v['clients__getitem']
            assert False
        except KeyError:
            assert True
        except:
            assert False


class TestDBMetadataBase(TestMetadata):
    __test__ = False

    def __init__(self, *args, **kwargs):
        TestMetadata.__init__(self, *args, **kwargs)
        test_syncdb()

    def load_clients_data(self, metadata=None, xdata=None):
        if metadata is None:
            metadata = get_metadata_object()
        for client in clients_test_tree.findall("Client"):
            metadata.add_client(client.get("name"))
        return metadata

    def get_metadata_object(self, core=None, watch_clients=False):
        if core is None:
            core = Mock()
        metadata = DBMetadata(core, datastore, watch_clients=watch_clients)
        return metadata

    def get_nonexistent_client(self, _, prefix="client"):
        clients = [o.hostname for o in MetadataClientModel.objects.all()]
        i = 0
        client_name = "%s%s" % (prefix, i)
        while client_name in clients:
            i += 1
            client_name = "%s%s" % (prefix, i)
        return client_name

    @patch('os.path.exists')
    def test__init(self, mock_exists):
        core = Mock()
        core.fam = Mock()
        mock_exists.return_value = False
        metadata = self.get_metadata_object(core=core, watch_clients=True)
        self.assertIsInstance(metadata, Bcfg2.Server.Plugin.DatabaseBacked)
        core.fam.AddMonitor.assert_called_once_with(os.path.join(metadata.data,
                                                                 "groups.xml"),
                                                    metadata)
        
        mock_exists.return_value = True
        core.fam.reset_mock()
        metadata = self.get_metadata_object(core=core, watch_clients=True)
        core.fam.AddMonitor.assert_any_call(os.path.join(metadata.data,
                                                         "groups.xml"),
                                            metadata)
        core.fam.AddMonitor.assert_any_call(os.path.join(metadata.data,
                                                         "clients.xml"),
                                            metadata)
    
    def test_add_group(self):
        pass

    def test_add_bundle(self):
        pass

    def test_add_client(self):
        metadata = self.get_metadata_object()
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
        metadata = self.get_metadata_object()
        self.assertItemsEqual(metadata.list_clients(),
                              [c.hostname
                               for c in MetadataClientModel.objects.all()])

    def test_remove_group(self):
        pass

    def test_remove_bundle(self):
        pass

    def test_remove_client(self):
        metadata = self.get_metadata_object()
        client_name = self.get_nonexistent_client(metadata)

        self.assertRaises(MetadataConsistencyError,
                          metadata.remove_client,
                          client_name)

        metadata.add_client(client_name)
        metadata.remove_client(client_name)
        self.assertNotIn(client_name, metadata.clients)
        self.assertNotIn(client_name, metadata.list_clients())
        self.assertItemsEqual(metadata.clients,
                              [c.hostname
                               for c in MetadataClientModel.objects.all()])

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("Bcfg2.Server.Plugins.DBMetadata.DBMetadata._set_profile")
    def test_set_profile(self, mock_set_profile):
        TestMetadata.test_set_profile(self,
                                      inherited_set_profile=mock_set_profile)

    def test__set_profile(self):
        metadata = self.get_metadata_object()
        profile = "group1"
        client_name = self.get_nonexistent_client(metadata)
        metadata._set_profile(client_name, profile, None)
        self.assertIn(client_name, metadata.list_clients())
        self.assertIn(client_name, metadata.clientgroups)
        self.assertItemsEqual(metadata.clientgroups[client_name], [profile])

        self.assertRaises(Bcfg2.Server.Plugin.PluginExecutionError,
                          metadata._set_profile,
                          client_name, profile, None)

    def test_process_statistics(self):
        pass


class TestDBMetadata_NoClientsXML(TestDBMetadataBase):
    """ test DBMetadata without a clients.xml. we have to disable or
    override tests that rely on client options """
    __test__ = True

    def __init__(self, *args, **kwargs):
        TestMetadata.__init__(self, *args, **kwargs)

        for client in self.clients_test_tree.findall("Client"):
            newclient = lxml.etree.SubElement(self.groups_test_tree.getroot(),
                                              "Client", name=client.get("name"))
            lxml.etree.SubElement(newclient, "Group",
                                  name=client.get("profile"))

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

        # test basic client metadata
        metadata.get_initial_metadata("client1")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client1", "group1", set(["group1"]), set(), set(),
                          set(), dict(category1='group1'), None, None))

        # test bundles, category suppression
        metadata.get_initial_metadata("client2")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client2", "group2", set(["group2"]),
                          set(["bundle1", "bundle2"]), set(), set(),
                          dict(category1="group2"), None, None))

        # test new client creation
        new1 = self.get_nonexistent_client(metadata)
        imd = metadata.get_initial_metadata(new1)
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         (new1, "group1", set(["group1"]), set(), set(), set(),
                          dict(category1="group1"), None, None))

        # test nested groups, per-client groups
        imd = metadata.get_initial_metadata("client8")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client8", "group1",
                          set(["group1", "group8", "group9", "group10"]), set(),
                          set(), set(), dict(category1="group1"), None, None))

        # test per-client groups, group negation, nested groups
        imd = metadata.get_initial_metadata("client9")
        self.assertEqual(mock_clientmetadata.call_args[0][:9],
                         ("client9", "group2",
                          set(["group2", "group8", "group11"]),
                          set(["bundle1", "bundle2"]), set(), set(),
                          dict(category1="group2"), None, None))

        # test exception on new client with no default profile
        metadata.default = None
        new2 = self.get_nonexistent_client(metadata)
        self.assertRaises(MetadataConsistencyError,
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

        mock_resolve_client.side_effect = MetadataConsistencyError
        self.assertFalse(metadata.AuthenticateConnection(None, "root",
                                                         "password1",
                                                         "1.2.3.8"))

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml", Mock())
    @patch("socket.gethostbyaddr")
    def test_resolve_client(self, mock_gethostbyaddr):
        metadata = self.load_clients_data(metadata=self.load_groups_data())
        metadata.session_cache[('1.2.3.3', None)] = (time.time(), 'client3')
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None)), 'client3')

        metadata.session_cache[('1.2.3.3', None)] = (time.time() - 100,
                                                     'client3')
        mock_gethostbyaddr.return_value = ("client3", [], ['1.2.3.3'])
        self.assertEqual(metadata.resolve_client(('1.2.3.3', None),
                                                 cleanup_cache=True), 'client3')
        self.assertEqual(metadata.session_cache, dict())

        mock_gethostbyaddr.return_value = ('client6', [], ['1.2.3.6'])
        self.assertEqual(metadata.resolve_client(('1.2.3.6', None)), 'client6')
        mock_gethostbyaddr.assert_called_with('1.2.3.6')

        mock_gethostbyaddr.reset_mock()
        mock_gethostbyaddr.return_value = None
        mock_gethostbyaddr.side_effect = socket.herror
        self.assertRaises(MetadataConsistencyError,
                          metadata.resolve_client,
                          ('1.2.3.8', None))
        mock_gethostbyaddr.assert_called_with('1.2.3.8')

    def test_clients_xml_event(self):
        pass


class TestDBMetadata_ClientsXML(TestDBMetadataBase):
    """ test DBMetadata with a clients.xml.  """
    __test__ = True
    
    def load_clients_data(self, metadata=None, xdata=None):
        if metadata is None:
            metadata = self.get_metadata_object()
        metadata.core.fam = Mock()
        metadata._handle_file("clients.xml")
        metadata = TestMetadata.load_clients_data(self, metadata=metadata,
                                                  xdata=xdata)
        return TestDBMetadataBase.load_clients_data(self, metadata=metadata,
                                                    xdata=xdata)

    @patch("Bcfg2.Server.Plugins.Metadata.XMLMetadataConfig.load_xml")
    @patch("Bcfg2.Server.Plugins.Metadata.Metadata._handle_clients_xml_event")
    @patch("Bcfg2.Server.Plugins.DBMetadata.DBMetadata.list_clients")
    def test_clients_xml_event(self, mock_list_clients, mock_handle_event,
                               mock_load_xml):
        metadata = self.get_metadata_object()
        metadata.profiles = ["group1", "group2"]
        evt = Mock()
        evt.filename = os.path.join(datastore, "DBMetadata", "clients.xml")
        evt.code2str = Mock(return_value="changed")
        metadata.HandleEvent(evt)
        self.assertFalse(mock_handle_event.called)
        self.assertFalse(mock_load_xml.called)

        mock_load_xml.reset_mock()
        mock_handle_event.reset_mock()
        mock_list_clients.reset_mock()
        metadata._handle_file("clients.xml")
        metadata.HandleEvent(evt)
        mock_handle_event.assert_called_with(metadata, evt)
        mock_list_clients.assert_any_call()
        mock_load_xml.assert_any_call()
