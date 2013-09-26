import os
import sys
import lxml.etree
import Bcfg2.Server.Plugin
from mock import Mock, MagicMock, patch
try:
    from Bcfg2.Server.Plugins.AWSTags import *
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

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
from TestPlugin import TestPlugin, TestConnector, TestClientRunHooks

config = '''
<AWSTags>
  <Tag name="name-only">
    <Group>group1</Group>
    <Group>group2</Group>
  </Tag>
  <Tag name="name-and-value" value="value">
    <Group>group3</Group>
  </Tag>
  <Tag name="regex-(.*)">
    <Group>group-$1</Group>
  </Tag>
  <Tag name="regex-value" value="(.*)">
    <Group>group-$1</Group>
  </Tag>
</AWSTags>
'''

tags = {
    "empty.example.com": {},
    "no-matches.example.com": {"nameonly": "foo",
                               "Name": "no-matches",
                               "foo": "bar"},
    "foo.example.com": {"name-only": "name-only",
                        "name-and-value": "wrong",
                        "regex-name": "foo"},
    "bar.example.com": {"name-and-value": "value",
                        "regex-value": "bar"}}

groups = {
    "empty.example.com": [],
    "no-matches.example.com": [],
    "foo.example.com": ["group1", "group2", "group-name"],
    "bar.example.com": ["group3", "group-value", "group-bar"]}


def make_instance(name):
    rv = Mock()
    rv.private_dns_name = name
    rv.tags = tags[name]
    return rv


instances = [make_instance(n) for n in tags.keys()]


def get_all_instances(filters=None):
    insts = [i for i in instances
             if i.private_dns_name == filters['private-dns-name']]
    res = Mock()
    res.instances = insts
    return [res]


if HAS_BOTO:
    class TestAWSTags(TestPlugin, TestClientRunHooks, TestConnector):
        test_obj = AWSTags

        def get_obj(self, core=None):
            @patchIf(not isinstance(Bcfg2.Server.Plugins.AWSTags.connect_ec2,
                                    Mock),
                     "Bcfg2.Server.Plugins.AWSTags.connect_ec2", Mock())
            @patch("lxml.etree.Element", Mock())
            def inner():
                obj = TestPlugin.get_obj(self, core=core)
                obj.config.data = config
                obj.config.Index()
                return obj
            return inner()

        @patch("Bcfg2.Server.Plugins.AWSTags.connect_ec2")
        def test_connect(self, mock_connect_ec2):
            """ Test connection to EC2 """
            key_id = "a09sdbipasdf"
            access_key = "oiilb234ipwe9"

            def cfp_get(section, option):
                if option == "access_key_id":
                    return key_id
                elif option == "secret_access_key":
                    return access_key
                else:
                    return Mock()

            core = Mock()
            core.setup.cfp.get = Mock(side_effect=cfp_get)
            awstags = self.get_obj(core=core)
            mock_connect_ec2.assert_called_with(
                aws_access_key_id=key_id,
                aws_secret_access_key=access_key)

        def test_get_additional_data(self):
            """ Test AWSTags.get_additional_data() """
            awstags = self.get_obj()
            awstags._ec2.get_all_instances = \
                Mock(side_effect=get_all_instances)

            for hostname, expected in tags.items():
                metadata = Mock()
                metadata.hostname = hostname
                self.assertItemsEqual(awstags.get_additional_data(metadata),
                                      expected)

        def test_get_additional_groups_caching(self):
            """ Test AWSTags.get_additional_groups() with caching enabled """
            awstags = self.get_obj()
            awstags._ec2.get_all_instances = \
                Mock(side_effect=get_all_instances)

            for hostname, expected in groups.items():
                metadata = Mock()
                metadata.hostname = hostname
                actual = awstags.get_additional_groups(metadata)
                msg = """%s has incorrect groups:
actual:   %s
expected: %s""" % (hostname, actual, expected)
                self.assertItemsEqual(actual, expected, msg)
