import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.Cfg import CfgCreationError
from Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator import *
from Bcfg2.Server.Plugin import PluginExecutionError
import Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator
try:
    from Bcfg2.Server.Encryption import EVPError
    HAS_CRYPTO = True
except:
    HAS_CRYPTO = False

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
from TestServer.TestPlugins.TestCfg.Test_init import TestCfgCreator
from TestServer.TestPlugin.Testhelpers import TestStructFile


class TestCfgPrivateKeyCreator(TestCfgCreator, TestStructFile):
    test_obj = CfgPrivateKeyCreator
    should_monitor = False

    def get_obj(self, name=None, fam=None):
        return TestCfgCreator.get_obj(self, name=name)

    @patch("Bcfg2.Server.Plugins.Cfg.CfgCreator.handle_event")
    @patch("Bcfg2.Server.Plugin.helpers.StructFile.HandleEvent")
    def test_handle_event(self, mock_HandleEvent, mock_handle_event):
        pkc = self.get_obj()
        evt = Mock()
        pkc.handle_event(evt)
        mock_HandleEvent.assert_called_with(pkc, evt)
        mock_handle_event.assert_called_with(pkc, evt)

    def test_category(self):
        pkc = self.get_obj()
        pkc.setup = Mock()
        pkc.setup.cfp = Mock()
        pkc.setup.cfp.has_section.return_value = False
        pkc.setup.cfp.has_option.return_value = False

        self.assertIsNone(pkc.category)
        pkc.setup.cfp.has_section.assert_called_with("sshkeys")

        pkc.setup.reset_mock()
        pkc.setup.cfp.has_section.return_value = True
        self.assertIsNone(pkc.category)
        pkc.setup.cfp.has_section.assert_called_with("sshkeys")
        pkc.setup.cfp.has_option.assert_called_with("sshkeys", "category")

        pkc.setup.reset_mock()
        pkc.setup.cfp.has_option.return_value = True
        self.assertEqual(pkc.category, pkc.setup.cfp.get.return_value)
        pkc.setup.cfp.has_section.assert_called_with("sshkeys")
        pkc.setup.cfp.has_option.assert_called_with("sshkeys", "category")
        pkc.setup.cfp.get.assert_called_with("sshkeys", "category")

    @skipUnless(HAS_CRYPTO, "No crypto libraries found, skipping")
    @patchIf(HAS_CRYPTO,
             "Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator.get_passphrases")
    def test_passphrase(self, mock_get_passphrases):
        pkc = self.get_obj()
        pkc.setup = Mock()
        pkc.setup.cfp = Mock()
        pkc.setup.cfp.has_section.return_value = False
        pkc.setup.cfp.has_option.return_value = False

        self.assertIsNone(pkc.passphrase)
        pkc.setup.cfp.has_section.assert_called_with("sshkeys")

        pkc.setup.reset_mock()
        pkc.setup.cfp.has_section.return_value = True
        self.assertIsNone(pkc.passphrase)
        pkc.setup.cfp.has_section.assert_called_with("sshkeys")
        pkc.setup.cfp.has_option.assert_called_with("sshkeys",
                                                    "passphrase")

        pkc.setup.reset_mock()
        pkc.setup.cfp.get.return_value = "test"
        mock_get_passphrases.return_value = dict(test="foo", test2="bar")
        pkc.setup.cfp.has_option.return_value = True
        self.assertEqual(pkc.passphrase, "foo")
        pkc.setup.cfp.has_section.assert_called_with("sshkeys")
        pkc.setup.cfp.has_option.assert_called_with("sshkeys",
                                                    "passphrase")
        pkc.setup.cfp.get.assert_called_with("sshkeys", "passphrase")
        mock_get_passphrases.assert_called_with()

    @patch("shutil.rmtree")
    @patch("tempfile.mkdtemp")
    @patch("subprocess.Popen")
    def test__gen_keypair(self, mock_Popen, mock_mkdtemp, mock_rmtree):
        pkc = self.get_obj()
        pkc.XMLMatch = Mock()
        mock_mkdtemp.return_value = datastore
        metadata = Mock()

        proc = Mock()
        proc.wait.return_value = 0
        proc.communicate.return_value = MagicMock()
        mock_Popen.return_value = proc

        spec = lxml.etree.Element("PrivateKey")
        pkc.XMLMatch.return_value = spec

        def reset():
            pkc.XMLMatch.reset_mock()
            mock_Popen.reset_mock()
            mock_mkdtemp.reset_mock()
            mock_rmtree.reset_mock()

        self.assertEqual(pkc._gen_keypair(metadata),
                         os.path.join(datastore, "privkey"))
        pkc.XMLMatch.assert_called_with(metadata)
        mock_mkdtemp.assert_called_with()
        self.assertItemsEqual(mock_Popen.call_args[0][0],
                              ["ssh-keygen", "-f",
                               os.path.join(datastore, "privkey"),
                               "-t", "rsa", "-N", ""])

        reset()
        lxml.etree.SubElement(spec, "Params", bits="768", type="dsa")
        passphrase = lxml.etree.SubElement(spec, "Passphrase")
        passphrase.text = "foo"

        self.assertEqual(pkc._gen_keypair(metadata),
                         os.path.join(datastore, "privkey"))
        pkc.XMLMatch.assert_called_with(metadata)
        mock_mkdtemp.assert_called_with()
        self.assertItemsEqual(mock_Popen.call_args[0][0],
                              ["ssh-keygen", "-f",
                               os.path.join(datastore, "privkey"),
                               "-t", "dsa", "-b", "768", "-N", "foo"])

        reset()
        proc.wait.return_value = 1
        self.assertRaises(CfgCreationError, pkc._gen_keypair, metadata)
        mock_rmtree.assert_called_with(datastore)

    def test_get_specificity(self):
        pkc = self.get_obj()
        pkc.XMLMatch = Mock()

        metadata = Mock()

        def reset():
            pkc.XMLMatch.reset_mock()
            metadata.group_in_category.reset_mock()

        category = "Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator.CfgPrivateKeyCreator.category"
        @patch(category, None)
        def inner():
            pkc.XMLMatch.return_value = lxml.etree.Element("PrivateKey")
            self.assertItemsEqual(pkc.get_specificity(metadata),
                                  dict(host=metadata.hostname))
        inner()

        @patch(category, "foo")
        def inner2():
            pkc.XMLMatch.return_value = lxml.etree.Element("PrivateKey")
            self.assertItemsEqual(pkc.get_specificity(metadata),
                                  dict(group=metadata.group_in_category.return_value,
                                       prio=50))
            metadata.group_in_category.assert_called_with("foo")

            reset()
            pkc.XMLMatch.return_value = lxml.etree.Element("PrivateKey",
                                                           perhost="true")
            self.assertItemsEqual(pkc.get_specificity(metadata),
                                  dict(host=metadata.hostname))

            reset()
            pkc.XMLMatch.return_value = lxml.etree.Element("PrivateKey",
                                                           category="bar")
            self.assertItemsEqual(pkc.get_specificity(metadata),
                                  dict(group=metadata.group_in_category.return_value,
                                       prio=50))
            metadata.group_in_category.assert_called_with("bar")

            reset()
            pkc.XMLMatch.return_value = lxml.etree.Element("PrivateKey",
                                                           prio="10")
            self.assertItemsEqual(pkc.get_specificity(metadata),
                                  dict(group=metadata.group_in_category.return_value,
                                       prio=10))
            metadata.group_in_category.assert_called_with("foo")

            reset()
            pkc.XMLMatch.return_value = lxml.etree.Element("PrivateKey")
            metadata.group_in_category.return_value = ''
            self.assertItemsEqual(pkc.get_specificity(metadata),
                                  dict(host=metadata.hostname))
            metadata.group_in_category.assert_called_with("foo")

        inner2()

    @patch("shutil.rmtree")
    @patch("%s.open" % builtins)
    def test_create_data(self, mock_open, mock_rmtree):
        pkc = self.get_obj()
        pkc.XMLMatch = Mock()
        pkc.get_specificity = Mock()
        # in order to make ** magic work in older versions of python,
        # get_specificity() must return an actual dict, not just a
        # Mock object that works like a dict.  in order to test that
        # the get_specificity() return value is being used
        # appropriately, we put some dummy data in it and test for
        # that data
        pkc.get_specificity.side_effect = lambda m, s: dict(group="foo")
        pkc._gen_keypair = Mock()
        privkey = os.path.join(datastore, "privkey")
        pkc._gen_keypair.return_value = privkey
        pkc.pubkey_creator = Mock()
        pkc.pubkey_creator.get_filename.return_value = "pubkey.filename"
        pkc.write_data = Mock()

        entry = lxml.etree.Element("Path", name="/home/foo/.ssh/id_rsa")
        metadata = Mock()

        def open_read_rv():
            mock_open.return_value.read.side_effect = lambda: "privatekey"
            return "ssh-rsa publickey foo@bar.com"

        def reset():
            mock_open.reset_mock()
            mock_rmtree.reset_mock()
            pkc.XMLMatch.reset_mock()
            pkc.get_specificity.reset_mock()
            pkc._gen_keypair.reset_mock()
            pkc.pubkey_creator.reset_mock()
            pkc.write_data.reset_mock()
            mock_open.return_value.read.side_effect = open_read_rv

        reset()
        passphrase = "Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator.CfgPrivateKeyCreator.passphrase"

        @patch(passphrase, None)
        def inner():
            self.assertEqual(pkc.create_data(entry, metadata), "privatekey")
            pkc.XMLMatch.assert_called_with(metadata)
            pkc.get_specificity.assert_called_with(metadata,
                                                   pkc.XMLMatch.return_value)
            pkc._gen_keypair.assert_called_with(metadata,
                                                pkc.XMLMatch.return_value)
            self.assertItemsEqual(mock_open.call_args_list,
                                  [call(privkey + ".pub"), call(privkey)])
            pkc.pubkey_creator.get_filename.assert_called_with(group="foo")
            pkc.pubkey_creator.write_data.assert_called_with(
                "ssh-rsa publickey pubkey.filename\n", group="foo")
            pkc.write_data.assert_called_with("privatekey", group="foo")
            mock_rmtree.assert_called_with(datastore)

            reset()
            self.assertEqual(pkc.create_data(entry, metadata, return_pair=True),
                             ("ssh-rsa publickey pubkey.filename\n",
                              "privatekey"))
            pkc.XMLMatch.assert_called_with(metadata)
            pkc.get_specificity.assert_called_with(metadata,
                                                   pkc.XMLMatch.return_value)
            pkc._gen_keypair.assert_called_with(metadata,
                                                pkc.XMLMatch.return_value)
            self.assertItemsEqual(mock_open.call_args_list,
                                  [call(privkey + ".pub"), call(privkey)])
            pkc.pubkey_creator.get_filename.assert_called_with(group="foo")
            pkc.pubkey_creator.write_data.assert_called_with(
                "ssh-rsa publickey pubkey.filename\n",
                group="foo")
            pkc.write_data.assert_called_with("privatekey", group="foo")
            mock_rmtree.assert_called_with(datastore)

        inner()

        if HAS_CRYPTO:
            @patch(passphrase, "foo")
            @patch("Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator.ssl_encrypt")
            def inner2(mock_ssl_encrypt):
                reset()
                mock_ssl_encrypt.return_value = "encryptedprivatekey"
                Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator.HAS_CRYPTO = True
                self.assertEqual(pkc.create_data(entry, metadata),
                                 "encryptedprivatekey")
                pkc.XMLMatch.assert_called_with(metadata)
                pkc.get_specificity.assert_called_with(
                    metadata,
                    pkc.XMLMatch.return_value)
                pkc._gen_keypair.assert_called_with(metadata,
                                                    pkc.XMLMatch.return_value)
                self.assertItemsEqual(mock_open.call_args_list,
                                      [call(privkey + ".pub"), call(privkey)])
                pkc.pubkey_creator.get_filename.assert_called_with(group="foo")
                pkc.pubkey_creator.write_data.assert_called_with(
                    "ssh-rsa publickey pubkey.filename\n", group="foo")
                pkc.write_data.assert_called_with("encryptedprivatekey",
                                                  group="foo", ext=".crypt")
                mock_ssl_encrypt.assert_called_with("privatekey", "foo")
                mock_rmtree.assert_called_with(datastore)

            inner2()

