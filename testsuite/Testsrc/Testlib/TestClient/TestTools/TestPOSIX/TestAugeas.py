# -*- coding: utf-8 -*-
import os
import sys
import copy
import lxml.etree
import tempfile
from mock import Mock, MagicMock, patch
try:
    from Bcfg2.Client.Tools.POSIX.Augeas import *
    HAS_AUGEAS = True
except ImportError:
    POSIXAugeas = None
    HAS_AUGEAS = False

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from TestPOSIX.Testbase import TestPOSIXTool
from common import *


test_data = """<Test>
  <Empty/>
  <Text>content with spaces</Text>
  <Attrs foo="foo" bar="bar"/>
  <Children identical="false">
    <Foo/>
    <Bar attr="attr"/>
  </Children>
  <Children identical="true">
    <Thing>one</Thing>
    <Thing>two</Thing>
  </Children>
  <Children multi="true">
    <Thing>same</Thing>
    <Thing>same</Thing>
    <Thing>same</Thing>
    <Thing>same</Thing>
  </Children>
</Test>
"""

test_xdata = lxml.etree.XML(test_data)

if can_skip or HAS_AUGEAS:
    class TestPOSIXAugeas(TestPOSIXTool):
        test_obj = POSIXAugeas

        applied_commands = dict(
            insert=lxml.etree.Element(
                "Insert", label="Thing",
                path='Test/Children[#attribute/identical = "true"]/Thing'),
            set=lxml.etree.Element("Set", path="Test/Text/#text",
                                   value="content with spaces"),
            move=lxml.etree.Element(
                "Move", source="Test/Foo",
                destination='Test/Children[#attribute/identical = "false"]/Foo'),
            remove=lxml.etree.Element("Remove", path="Test/Bar"),
            clear=lxml.etree.Element("Clear", path="Test/Empty/#text"),
            setm=lxml.etree.Element(
                "SetMulti", sub="#text", value="same",
                base='Test/Children[#attribute/multi = "true"]/Thing'))

        @skipUnless(HAS_AUGEAS, "Python Augeas libraries not found")
        def setUp(self):
            fd, self.tmpfile = tempfile.mkstemp()
            os.fdopen(fd, 'w').write(test_data)

        def tearDown(self):
            tmpfile = getattr(self, "tmpfile", None)
            if tmpfile and os.path.exists(tmpfile):
                os.unlink(tmpfile)

        def test_fully_specified(self):
            ptool = self.get_obj()

            entry = lxml.etree.Element("Path", name="/test", type="augeas")
            self.assertFalse(ptool.fully_specified(entry))

            lxml.etree.SubElement(entry, "Set", path="/test", value="test")
            self.assertTrue(ptool.fully_specified(entry))

        def test_install(self):
            # this is tested adequately by the other tests
            pass

        def test_verify(self):
            # this is tested adequately by the other tests
            pass

        @patch("Bcfg2.Client.Tools.POSIX.Augeas.POSIXTool.verify")
        def _verify(self, commands, mock_verify):
            ptool = self.get_obj()
            mock_verify.return_value = True

            entry = lxml.etree.Element("Path", name=self.tmpfile,
                                       type="augeas", lens="Xml")
            entry.extend(commands)

            modlist = []
            self.assertTrue(ptool.verify(entry, modlist))
            mock_verify.assert_called_with(ptool, entry, modlist)
            self.assertXMLEqual(lxml.etree.parse(self.tmpfile).getroot(),
                                test_xdata)

        def test_verify_insert(self):
            """ Test successfully verifying an Insert command """
            self._verify([self.applied_commands['insert']])

        def test_verify_set(self):
            """ Test successfully verifying a Set command """
            self._verify([self.applied_commands['set']])

        def test_verify_move(self):
            """ Test successfully verifying a Move command """
            self._verify([self.applied_commands['move']])

        def test_verify_remove(self):
            """ Test successfully verifying a Remove command """
            self._verify([self.applied_commands['remove']])

        def test_verify_clear(self):
            """ Test successfully verifying a Clear command """
            self._verify([self.applied_commands['clear']])

        def test_verify_set_multi(self):
            """ Test successfully verifying a SetMulti command """
            self._verify([self.applied_commands['setm']])

        def test_verify_all(self):
            """ Test successfully verifying multiple commands """
            self._verify(self.applied_commands.values())

        @patch("Bcfg2.Client.Tools.POSIX.Augeas.POSIXTool.install")
        def _install(self, commands, expected, mock_install, **attrs):
            ptool = self.get_obj()
            mock_install.return_value = True

            entry = lxml.etree.Element("Path", name=self.tmpfile,
                                       type="augeas", lens="Xml")
            for key, val in attrs.items():
                entry.set(key, val)
            entry.extend(commands)

            self.assertTrue(ptool.install(entry))
            mock_install.assert_called_with(ptool, entry)
            self.assertXMLEqual(lxml.etree.parse(self.tmpfile).getroot(),
                                expected)

        def test_install_set_existing(self):
            """ Test setting the value of an existing node """
            expected = copy.deepcopy(test_xdata)
            expected.find("Text").text = "Changed content"
            self._install([lxml.etree.Element("Set", path="Test/Text/#text",
                                              value="Changed content")],
                          expected)

        def test_install_set_new(self):
            """ Test setting the value of an new node """
            expected = copy.deepcopy(test_xdata)
            newtext = lxml.etree.SubElement(expected, "NewText")
            newtext.text = "new content"
            self._install([lxml.etree.Element("Set", path="Test/NewText/#text",
                                              value="new content")],
                          expected)

        def test_install_remove(self):
            """ Test removing a node """
            expected = copy.deepcopy(test_xdata)
            expected.remove(expected.find("Attrs"))
            self._install(
                [lxml.etree.Element("Remove",
                                    path='Test/*[#attribute/foo = "foo"]')],
                expected)

        def test_install_move(self):
            """ Test moving a node """
            expected = copy.deepcopy(test_xdata)
            foo = expected.xpath("//Foo")[0]
            expected.append(foo)
            self._install(
                [lxml.etree.Element("Move", source='Test/Children/Foo',
                                    destination='Test/Foo')],
                expected)

        def test_install_clear(self):
            """ Test clearing a node """
            # TODO: clearing a node doesn't seem to work with the XML lens
            #
            # % augtool -b
            # augtool> set /augeas/load/Xml/incl[3] "/tmp/test.xml"
            # augtool> load
            # augtool> clear '/files/tmp/test.xml/Test/Text/#text'
            # augtool> save
            # error: Failed to execute command
            # saving failed (run 'print /augeas//error' for details)
            # augtool> print /augeas//error
            #
            # The error isn't useful.
            pass

        def test_install_set_multi(self):
            """ Test setting multiple nodes at once """
            expected = copy.deepcopy(test_xdata)
            for thing in expected.xpath("Children[@identical='true']/Thing"):
                thing.text = "same"
            self._install(
                [lxml.etree.Element(
                    "SetMulti", value="same",
                    base='Test/Children[#attribute/identical = "true"]',
                    sub="Thing/#text")],
                expected)

        def test_install_insert(self):
            """ Test inserting a node """
            expected = copy.deepcopy(test_xdata)
            children = expected.xpath("Children[@identical='true']")[0]
            thing = lxml.etree.Element("Thing")
            thing.text = "three"
            children.append(thing)
            self._install(
                [lxml.etree.Element(
                    "Insert",
                    path='Test/Children[#attribute/identical = "true"]/Thing[2]',
                    label="Thing", where="after"),
                 lxml.etree.Element(
                     "Set",
                     path='Test/Children[#attribute/identical = "true"]/Thing[3]/#text',
                     value="three")],
                expected)

        def test_install_initial(self):
            """ Test creating initial content and then modifying it """
            os.unlink(self.tmpfile)
            expected = copy.deepcopy(test_xdata)
            expected.find("Text").text = "Changed content"
            initial = lxml.etree.Element("Initial")
            initial.text = test_data
            modify = lxml.etree.Element("Set", path="Test/Text/#text",
                                        value="Changed content")
            self._install([initial, modify], expected, current_exists="false")
