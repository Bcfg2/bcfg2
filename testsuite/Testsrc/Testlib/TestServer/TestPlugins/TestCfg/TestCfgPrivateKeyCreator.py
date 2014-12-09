import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Compat import StringIO
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

    def setUp(self):
        TestXMLCfgCreator.setUp(self)
        set_setup_default("cfg_category", "category")

    @patch("Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator.get_cfg", Mock())
    def get_obj(self, name=None, fam=None):
        return TestXMLCfgCreator.get_obj(self, name=name)

    @patch("shutil.rmtree")
    def _gen_keypair(self, mock_mkdtemp, mock_rmtree):
        pkc = self.get_obj()
        pkc.cmd = Mock()
        pkc.XMLMatch = Mock()
        metadata = Mock()

        exc = Mock()
        exc.success = True
        pkc.cmd.run.return_value = exc

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
    @patch("tempfile.mkdtemp")
    @patch("%s.open" % builtins)
    def _create_private_key(self, expected, mock_open, mock_mkdtemp,
                            mock_rmtree, spec=None):
        pkc = self.get_obj(name="/home/foo/.ssh/id_rsa/privkey.xml")
        pkc.cmd = MockExecutor()
        pkc.pubkey_creator.write_data = Mock()
        pkc.write_data = Mock()
        mock_mkdtemp.return_value = datastore

        if spec is None:
            pkc.xdata = lxml.etree.Element("PrivateKey")
        else:
            pkc.xdata = spec

        privkey_filename = os.path.join(datastore, "privkey")
        pubkey_filename = os.path.join(datastore, "privkey.pub")

        entry = lxml.etree.Element("Path", name="/home/foo/.ssh/id_rsa")
        metadata = Mock()
        metadata.group_in_category.return_value = "foo"

        def open_key(fname):
            if fname == privkey_filename:
                return StringIO("privatekey")
            elif fname == pubkey_filename:
                return StringIO("ssh-rsa publickey foo@bar.com")
            else:
                self.fail("Unexpected open call: %s" % fname)

        mock_open.side_effect = open_key

        self.assertEqual(pkc.create_data(entry, metadata), "privatekey")
        self.assertItemsEqual(mock_open.call_args_list,
                              [call(pubkey_filename), call(privkey_filename)])
        self.assertItemsEqual(
            pkc.cmd.calls[0]['command'],
            ['ssh-keygen', '-f', privkey_filename] + expected)
        metadata.group_in_category.assert_called_with("category")
        pkc.pubkey_creator.write_data.assert_called_with(
            "ssh-rsa publickey /home/foo/.ssh/id_rsa.pub/id_rsa.pub.G50_foo\n",
            group="foo", prio=50)
        pkc.write_data.assert_called_with("privatekey", group="foo", prio=50)
        mock_rmtree.assert_called_with(datastore)

    def test_create_data(self):
        pass

    def test_create_private_key_defaults(self):
        self._create_private_key(['-t', 'rsa', '-N', ''])

    def test_create_private_key_spec(self):
        spec = lxml.etree.Element("PrivateKey")
        lxml.etree.SubElement(spec, "Params", bits="768", type="dsa")
        passphrase = lxml.etree.SubElement(spec, "Passphrase")
        passphrase.text = "foo"

        self._create_private_key(['-t', 'dsa', '-b', '768', '-N', 'foo'],
                                 spec=spec)
