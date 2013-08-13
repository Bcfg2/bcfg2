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
from TestServer.TestPlugins.TestCfg.Test_init import TestXMLCfgCreator


class TestCfgPrivateKeyCreator(TestXMLCfgCreator):
    test_obj = CfgPrivateKeyCreator
    should_monitor = False

    def get_obj(self, name=None, fam=None):
        return TestXMLCfgCreator.get_obj(self, name=name)

    @patch("shutil.rmtree")
    @patch("tempfile.mkdtemp")
    def test__gen_keypair(self, mock_mkdtemp, mock_rmtree):
        pkc = self.get_obj()
        pkc.cmd = Mock()
        pkc.XMLMatch = Mock()
        mock_mkdtemp.return_value = datastore
        metadata = Mock()

        exc = Mock()
        exc.success = True
        pkc.cmd.run.return_value = exc

        spec = lxml.etree.Element("PrivateKey")
        pkc.XMLMatch.return_value = spec

        def reset():
            pkc.XMLMatch.reset_mock()
            pkc.cmd.reset_mock()
            mock_mkdtemp.reset_mock()
            mock_rmtree.reset_mock()

        self.assertEqual(pkc._gen_keypair(metadata),
                         os.path.join(datastore, "privkey"))
        pkc.XMLMatch.assert_called_with(metadata)
        mock_mkdtemp.assert_called_with()
        pkc.cmd.run.assert_called_with(["ssh-keygen", "-f",
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
        pkc.cmd.run.assert_called_with(["ssh-keygen", "-f",
                                        os.path.join(datastore, "privkey"),
                                        "-t", "dsa", "-b", "768", "-N", "foo"])

        reset()
        pkc.cmd.run.return_value.success = False
        self.assertRaises(CfgCreationError, pkc._gen_keypair, metadata)
        mock_rmtree.assert_called_with(datastore)

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
        pkc.get_specificity.side_effect = lambda m: dict(group="foo")
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
        self.assertEqual(pkc.create_data(entry, metadata), "privatekey")
        pkc.XMLMatch.assert_called_with(metadata)
        pkc.get_specificity.assert_called_with(metadata)
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
        pkc.get_specificity.assert_called_with(metadata)
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
