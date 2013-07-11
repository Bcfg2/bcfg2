import os
import sys
import lxml.etree
import Bcfg2.Server.Plugin
from mock import Mock, MagicMock, patch
from Bcfg2.Server.Plugins.ACL import *

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
from TestPlugin import TestXMLFileBacked, TestStructFile, TestPlugin, \
    TestClientACLs


class TestFunctions(Bcfg2TestCase):
    def test_rmi_names_equal(self):
        good_cases = [('*', 'foo'),
                      ('foo', 'foo'),
                      ('foo.*', 'foo.bar'),
                      ('*.*', 'foo.bar'),
                      ('foo.bar', 'foo.bar'),
                      ('*.bar', 'foo.bar'),
                      ('foo.*.bar', 'foo.baz.bar')]
        bad_cases = [('foo', 'bar'),
                     ('*', 'foo.bar'),
                     ('*.*', 'foo'),
                     ('*.*', 'foo.bar.baz'),
                     ('foo.*', 'bar.foo'),
                     ('*.bar', 'bar.foo'),
                     ('foo.*', 'foobar')]
        for first, second in good_cases:
            self.assertTrue(rmi_names_equal(first, second),
                            "rmi_names_equal(%s, %s) unexpectedly False" %
                            (first, second))
            self.assertTrue(rmi_names_equal(second, first),
                            "rmi_names_equal(%s, %s) unexpectedly False" %
                            (second, first))
        for first, second in bad_cases:
            self.assertFalse(rmi_names_equal(first, second),
                             "rmi_names_equal(%s, %s) unexpectedly True" %
                             (first, second))
            self.assertFalse(rmi_names_equal(second, first),
                             "rmi_names_equal(%s, %s) unexpectedly True" %
                             (second, first))

    def test_ip_matches(self):
        good_cases = [
            ("192.168.1.1", lxml.etree.Element("test", address="192.168.1.1")),
            ("192.168.1.17", lxml.etree.Element("test", address="192.168.1.0",
                                                netmask="24")),
            ("192.168.1.17", lxml.etree.Element("test", address="192.168.1.0",
                                                netmask="255.255.255.0")),
            ("192.168.1.31", lxml.etree.Element("test", address="192.168.1.0",
                                                netmask="255.255.255.224")),
            ("192.168.1.31", lxml.etree.Element("test", address="192.168.1.0",
                                                netmask="27")),
            ("10.55.67.191", lxml.etree.Element("test", address="10.55.0.0",
                                                netmask="16"))]
        bad_cases = [
            ("192.168.1.1", lxml.etree.Element("test", address="192.168.1.2")),
            ("192.168.2.17", lxml.etree.Element("test", address="192.168.1.0",
                                                netmask="24")),
            ("192.168.2.17", lxml.etree.Element("test", address="192.168.1.0",
                                                netmask="255.255.255.0")),
            ("192.168.1.35", lxml.etree.Element("test", address="192.168.1.0",
                                                netmask="255.255.255.224")),
            ("192.168.1.35", lxml.etree.Element("test", address="192.168.1.0",
                                                netmask="27")),
            ("10.56.67.191", lxml.etree.Element("test", address="10.55.0.0",
                                                netmask="16"))]
        for ip, entry in good_cases:
            self.assertTrue(ip_matches(ip, entry),
                            "ip_matches(%s, %s) unexpectedly False" %
                            (ip, lxml.etree.tostring(entry)))
        for ip, entry in bad_cases:
            self.assertFalse(ip_matches(ip, entry),
                             "ip_matches(%s, %s) unexpectedly True" %
                             (ip, lxml.etree.tostring(entry)))


class TestIPACLFile(TestXMLFileBacked):
    test_obj = IPACLFile

    @patch("Bcfg2.Server.Plugins.ACL.ip_matches")
    @patch("Bcfg2.Server.Plugins.ACL.rmi_names_equal")
    def test_check_acl(self, mock_rmi_names_equal, mock_ip_matches):
        af = self.get_obj()
        ip = "10.0.0.8"
        rmi = "ACL.test"

        def reset():
            mock_rmi_names_equal.reset_mock()
            mock_ip_matches.reset_mock()

        # test default defer with no entries
        af.entries = []
        self.assertIsNone(af.check_acl(ip, rmi))

        # test explicit allow, deny, and defer
        entries = dict(Allow=lxml.etree.Element("Allow", method=rmi),
                       Deny=lxml.etree.Element("Deny", method=rmi),
                       Defer=lxml.etree.Element("Defer", method=rmi))
        af.entries = list(entries.values())

        def get_ip_matches(tag):
            def ip_matches(ip, entry):
                return entry.tag == tag

            return ip_matches

        mock_rmi_names_equal.return_value = True

        reset()
        mock_ip_matches.side_effect = get_ip_matches("Allow")
        self.assertTrue(af.check_acl(ip, rmi))
        mock_ip_matches.assert_called_with(ip, entries['Allow'])
        mock_rmi_names_equal.assert_called_with(rmi, rmi)

        reset()
        mock_ip_matches.side_effect = get_ip_matches("Deny")
        self.assertFalse(af.check_acl(ip, rmi))
        mock_ip_matches.assert_called_with(ip, entries['Deny'])
        mock_rmi_names_equal.assert_called_with(rmi, rmi)

        reset()
        mock_ip_matches.side_effect = get_ip_matches("Defer")
        self.assertIsNone(af.check_acl(ip, rmi))
        mock_ip_matches.assert_called_with(ip, entries['Defer'])
        mock_rmi_names_equal.assert_called_with(rmi, rmi)

        # test matching RMI names
        reset()
        mock_ip_matches.side_effect = lambda i, e: True
        mock_rmi_names_equal.side_effect = lambda a, b: a == b
        rmi = "ACL.test2"
        matching = lxml.etree.Element("Allow", method=rmi)
        af.entries.append(matching)
        self.assertTrue(af.check_acl(ip, rmi))
        mock_ip_matches.assert_called_with(ip, matching)
        self.assertTrue(
            call('ACL.test', rmi) in mock_rmi_names_equal.call_args_list or
            call(rmi, 'ACL.test') in mock_rmi_names_equal.call_args_list)

        # test implicit allow for localhost, defer for others
        reset()
        mock_ip_matches.side_effect = lambda i, e: False
        self.assertIsNone(af.check_acl(ip, rmi))

        reset()
        self.assertTrue(af.check_acl("127.0.0.1", rmi))


class TestMetadataACLFile(TestStructFile):
    test_obj = MetadataACLFile

    @patch("Bcfg2.Server.Plugins.ACL.rmi_names_equal")
    def test_check_acl(self, mock_rmi_names_equal):
        af = self.get_obj()
        af.Match = Mock()
        metadata = Mock()
        mock_rmi_names_equal.side_effect = lambda a, b: a == b

        def reset():
            af.Match.reset_mock()
            mock_rmi_names_equal.reset_mock()

        # test default allow
        af.entries = []
        self.assertTrue(af.check_acl(metadata, 'ACL.test'))

        # test explicit allow and deny
        reset()
        af.entries = [lxml.etree.Element("Allow", method='ACL.test'),
                      lxml.etree.Element("Deny", method='ACL.test2')]
        af.Match.return_value = af.entries
        self.assertTrue(af.check_acl(metadata, 'ACL.test'))
        af.Match.assert_called_with(metadata)
        self.assertIn(call('ACL.test', 'ACL.test'),
                      mock_rmi_names_equal.call_args_list)

        reset()
        self.assertFalse(af.check_acl(metadata, 'ACL.test2'))
        af.Match.assert_called_with(metadata)
        self.assertIn(call('ACL.test2', 'ACL.test2'),
                      mock_rmi_names_equal.call_args_list)

        # test default deny for non-localhost
        reset()
        self.assertFalse(af.check_acl(metadata, 'ACL.test3'))
        af.Match.assert_called_with(metadata)

        # test default allow for localhost
        reset()
        metadata.hostname = 'localhost'
        self.assertTrue(af.check_acl(metadata, 'ACL.test3'))
        af.Match.assert_called_with(metadata)


class TestACL(TestPlugin, TestClientACLs):
    test_obj = ACL

    def test_check_acl_ip(self):
        acl = self.get_obj()
        acl.ip_acls = Mock()
        self.assertEqual(acl.check_acl_ip(("192.168.1.10", "12345"),
                                          "ACL.test"),
                         acl.ip_acls.check_acl.return_value)
        acl.ip_acls.check_acl.assert_called_with("192.168.1.10", "ACL.test")

    def test_check_acl_metadata(self):
        acl = self.get_obj()
        acl.metadata_acls = Mock()
        metadata = Mock()
        self.assertEqual(acl.check_acl_metadata(metadata, "ACL.test"),
                         acl.metadata_acls.check_acl.return_value)
        acl.metadata_acls.check_acl.assert_called_with(metadata, "ACL.test")
