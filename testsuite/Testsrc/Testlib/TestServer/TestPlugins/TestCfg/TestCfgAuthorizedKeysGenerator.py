import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg.CfgAuthorizedKeysGenerator import *
import Bcfg2.Server.Plugins.Cfg.CfgAuthorizedKeysGenerator

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
from TestServer.TestPlugins.TestCfg.Test_init import TestCfgGenerator
from TestServer.TestPlugin.Testhelpers import TestStructFile


class TestCfgAuthorizedKeysGenerator(TestCfgGenerator, TestStructFile):
    test_obj = CfgAuthorizedKeysGenerator
    should_monitor = False

    def setUp(self):
        TestCfgGenerator.setUp(self)
        TestStructFile.setUp(self)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgAuthorizedKeysGenerator.get_cfg")
    def get_obj(self, mock_get_cfg, name=None, core=None, fam=None):
        if name is None:
            name = self.path
        if core is not None:
            mock_get_cfg.return_value.core = core
        return self.test_obj(name)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgGenerator.handle_event")
    @patch("Bcfg2.Server.Plugin.helpers.StructFile.HandleEvent")
    def test_handle_event(self, mock_HandleEvent, mock_handle_event):
        akg = self.get_obj()
        evt = Mock()
        akg.handle_event(evt)
        mock_HandleEvent.assert_called_with(akg, evt)
        mock_handle_event.assert_called_with(akg, evt)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgAuthorizedKeysGenerator.ClientMetadata")
    def test_get_data(self, mock_ClientMetadata):
        Bcfg2.Options.setup.sshkeys_category = "category"
        akg = self.get_obj()
        akg.XMLMatch = Mock()

        def ClientMetadata(host, profile, groups, *args):
            rv = Mock()
            rv.hostname = host
            rv.profile = profile
            rv.groups = groups
            return rv

        mock_ClientMetadata.side_effect = ClientMetadata

        def build_metadata(host):
            rv = Mock()
            rv.hostname = host
            rv.profile = host
            return rv

        akg.core.build_metadata = Mock()
        akg.core.build_metadata.side_effect = build_metadata

        def Bind(ent, md):
            ent.text = "%s %s" % (md.profile, ent.get("name"))
            return ent

        akg.core.Bind = Mock()
        akg.core.Bind.side_effect = Bind
        metadata = Mock()
        metadata.profile = "profile"
        metadata.group_in_category.return_value = "profile"
        entry = lxml.etree.Element("Path", name="/root/.ssh/authorized_keys")

        def reset():
            mock_ClientMetadata.reset_mock()
            akg.XMLMatch.reset_mock()
            akg.core.build_metadata.reset_mock()
            akg.core.Bind.reset_mock()
            metadata.reset_mock()

        pubkey = "/home/foo/.ssh/id_rsa.pub"
        spec = lxml.etree.Element("AuthorizedKeys")
        lxml.etree.SubElement(spec, "Allow", attrib={"from": pubkey})
        akg.XMLMatch.return_value = spec
        self.assertEqual(akg.get_data(entry, metadata), "profile %s" % pubkey)
        akg.XMLMatch.assert_called_with(metadata)
        self.assertEqual(akg.core.Bind.call_args[0][0].get("name"), pubkey)
        self.assertEqual(akg.core.Bind.call_args[0][1], metadata)

        reset()
        group = "somegroup"
        spec = lxml.etree.Element("AuthorizedKeys")
        lxml.etree.SubElement(spec, "Allow",
                              attrib={"from": pubkey, "group": group})
        akg.XMLMatch.return_value = spec
        self.assertEqual(akg.get_data(entry, metadata),
                         "%s %s" % (group, pubkey))
        akg.XMLMatch.assert_called_with(metadata)
        self.assertItemsEqual(mock_ClientMetadata.call_args[0][2], [group])
        self.assertEqual(akg.core.Bind.call_args[0][0].get("name"), pubkey)
        self.assertIn(group, akg.core.Bind.call_args[0][1].groups)

        reset()
        host = "baz.example.com"
        spec = lxml.etree.Element("AuthorizedKeys")
        lxml.etree.SubElement(
            lxml.etree.SubElement(spec,
                                  "Allow",
                                  attrib={"from": pubkey, "host": host}),
            "Params", foo="foo", bar="bar=bar")
        akg.XMLMatch.return_value = spec
        params, actual_host, actual_pubkey = akg.get_data(entry,
                                                          metadata).split()
        self.assertEqual(actual_host, host)
        self.assertEqual(actual_pubkey, pubkey)
        self.assertItemsEqual(params.split(","), ["foo=foo", "bar=bar=bar"])
        akg.XMLMatch.assert_called_with(metadata)
        akg.core.build_metadata.assert_called_with(host)
        self.assertEqual(akg.core.Bind.call_args[0][0].get("name"), pubkey)
        self.assertEqual(akg.core.Bind.call_args[0][1].hostname, host)

        reset()
        spec = lxml.etree.Element("AuthorizedKeys")
        text = lxml.etree.SubElement(spec, "Allow")
        text.text = "ssh-rsa publickey /foo/bar\n"
        lxml.etree.SubElement(text, "Params", foo="foo")
        akg.XMLMatch.return_value = spec
        self.assertEqual(akg.get_data(entry, metadata),
                         "foo=foo %s" % text.text.strip())
        akg.XMLMatch.assert_called_with(metadata)
        self.assertFalse(akg.core.build_metadata.called)
        self.assertFalse(akg.core.Bind.called)

        reset()
        lxml.etree.SubElement(spec, "Allow", attrib={"from": pubkey})
        akg.XMLMatch.return_value = spec
        self.assertItemsEqual(akg.get_data(entry, metadata).splitlines(),
                              ["foo=foo %s" % text.text.strip(),
                               "profile %s" % pubkey])
        akg.XMLMatch.assert_called_with(metadata)

        reset()
        metadata.group_in_category.return_value = ''
        spec = lxml.etree.Element("AuthorizedKeys")
        lxml.etree.SubElement(spec, "Allow", attrib={"from": pubkey})
        akg.XMLMatch.return_value = spec
        self.assertEqual(akg.get_data(entry, metadata), '')
        akg.XMLMatch.assert_called_with(metadata)
        self.assertFalse(akg.core.build_metadata.called)
        self.assertFalse(akg.core.Bind.called)
        self.assertFalse(mock_ClientMetadata.called)
