import os
import sys
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Compat import long
from Bcfg2.Client.Tools import Tool, SvcTool, PkgTool, \
    ToolInstantiationError

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


class TestTool(Bcfg2TestCase):
    test_obj = Tool

    def get_obj(self, setup=None, config=None):
        if config is None:
            config = lxml.etree.Element("Configuration")
        if not setup:
            setup = MagicMock()
        if 'command_timeout' not in setup:
            setup['command_timeout'] = None

        execs = self.test_obj.__execs__
        self.test_obj.__execs__ = []

        @patch("Bcfg2.Options.get_option_parser")
        def inner(mock_option_parser):
            mock_option_parser.return_value = setup
            return self.test_obj(config)

        rv = inner()
        self.test_obj.__execs__ = execs
        return rv

    def test__init(self):
        @patch("%s.%s._check_execs" % (self.test_obj.__module__,
                                       self.test_obj.__name__))
        @patch("%s.%s._analyze_config" % (self.test_obj.__module__,
                                          self.test_obj.__name__))
        def inner(mock_analyze_config, mock_check_execs):
            t = self.get_obj()
            mock_analyze_config.assert_called_with()
            mock_check_execs.assert_called_with()

    def test__analyze_config(self):
        t = self.get_obj()
        t.getSupportedEntries = Mock()

        t.__important__ = ["/test"]
        important = []
        t.config = lxml.etree.Element("Config")
        bundle1 = lxml.etree.SubElement(t.config, "Bundle")
        important.append(lxml.etree.SubElement(bundle1, "Path",
                                               name="/foo", important="true"))
        lxml.etree.SubElement(bundle1, "Package", name="bar", important="true")
        lxml.etree.SubElement(bundle1, "Path", name="/bar")
        bundle2 = lxml.etree.SubElement(t.config, "Bundle")
        important.append(lxml.etree.SubElement(bundle2, "Path", name="/quux",
                                               important="true"))
        lxml.etree.SubElement(bundle2, "Path", name="/baz", important="false")

        t._analyze_config()
        self.assertItemsEqual(t.__important__,
                              ["/test"] + [e.get("name") for e in important])
        t.getSupportedEntries.assert_called_with()

    def test__check_execs(self):
        t = self.get_obj()
        if t.__execs__ == []:
            t.__execs__.append("/bin/true")

        @patch("os.stat")
        def inner(mock_stat):
            mock_stat.return_value = (33261, 2245040, long(64770), 1, 0, 0,
                                      25552, 1360831382, 1352194410,
                                      1354626626)
            t._check_execs()
            self.assertItemsEqual(mock_stat.call_args_list,
                                  [call(e) for e in t.__execs__])

            # not executable
            mock_stat.reset_mock()
            mock_stat.return_value = (33188, 2245040, long(64770), 1, 0, 0,
                                      25552, 1360831382, 1352194410,
                                      1354626626)
            self.assertRaises(ToolInstantiationError, t._check_execs)

            # non-existant
            mock_stat.reset_mock()
            mock_stat.side_effect = OSError
            self.assertRaises(ToolInstantiationError, t._check_execs)

        inner()

    def test_BundleUpdated(self):
        pass

    def test_BundleNotUpdated(self):
        pass

    def test_Inventory(self):
        t = self.get_obj()
        t.canVerify = Mock()
        t.canVerify.side_effect = lambda e: e.get("verify") != "false"
        t.buildModlist = Mock()
        t.FindExtra = Mock()
        t.VerifyPath = Mock()
        t.VerifyPackage = Mock()
        t.VerifyService = Mock()

        def reset():
            t.canVerify.reset_mock()
            t.buildModlist.reset_mock()
            t.FindExtra.reset_mock()
            t.VerifyPath.reset_mock()
            t.VerifyPackage.reset_mock()
            t.VerifyService.reset_mock()

        paths = []
        packages = []
        services = []
        config = lxml.etree.Element("Configuration")
        bundle1 = lxml.etree.SubElement(config, "Bundle")
        paths.append(lxml.etree.SubElement(bundle1, "Path", name="/foo"))
        lxml.etree.SubElement(bundle1, "Package", name="foo", verify="false")
        packages.append(lxml.etree.SubElement(bundle1, "Package", name="bar"))
        lxml.etree.SubElement(bundle1, "Bogus")

        bundle2 = lxml.etree.SubElement(config, "Bundle")
        paths.append(lxml.etree.SubElement(bundle2, "Path", name="/bar"))
        services.append(lxml.etree.SubElement(bundle2, "Service", name="bar"))
        lxml.etree.SubElement(bundle2, "Path", name="/baz", verify="false")

        expected_states = dict([(e, t.VerifyPath.return_value)
                                for e in paths])
        expected_states.update(dict([(e, t.VerifyPackage.return_value)
                                     for e in packages]))
        expected_states.update(dict([(e, t.VerifyService.return_value)
                                     for e in services]))

        def perform_assertions(states):
            t.buildModlist.assert_called_with()
            t.FindExtra.assert_called_with()
            self.assertItemsEqual(t.canVerify.call_args_list,
                                  [call(e) for e in bundle1.getchildren()] + \
                                      [call(e) for e in bundle2.getchildren()])
            self.assertItemsEqual(t.VerifyPath.call_args_list,
                                  [call(e, t.buildModlist.return_value)
                                   for e in paths])
            self.assertItemsEqual(t.VerifyPackage.call_args_list,
                                  [call(e, t.buildModlist.return_value)
                                   for e in packages])
            self.assertItemsEqual(t.VerifyService.call_args_list,
                                  [call(e, t.buildModlist.return_value)
                                   for e in services])
            self.assertItemsEqual(states, expected_states)
            self.assertEqual(t.extra, t.FindExtra.return_value)

        actual_states = t.Inventory(structures=[bundle1, bundle2])
        perform_assertions(actual_states)

        reset()
        t.config = config
        actual_states = t.Inventory()
        perform_assertions(actual_states)

    def test_Install(self):
        t = self.get_obj()
        t.InstallPath = Mock()
        t.InstallPackage = Mock()
        t.InstallService = Mock()

        t.InstallPath.side_effect = lambda e: e.get("modified") == "true"
        t.InstallPackage.side_effect = lambda e: e.get("modified") == "true"
        t.InstallService.side_effect = lambda e: e.get("modified") == "true"

        entries = [lxml.etree.Element("Path", name="/foo", modified="true"),
                   lxml.etree.Element("Package", name="bar", modified="true"),
                   lxml.etree.Element("Bogus"),
                   lxml.etree.Element("Path", name="/bar", modified="true"),
                   lxml.etree.Element("Service", name="bar")]

        expected_states = dict([(e, t.InstallPath.return_value)
                                for e in entries if e.tag == "Path"])
        expected_states.update(dict([(e, t.InstallPackage.return_value)
                                     for e in entries if e.tag == "Package"]))
        expected_states.update(dict([(e, t.InstallService.return_value)
                                     for e in entries if e.tag == "Service"]))

        t.modified = []
        actual_states = t.Install(entries)
        self.assertItemsEqual(t.InstallPath.call_args_list,
                              [call(e) for e in entries if e.tag == "Path"])
        self.assertItemsEqual(t.InstallPackage.call_args_list,
                              [call(e) for e in entries if e.tag == "Package"])
        self.assertItemsEqual(t.InstallService.call_args_list,
                              [call(e) for e in entries if e.tag == "Service"])
        self.assertItemsEqual(actual_states, expected_states)
        self.assertItemsEqual(t.modified,
                              [e for e in entries
                               if e.get("modified") == "true"])

    def rest_Remove(self):
        pass

    def test_getSupportedEntries(self):
        t = self.get_obj()

        def handlesEntry(entry):
            return entry.get("handled") == "true"
        t.handlesEntry = Mock()
        t.handlesEntry.side_effect = handlesEntry

        handled = []
        t.config = lxml.etree.Element("Config")
        bundle1 = lxml.etree.SubElement(t.config, "Bundle")
        lxml.etree.SubElement(bundle1, "Path", name="/foo")
        handled.append(lxml.etree.SubElement(bundle1, "Path", name="/bar",
                                             handled="true"))
        bundle2 = lxml.etree.SubElement(t.config, "Bundle")
        handled.append(lxml.etree.SubElement(bundle2, "Path", name="/quux",
                                             handled="true"))
        lxml.etree.SubElement(bundle2, "Path", name="/baz")

        self.assertItemsEqual(handled,
                              t.getSupportedEntries())

    def test_handlesEntry(self):
        t = self.get_obj()
        handles = t.__handles__
        t.__handles__ = [("Path", "file"),
                         ("Package", "yum")]
        self.assertTrue(t.handlesEntry(lxml.etree.Element("Path", type="file",
                                                          name="/foo")))
        self.assertFalse(t.handlesEntry(lxml.etree.Element("Path",
                                                           type="permissions",
                                                           name="/bar")))
        self.assertFalse(t.handlesEntry(lxml.etree.Element("Bogus",
                                                           type="file",
                                                           name="/baz")))
        self.assertTrue(t.handlesEntry(lxml.etree.Element("Package",
                                                          type="yum",
                                                          name="quux")))
        t.__handles__ = handles

    def test_buildModlist(self):
        t = self.get_obj()
        paths = []

        t.config = lxml.etree.Element("Config")
        bundle1 = lxml.etree.SubElement(t.config, "Bundle")
        paths.append(lxml.etree.SubElement(bundle1, "Path", name="/foo"))
        lxml.etree.SubElement(bundle1, "Package", name="bar")
        paths.append(lxml.etree.SubElement(bundle1, "Path", name="/bar"))
        bundle2 = lxml.etree.SubElement(t.config, "Bundle")
        paths.append(lxml.etree.SubElement(bundle2, "Path", name="/quux"))
        lxml.etree.SubElement(bundle2, "Service", name="baz")

        self.assertItemsEqual([p.get("name") for p in paths],
                              t.buildModlist())

    def test_missing_attrs(self):
        t = self.get_obj()
        req = t.__req__
        t.__req__ = dict(Path=dict(file=["name"],
                                   permissions=["name", "owner", "group"]),
                         Package=["name"])
        # tuples of <entry>, <return value>
        cases = [
            (lxml.etree.Element("Path", name="/foo"), ["type"]),
            (lxml.etree.Element("Path", type="file"), ["name"]),
            (lxml.etree.Element("Path", type="file", name="/foo"), []),
            (lxml.etree.Element("Path", type="permissions", name="/foo"),
             ["owner", "group"]),
            (lxml.etree.Element("Path", type="permissions", name="/foo",
                                owner="root", group="root", mode="0644"), []),
            (lxml.etree.Element("Package", type="yum"), ["name"]),
            (lxml.etree.Element("Package", type="yum", name="/bar"), []),
            (lxml.etree.Element("Package", type="apt", name="/bar"), [])]
        for entry, expected in cases:
            self.assertItemsEqual(t.missing_attrs(entry), expected)

        t.__req__ = req

    def test_canVerify(self):
        t = self.get_obj()
        entry = Mock()
        t._entry_is_complete = Mock()
        self.assertEqual(t.canVerify(entry),
                         t._entry_is_complete.return_value)
        t._entry_is_complete.assert_called_with(entry, action="verify")

    def test_FindExtra(self):
        t = self.get_obj()
        self.assertItemsEqual(t.FindExtra(), [])

    def test_canInstall(self):
        t = self.get_obj()
        entry = Mock()
        t._entry_is_complete = Mock()
        self.assertEqual(t.canInstall(entry),
                         t._entry_is_complete.return_value)
        t._entry_is_complete.assert_called_with(entry, action="install")

    def test__entry_is_complete(self):
        t = self.get_obj()
        t.handlesEntry = Mock()
        t.missing_attrs = Mock()

        def reset():
            t.handlesEntry.reset_mock()
            t.missing_attrs.reset_mock()

        entry = lxml.etree.Element("Path", name="/test")

        t.handlesEntry.return_value = False
        t.missing_attrs.return_value = []
        self.assertFalse(t._entry_is_complete(entry))

        reset()
        t.handlesEntry.return_value = True
        t.missing_attrs.return_value = ["type"]
        self.assertFalse(t._entry_is_complete(entry))

        reset()
        t.missing_attrs.return_value = []
        self.assertTrue(t._entry_is_complete(entry))

        reset()
        entry.set("failure", "failure")
        self.assertFalse(t._entry_is_complete(entry))


class TestPkgTool(TestTool):
    test_obj = PkgTool

    def get_obj(self, **kwargs):
        @patch("%s.%s.RefreshPackages" % (self.test_obj.__module__,
                                          self.test_obj.__name__), Mock())
        def inner():
            return TestTool.get_obj(self, **kwargs)

        return inner()

    def test_VerifyPackage(self):
        pt = self.get_obj()
        self.assertRaises(NotImplementedError,
                          pt.VerifyPackage, Mock(), Mock())

    def test_Install(self):
        pt = self.get_obj()
        pt.cmd = Mock()
        pt.RefreshPackages = Mock()
        pt.VerifyPackage = Mock()
        pt._get_package_command = Mock()
        pt._get_package_command.side_effect = lambda pkgs: \
            [p.get("name") for p in pkgs]
        packages = [lxml.etree.Element("Package", type="echo", name="foo",
                                       version="1.2.3"),
                    lxml.etree.Element("Package", type="echo", name="bar",
                                       version="any"),
                    lxml.etree.Element("Package", type="echo", name="baz",
                                       version="2.3.4")]

        def reset():
            pt.cmd.reset_mock()
            pt.RefreshPackages.reset_mock()
            pt.VerifyPackage.reset_mock()
            pt._get_package_command.reset_mock()
            pt.modified = []

        # test single-pass install success
        reset()
        pt.cmd.run.return_value = True
        states = pt.Install(packages)
        pt._get_package_command.assert_called_with(packages)
        pt.cmd.run.assert_called_with([p.get("name") for p in packages])
        self.assertItemsEqual(states,
                              dict([(p, True) for p in packages]))
        self.assertItemsEqual(pt.modified, packages)

        # test failed single-pass install
        reset()

        def run(cmd):
            if "foo" in cmd:
                # fail when installing all packages, and when installing foo
                return False
            # succeed otherwise
            return True

        pt.VerifyPackage.side_effect = lambda p, m: p.get("name") == "bar"

        pt.cmd.run.side_effect = run
        states = pt.Install(packages)
        pt._get_package_command.assert_any_call(packages)
        for pkg in packages:
            pt.VerifyPackage.assert_any_call(pkg, [])
            if pkg.get("name") != "bar":
                pt._get_package_command.assert_any_call([pkg])
        # pt.cmd.run is called once for all packages, and then once
        # for each package that does not verify.  "bar" verifies, so
        # it's run for foo and baz
        self.assertItemsEqual(pt.cmd.run.call_args_list,
                              [call([p.get("name") for p in packages]),
                               call(["foo"]),
                               call(["baz"])])
        pt.RefreshPackages.assert_called_with()
        self.assertItemsEqual(states,
                              dict([(p, p.get("name") != "bar")
                                    for p in packages]))
        # bar is modified, because it verifies successfully; baz is
        # modified, because it is installed successfully.  foo is not
        # installed successfully, so is not modified.
        self.assertItemsEqual(pt.modified,
                              [p for p in packages if p.get("name") != "foo"])

    def test__get_package_command(self):
        packages = [lxml.etree.Element("Package", type="test", name="foo",
                                       version="1.2.3"),
                    lxml.etree.Element("Package", type="test", name="bar",
                                       version="any"),
                    lxml.etree.Element("Package", type="test", name="baz",
                                       version="2.3.4")]
        pt = self.get_obj()
        pkgtool = pt.pkgtool
        pt.pkgtool = ("install %s", ("%s-%s", ["name", "version"]))
        self.assertEqual(pt._get_package_command([
                    lxml.etree.Element("Package", type="test", name="foo",
                                       version="1.2.3")]),
                         "install foo-1.2.3")
        self.assertItemsEqual(pt._get_package_command(packages).split(),
                              ["install", "foo-1.2.3", "bar-any", "baz-2.3.4"])

    def test_RefreshPackages(self):
        pt = self.get_obj()
        self.assertRaises(NotImplementedError, pt.RefreshPackages)

    def test_FindExtra(self):
        pt = self.get_obj()
        pt.getSupportedEntries = Mock()
        pt.getSupportedEntries.return_value = [
            lxml.etree.Element("Package", name="foo"),
            lxml.etree.Element("Package", name="bar"),
            lxml.etree.Element("Package", name="baz")]
        pt.installed = dict(foo="1.2.3",
                            bar="2.3.4",
                            quux="3.4.5",
                            xyzzy="4.5.6")
        extra = pt.FindExtra()
        self.assertEqual(len(extra), 2)
        self.assertItemsEqual([e.get("name") for e in extra],
                              ["quux", "xyzzy"])
        for el in extra:
            self.assertEqual(el.tag, "Package")
            self.assertEqual(el.get("type"), pt.pkgtype)


class TestSvcTool(TestTool):
    test_obj = SvcTool

    def test_start_service(self):
        st = self.get_obj()
        st.get_svc_command = Mock()
        st.cmd = MagicMock()
        service = lxml.etree.Element("Service", name="foo", type="test")
        self.assertEqual(st.start_service(service),
                         st.cmd.run.return_value)
        st.get_svc_command.assert_called_with(service, "start")
        st.cmd.run.assert_called_with(st.get_svc_command.return_value)

    def test_stop_service(self):
        st = self.get_obj()
        st.get_svc_command = Mock()
        st.cmd = MagicMock()
        service = lxml.etree.Element("Service", name="foo", type="test")
        self.assertEqual(st.stop_service(service),
                         st.cmd.run.return_value)
        st.get_svc_command.assert_called_with(service, "stop")
        st.cmd.run.assert_called_with(st.get_svc_command.return_value)

    def test_restart_service(self):
        st = self.get_obj()
        st.get_svc_command = Mock()
        st.cmd = MagicMock()

        def reset():
            st.get_svc_command.reset_mock()
            st.cmd.reset_mock()

        service = lxml.etree.Element("Service", name="foo", type="test")
        self.assertEqual(st.restart_service(service),
                         st.cmd.run.return_value)
        st.get_svc_command.assert_called_with(service, "restart")
        st.cmd.run.assert_called_with(st.get_svc_command.return_value)

        reset()
        service.set('target', 'reload')
        self.assertEqual(st.restart_service(service),
                         st.cmd.run.return_value)
        st.get_svc_command.assert_called_with(service, "reload")
        st.cmd.run.assert_called_with(st.get_svc_command.return_value)

    def test_check_service(self):
        st = self.get_obj()
        st.get_svc_command = Mock()
        st.cmd = MagicMock()
        service = lxml.etree.Element("Service", name="foo", type="test")

        def reset():
            st.get_svc_command.reset_mock()
            st.cmd.reset_mock()

        self.assertEqual(st.check_service(service),
                         st.cmd.run.return_value)
        st.get_svc_command.assert_called_with(service, "status")
        st.cmd.run.assert_called_with(st.get_svc_command.return_value)

        reset()
        self.assertEqual(st.check_service(service),
                         st.cmd.run.return_value)
        st.get_svc_command.assert_called_with(service, "status")
        st.cmd.run.assert_called_with(st.get_svc_command.return_value)

    def test_Remove(self):
        st = self.get_obj()
        st.InstallService = Mock()
        services = [lxml.etree.Element("Service", type="test", name="foo"),
                    lxml.etree.Element("Service", type="test", name="bar",
                                       status="on")]
        st.Remove(services)
        self.assertItemsEqual(st.InstallService.call_args_list,
                              [call(e) for e in services])
        for entry in services:
            self.assertEqual(entry.get("status"), "off")

    @patch("Bcfg2.Client.prompt")
    def test_BundleUpdated(self, mock_prompt):
        st = self.get_obj(setup=dict(interactive=False,
                                     servicemode='default'))
        st.handlesEntry = Mock()
        st.handlesEntry.side_effect = lambda e: e.tag == "Service"
        st.stop_service = Mock()
        st.stop_service.return_value = True
        st.restart_service = Mock()
        st.restart_service.side_effect = lambda e: e.get("name") != "failed"

        def reset():
            st.handlesEntry.reset_mock()
            st.stop_service.reset_mock()
            st.restart_service.reset_mock()
            mock_prompt.reset_mock()
            st.restarted = []

        norestart = lxml.etree.Element("Service", type="test",
                                       name="norestart", restart="false")
        interactive = lxml.etree.Element("Service", type="test",
                                         name="interactive", status="on",
                                         restart="interactive")
        interactive2 = lxml.etree.Element("Service", type="test",
                                          name="interactive2", status="on",
                                          restart="interactive")
        stop = lxml.etree.Element("Service", type="test", name="stop",
                                  status="off")
        restart = lxml.etree.Element("Service", type="test", name="restart",
                                     status="on")
        duplicate = lxml.etree.Element("Service", type="test", name="restart",
                                       status="on")
        failed = lxml.etree.Element("Service", type="test", name="failed",
                                    status="on")
        unhandled = lxml.etree.Element("Path", type="file", name="/unhandled")
        services = [norestart, interactive, interactive2, stop, restart,
                    duplicate, failed]
        entries = services + [unhandled]
        bundle = lxml.etree.Element("Bundle")
        bundle.extend(entries)

        # test in non-interactive mode
        reset()
        states = st.BundleUpdated(bundle)
        self.assertItemsEqual(st.handlesEntry.call_args_list,
                              [call(e) for e in entries])
        st.stop_service.assert_called_with(stop)
        self.assertItemsEqual(st.restart_service.call_args_list,
                              [call(restart), call(failed)])
        self.assertItemsEqual(st.restarted, [restart.get("name")])
        self.assertFalse(mock_prompt.called)

        # test in interactive mode
        reset()
        mock_prompt.side_effect = lambda p: "interactive2" not in p
        st.setup['interactive'] = True
        states = st.BundleUpdated(bundle)
        self.assertItemsEqual(st.handlesEntry.call_args_list,
                              [call(e) for e in entries])
        st.stop_service.assert_called_with(stop)
        self.assertItemsEqual(st.restart_service.call_args_list,
                              [call(restart), call(failed), call(interactive)])
        self.assertItemsEqual(st.restarted, [restart.get("name"),
                                             interactive.get("name")])
        self.assertEqual(len(mock_prompt.call_args_list), 4)

        # test in build mode
        reset()
        st.setup['interactive'] = False
        st.setup['servicemode'] = 'build'
        states = st.BundleUpdated(bundle)
        self.assertItemsEqual(st.handlesEntry.call_args_list,
                              [call(e) for e in entries])
        self.assertItemsEqual(st.stop_service.call_args_list,
                              [call(restart), call(duplicate), call(failed),
                               call(stop)])
        self.assertFalse(mock_prompt.called)
        self.assertFalse(st.restart_service.called)
        self.assertItemsEqual(st.restarted, [])

    @patch("Bcfg2.Client.Tools.Tool.Install")
    def test_Install(self, mock_Install):
        install = [lxml.etree.Element("Service", type="test", name="foo")]
        services = install + [lxml.etree.Element("Service", type="test",
                                                 name="bar", install="false")]
        st = self.get_obj()
        self.assertEqual(st.Install(services),
                         mock_Install.return_value)
        mock_Install.assert_called_with(st, install)

    def test_InstallService(self):
        st = self.get_obj()
        self.assertRaises(NotImplementedError, st.InstallService, Mock())
