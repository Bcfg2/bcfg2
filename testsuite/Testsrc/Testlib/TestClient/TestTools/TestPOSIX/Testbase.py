import os
import sys
import copy
import stat
import lxml.etree
from mock import Mock, MagicMock, patch
import Bcfg2.Client.Tools
from Bcfg2.Client.Tools.POSIX.base import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from TestTools.Test_init import TestTool
from common import *

try:
    import selinux
    HAS_SELINUX = True
except ImportError:
    HAS_SELINUX = False

try:
    import posix1e
    HAS_ACLS = True
except ImportError:
    HAS_ACLS = False


class TestPOSIXTool(TestTool):
    test_obj = POSIXTool

    def test_fully_specified(self):
        # fully_specified should do no checking on the abstract
        # POSIXTool object
        ptool = self.get_obj()
        self.assertTrue(ptool.fully_specified(Mock()))

    @patch('os.stat')
    @patch('os.walk')
    def test_verify(self, mock_walk, mock_stat):
        ptool = self.get_obj()
        ptool._verify_metadata = Mock()
        entry = lxml.etree.Element("Path", name="/test", type="file")

        mock_stat.return_value = MagicMock()
        ptool._verify_metadata.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        ptool._verify_metadata.assert_called_with(entry)

        ptool._verify_metadata.reset_mock()
        ptool._verify_metadata.return_value = True
        self.assertTrue(ptool.verify(entry, []))
        ptool._verify_metadata.assert_called_with(entry)

        ptool._verify_metadata.reset_mock()
        entry.set("recursive", "true")
        walk_rv = [("/", ["dir1", "dir2"], ["file1", "file2"]),
                   ("/dir1", ["dir3"], []),
                   ("/dir2", [], ["file3", "file4"])]
        mock_walk.return_value = walk_rv
        self.assertTrue(ptool.verify(entry, []))
        mock_walk.assert_called_with(entry.get("name"))
        all_verifies = [call(entry)]
        for root, dirs, files in walk_rv:
            all_verifies.extend([call(entry, path=os.path.join(root, p))
                                 for p in dirs + files])
        self.assertItemsEqual(ptool._verify_metadata.call_args_list, all_verifies)

    @patch('os.walk')
    def test_install(self, mock_walk):
        ptool = self.get_obj()
        ptool._set_perms = Mock()
        entry = lxml.etree.Element("Path", name="/test", type="file")

        ptool._set_perms.return_value = True
        self.assertTrue(ptool.install(entry))
        ptool._set_perms.assert_called_with(entry)

        ptool._set_perms.reset_mock()
        entry.set("recursive", "true")
        walk_rv = [("/", ["dir1", "dir2"], ["file1", "file2"]),
                   ("/dir1", ["dir3"], []),
                   ("/dir2", [], ["file3", "file4"])]
        mock_walk.return_value = walk_rv

        ptool._set_perms.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_walk.assert_called_with(entry.get("name"))
        all_set_perms = [call(entry)]
        for root, dirs, files in walk_rv:
            all_set_perms.extend([call(entry, path=os.path.join(root, p))
                                 for p in dirs + files])
        self.assertItemsEqual(ptool._set_perms.call_args_list,
                              all_set_perms)

        mock_walk.reset_mock()
        ptool._set_perms.reset_mock()

        def set_perms_rv(entry, path=None):
            if path == '/dir2/file3':
                return False
            else:
                return True
        ptool._set_perms.side_effect = set_perms_rv

        self.assertFalse(ptool.install(entry))
        mock_walk.assert_called_with(entry.get("name"))
        self.assertItemsEqual(ptool._set_perms.call_args_list, all_set_perms)

    @patch('os.rmdir')
    @patch('os.unlink')
    @patch('shutil.rmtree')
    @patch('os.path.isdir')
    @patch('os.path.islink')
    def test_remove(self, mock_islink, mock_isdir, mock_rmtree, mock_unlink,
                    mock_rmdir):
        ptool = self.get_obj()
        entry = lxml.etree.Element("Path", name="/etc/foo")

        def reset():
            mock_islink.reset_mock()
            mock_isdir.reset_mock()
            mock_rmtree.reset_mock()
            mock_unlink.reset_mock()
            mock_rmdir.reset_mock()

        mock_islink.return_value = True
        mock_isdir.return_value = False
        ptool._remove(entry)
        mock_unlink.assert_called_with(entry.get('name'))
        self.assertFalse(mock_rmtree.called)
        self.assertFalse(mock_rmdir.called)

        reset()
        mock_islink.return_value = False
        mock_isdir.return_value = True
        ptool._remove(entry)
        mock_rmtree.assert_called_with(entry.get('name'))
        self.assertFalse(mock_unlink.called)
        self.assertFalse(mock_rmdir.called)

        reset()
        ptool._remove(entry, recursive=False)
        mock_rmdir.assert_called_with(entry.get('name'))
        self.assertFalse(mock_unlink.called)
        self.assertFalse(mock_rmtree.called)

        reset()
        mock_islink.return_value = False
        mock_isdir.return_value = False
        ptool._remove(entry, recursive=False)
        mock_unlink.assert_called_with(entry.get('name'))
        self.assertFalse(mock_rmtree.called)
        self.assertFalse(mock_rmdir.called)

    @patch('os.lstat')
    def test_exists(self, mock_lstat):
        entry = lxml.etree.Element("Path", name="/etc/foo", type="file")

        ptool = self.get_obj()
        ptool._remove = Mock()

        def reset():
            mock_lstat.reset_mock()
            ptool._remove.reset_mock()

        mock_lstat.side_effect = OSError
        self.assertFalse(ptool._exists(entry))
        mock_lstat.assert_called_with(entry.get('name'))
        self.assertFalse(ptool._remove.called)

        reset()
        rv = MagicMock()
        mock_lstat.return_value = rv
        mock_lstat.side_effect = None
        self.assertEqual(ptool._exists(entry), rv)
        mock_lstat.assert_called_with(entry.get('name'))
        self.assertFalse(ptool._remove.called)

        reset()
        self.assertEqual(ptool._exists(entry, remove=True), None)
        mock_lstat.assert_called_with(entry.get('name'))
        ptool._remove.assert_called_with(entry)

        reset()
        ptool._remove.side_effect = OSError
        self.assertEqual(ptool._exists(entry, remove=True), rv)
        mock_lstat.assert_called_with(entry.get('name'))
        ptool._remove.assert_called_with(entry)

    @patch("os.chown")
    @patch("os.chmod")
    @patch("os.utime")
    @patch("os.geteuid")
    def test_set_perms(self, mock_geteuid, mock_utime, mock_chmod, mock_chown):
        ptool = self.get_obj()
        ptool._norm_entry_uid = Mock()
        ptool._norm_entry_gid = Mock()
        ptool._set_acls = Mock()
        ptool._set_secontext = Mock()
        def reset():
            ptool._set_secontext.reset_mock()
            ptool._set_acls.reset_mock()
            ptool._norm_entry_gid.reset_mock()
            ptool._norm_entry_uid.reset_mock()
            mock_chmod.reset_mock()
            mock_chown.reset_mock()
            mock_utime.reset_mock()
            mock_geteuid.reset_mock()

        # pretend to run as root
        mock_geteuid.return_value = 0

        # test symlink -- no owner, group, permissions
        entry = lxml.etree.Element("Path", name="/etc/foo", to="/etc/bar",
                                   type="symlink")
        ptool._set_acls.return_value = True
        ptool._set_secontext.return_value = True
        self.assertTrue(ptool._set_perms(entry))
        ptool._set_secontext.assert_called_with(entry, path=entry.get("name"))
        ptool._set_acls.assert_called_with(entry, path=entry.get("name"))

        # test file with owner, group, permissions
        reset()
        entry = lxml.etree.Element("Path", name="/etc/foo", owner="owner",
                                   group="group", mode="644", type="file")
        ptool._norm_entry_uid.return_value = 10
        ptool._norm_entry_gid.return_value = 100
        self.assertTrue(ptool._set_perms(entry))
        ptool._norm_entry_uid.assert_called_with(entry)
        ptool._norm_entry_gid.assert_called_with(entry)
        mock_chown.assert_called_with(entry.get("name"), 10, 100)
        mock_chmod.assert_called_with(entry.get("name"),
                                      int(entry.get("mode"), 8))
        self.assertFalse(mock_utime.called)
        ptool._set_secontext.assert_called_with(entry, path=entry.get("name"))
        ptool._set_acls.assert_called_with(entry, path=entry.get("name"))

        # test file with owner, group, permissions, run as non-root
        mock_geteuid.return_value = 1000
        reset()
        entry = lxml.etree.Element("Path", name="/etc/foo", owner="owner",
                                   group="group", mode="644", type="file")
        self.assertTrue(ptool._set_perms(entry))
        self.assertFalse(ptool._norm_entry_uid.called)
        self.assertFalse(ptool._norm_entry_gid.called)
        self.assertFalse(mock_chown.called)
        mock_chmod.assert_called_with(entry.get("name"),
                                      int(entry.get("mode"), 8))
        self.assertFalse(mock_utime.called)
        ptool._set_secontext.assert_called_with(entry, path=entry.get("name"))
        ptool._set_acls.assert_called_with(entry, path=entry.get("name"))
        mock_geteuid.return_value = 0

        # test with mtime
        reset()
        mtime = 1344459042
        entry.set("mtime", str(mtime))
        self.assertTrue(ptool._set_perms(entry))
        ptool._norm_entry_uid.assert_called_with(entry)
        ptool._norm_entry_gid.assert_called_with(entry)
        mock_chown.assert_called_with(entry.get("name"), 10, 100)
        mock_chmod.assert_called_with(entry.get("name"),
                                      int(entry.get("mode"), 8))
        mock_utime.assert_called_with(entry.get("name"), (mtime, mtime))
        ptool._set_secontext.assert_called_with(entry, path=entry.get("name"))
        ptool._set_acls.assert_called_with(entry, path=entry.get("name"))

        reset()
        self.assertTrue(ptool._set_perms(entry, path='/etc/bar'))
        ptool._norm_entry_uid.assert_called_with(entry)
        ptool._norm_entry_gid.assert_called_with(entry)
        mock_chown.assert_called_with('/etc/bar', 10, 100)
        mock_chmod.assert_called_with('/etc/bar', int(entry.get("mode"), 8))
        mock_utime.assert_called_with(entry.get("name"), (mtime, mtime))
        ptool._set_secontext.assert_called_with(entry, path='/etc/bar')
        ptool._set_acls.assert_called_with(entry, path='/etc/bar')

        # test dev_type modification of perms, failure of chown
        reset()
        def chown_rv(path, owner, group):
            if owner == 0 and group == 0:
                return True
            else:
                raise KeyError
        os.chown.side_effect = chown_rv
        entry.set("type", "device")
        entry.set("dev_type", list(device_map.keys())[0])
        self.assertFalse(ptool._set_perms(entry))
        ptool._norm_entry_uid.assert_called_with(entry)
        ptool._norm_entry_gid.assert_called_with(entry)
        mock_chown.assert_called_with(entry.get("name"), 0, 0)
        mock_chmod.assert_called_with(entry.get("name"),
                                      int(entry.get("mode"), 8) | list(device_map.values())[0])
        mock_utime.assert_called_with(entry.get("name"), (mtime, mtime))
        ptool._set_secontext.assert_called_with(entry, path=entry.get("name"))
        ptool._set_acls.assert_called_with(entry, path=entry.get("name"))

        # test failure of chmod
        reset()
        os.chown.side_effect = None
        os.chmod.side_effect = OSError
        entry.set("type", "file")
        del entry.attrib["dev_type"]
        self.assertFalse(ptool._set_perms(entry))
        ptool._norm_entry_uid.assert_called_with(entry)
        ptool._norm_entry_gid.assert_called_with(entry)
        mock_chown.assert_called_with(entry.get("name"), 10, 100)
        mock_chmod.assert_called_with(entry.get("name"),
                                      int(entry.get("mode"), 8))
        mock_utime.assert_called_with(entry.get("name"), (mtime, mtime))
        ptool._set_secontext.assert_called_with(entry, path=entry.get("name"))
        ptool._set_acls.assert_called_with(entry, path=entry.get("name"))

        # test that even when everything fails, we try to do it all.
        # e.g., when chmod fails, we still try to apply acls, set
        # selinux context, etc.
        reset()
        os.chown.side_effect = OSError
        os.utime.side_effect = OSError
        ptool._set_acls.return_value = False
        ptool._set_secontext.return_value = False
        self.assertFalse(ptool._set_perms(entry))
        ptool._norm_entry_uid.assert_called_with(entry)
        ptool._norm_entry_gid.assert_called_with(entry)
        mock_chown.assert_called_with(entry.get("name"), 10, 100)
        mock_chmod.assert_called_with(entry.get("name"),
                                      int(entry.get("mode"), 8))
        mock_utime.assert_called_with(entry.get("name"), (mtime, mtime))
        ptool._set_secontext.assert_called_with(entry, path=entry.get("name"))
        ptool._set_acls.assert_called_with(entry, path=entry.get("name"))

    @skipUnless(HAS_ACLS, "ACLS not found, skipping")
    @patchIf(HAS_ACLS, "posix1e.ACL")
    @patchIf(HAS_ACLS, "posix1e.Entry")
    @patch("os.path.isdir")
    def test_set_acls(self, mock_isdir, mock_Entry, mock_ACL):
        ptool = self.get_obj()
        ptool._list_entry_acls = Mock()
        ptool._norm_uid = Mock()
        ptool._norm_gid = Mock()
        entry = lxml.etree.Element("Path", name="/etc/foo", type="file")

        # disable acls for the initial test
        Bcfg2.Client.Tools.POSIX.base.HAS_ACLS = False
        self.assertTrue(ptool._set_acls(entry))
        Bcfg2.Client.Tools.POSIX.base.HAS_ACLS = True

        # build a set of file ACLs to return from posix1e.ACL(file=...)
        file_acls = []
        acl = Mock()
        acl.tag_type = posix1e.ACL_USER
        acl.name = "remove"
        file_acls.append(acl)
        acl = Mock()
        acl.tag_type = posix1e.ACL_GROUP
        acl.name = "remove"
        file_acls.append(acl)
        acl = Mock()
        acl.tag_type = posix1e.ACL_MASK
        acl.name = "keep"
        file_acls.append(acl)
        remove_acls = [a for a in file_acls if a.name == "remove"]

        # build a set of ACLs listed on the entry as returned by
        # _list_entry_acls()
        entry_acls = {("default", posix1e.ACL_USER, "user"): 7,
                      ("access", posix1e.ACL_GROUP, "group"): 5}
        ptool._list_entry_acls.return_value = entry_acls
        ptool._norm_uid.return_value = 10
        ptool._norm_gid.return_value = 100

        # set up the unreasonably complex return value for
        # posix1e.ACL(), which has three separate uses
        fileacl_rv = MagicMock()
        fileacl_rv.valid.return_value = True
        fileacl_rv.__iter__.return_value = iter(file_acls)
        filedef_rv = MagicMock()
        filedef_rv.valid.return_value = True
        filedef_rv.__iter__.return_value = iter(file_acls)
        acl_rv = MagicMock()
        def mock_acl_rv(file=None, filedef=None, acl=None):
            if file:
                return fileacl_rv
            elif filedef:
                return filedef_rv
            elif acl:
                return acl_rv

        # set up the equally unreasonably complex return value for
        # posix1e.Entry, which returns a new entry and adds it to
        # an ACL, so we have to track the Mock objects it returns.
        # why can't they just have an acl.add_entry() method?!?
        acl_entries = []
        def mock_entry_rv(acl):
            rv = MagicMock()
            rv.acl = acl
            rv.permset = set()
            acl_entries.append(rv)
            return rv
        mock_Entry.side_effect = mock_entry_rv

        def reset():
            mock_isdir.reset_mock()
            mock_ACL.reset_mock()
            mock_Entry.reset_mock()
            fileacl_rv.reset_mock()

        # test fs mounted noacl
        mock_ACL.side_effect = IOError(95, "Operation not permitted")
        self.assertFalse(ptool._set_acls(entry))

        # test other error
        reset()
        mock_ACL.side_effect = IOError
        self.assertFalse(ptool._set_acls(entry))

        reset()
        mock_ACL.side_effect = mock_acl_rv
        mock_isdir.return_value = True
        self.assertTrue(ptool._set_acls(entry))
        self.assertItemsEqual(mock_ACL.call_args_list,
                              [call(file=entry.get("name")),
                               call(filedef=entry.get("name"))])
        self.assertItemsEqual(fileacl_rv.delete_entry.call_args_list,
                              [call(a) for a in remove_acls])
        self.assertItemsEqual(filedef_rv.delete_entry.call_args_list,
                              [call(a) for a in remove_acls])
        ptool._list_entry_acls.assert_called_with(entry)
        ptool._norm_uid.assert_called_with("user")
        ptool._norm_gid.assert_called_with("group")
        fileacl_rv.calc_mask.assert_any_call()
        fileacl_rv.applyto.assert_called_with(entry.get("name"),
                                              posix1e.ACL_TYPE_ACCESS)
        filedef_rv.calc_mask.assert_any_call()
        filedef_rv.applyto.assert_called_with(entry.get("name"),
                                              posix1e.ACL_TYPE_DEFAULT)

        # build tuples of the Entry objects that were added to acl
        # and defacl so they're easier to compare for equality
        added_acls = []
        for acl in acl_entries:
            added_acls.append((acl.acl, acl.tag_type, acl.qualifier,
                               sum(acl.permset)))
        self.assertItemsEqual(added_acls,
                              [(filedef_rv, posix1e.ACL_USER, 10, 7),
                               (fileacl_rv, posix1e.ACL_GROUP, 100, 5)])

        reset()
        # have to reassign these because they're iterators, and
        # they've already been iterated over once
        fileacl_rv.__iter__.return_value = iter(file_acls)
        filedef_rv.__iter__.return_value = iter(file_acls)
        ptool._list_entry_acls.reset_mock()
        ptool._norm_uid.reset_mock()
        ptool._norm_gid.reset_mock()
        mock_isdir.return_value = False
        acl_entries = []
        self.assertTrue(ptool._set_acls(entry, path="/bin/bar"))
        mock_ACL.assert_called_with(file="/bin/bar")
        self.assertItemsEqual(fileacl_rv.delete_entry.call_args_list,
                              [call(a) for a in remove_acls])
        ptool._list_entry_acls.assert_called_with(entry)
        ptool._norm_gid.assert_called_with("group")
        fileacl_rv.calc_mask.assert_any_call()
        fileacl_rv.applyto.assert_called_with("/bin/bar",
                                              posix1e.ACL_TYPE_ACCESS)

        added_acls = []
        for acl in acl_entries:
            added_acls.append((acl.acl, acl.tag_type, acl.qualifier,
                               sum(acl.permset)))
        self.assertItemsEqual(added_acls,
                              [(fileacl_rv, posix1e.ACL_GROUP, 100, 5)])

    @skipUnless(HAS_SELINUX, "SELinux not found, skipping")
    @patchIf(HAS_SELINUX, "selinux.restorecon")
    @patchIf(HAS_SELINUX, "selinux.lgetfilecon")
    @patchIf(HAS_SELINUX, "selinux.lsetfilecon")
    def test_set_secontext(self, mock_lsetfilecon, mock_lgetfilecon,
                           mock_restorecon):
        Bcfg2.Options.setup.secontext_ignore = ['dosfs_t']
        ptool = self.get_obj()
        entry = lxml.etree.Element("Path", name="/etc/foo", type="file")

        mock_lgetfilecon.return_value = (0, "system_u:object_r:foo_t")

        # disable selinux for the initial test
        Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = False
        self.assertTrue(ptool._set_secontext(entry))
        Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = True

        # no context given
        self.assertTrue(ptool._set_secontext(entry))
        self.assertFalse(mock_restorecon.called)
        self.assertFalse(mock_lsetfilecon.called)
        self.assertFalse(mock_lgetfilecon.called)

        mock_restorecon.reset_mock()
        mock_lsetfilecon.reset_mock()
        mock_lgetfilecon.reset_mock()
        entry.set("secontext", "__default__")
        self.assertTrue(ptool._set_secontext(entry))
        mock_restorecon.assert_called_with(entry.get("name"))
        mock_lgetfilecon.assert_called_once_with(entry.get("name"))
        self.assertFalse(mock_lsetfilecon.called)

        mock_restorecon.reset_mock()
        mock_lsetfilecon.reset_mock()
        mock_lgetfilecon.reset_mock()
        mock_lsetfilecon.return_value = 0
        entry.set("secontext", "foo_t")
        self.assertTrue(ptool._set_secontext(entry))
        self.assertFalse(mock_restorecon.called)
        mock_lgetfilecon.assert_called_once_with(entry.get("name"))
        mock_lsetfilecon.assert_called_with(entry.get("name"), "foo_t")

        mock_restorecon.reset_mock()
        mock_lsetfilecon.reset_mock()
        mock_lgetfilecon.reset_mock()
        mock_lsetfilecon.return_value = 1
        self.assertFalse(ptool._set_secontext(entry))
        self.assertFalse(mock_restorecon.called)
        mock_lgetfilecon.assert_called_once_with(entry.get("name"))
        mock_lsetfilecon.assert_called_with(entry.get("name"), "foo_t")

        # ignored filesystem
        mock_restorecon.reset_mock()
        mock_lsetfilecon.reset_mock()
        mock_lgetfilecon.reset_mock()
        mock_lgetfilecon.return_value = (0, "system_u:object_r:dosfs_t")
        self.assertTrue(ptool._set_secontext(entry))
        self.assertFalse(mock_restorecon.called)
        self.assertFalse(mock_lsetfilecon.called)
        mock_lgetfilecon.assert_called_once_with(entry.get("name"))

    @patch("grp.getgrnam")
    def test_norm_gid(self, mock_getgrnam):
        ptool = self.get_obj()
        self.assertEqual(5, ptool._norm_gid("5"))
        self.assertFalse(mock_getgrnam.called)

        mock_getgrnam.reset_mock()
        mock_getgrnam.return_value = ("group", "x", 5, [])
        self.assertEqual(5, ptool._norm_gid("group"))
        mock_getgrnam.assert_called_with("group")

    def test_norm_entry_gid(self):
        ptool = self.get_obj()
        ptool._norm_gid = Mock()
        entry = lxml.etree.Element("Path", name="/test", type="file",
                                   group="group", owner="user")
        self.assertEqual(ptool._norm_entry_gid(entry),
                         ptool._norm_gid.return_value)
        ptool._norm_gid.assert_called_with(entry.get("group"))

        ptool._norm_gid.reset_mock()
        ptool._norm_gid.side_effect = KeyError
        self.assertEqual(ptool._norm_entry_gid(entry), 0)
        ptool._norm_gid.assert_called_with(entry.get("group"))

    @patch("pwd.getpwnam")
    def test_norm_uid(self, mock_getpwnam):
        ptool = self.get_obj()
        self.assertEqual(5, ptool._norm_uid("5"))
        self.assertFalse(mock_getpwnam.called)

        mock_getpwnam.reset_mock()
        mock_getpwnam.return_value = ("user", "x", 5, 5, "User", "/home/user",
                                      "/bin/zsh")
        self.assertEqual(5, ptool._norm_uid("user"))
        mock_getpwnam.assert_called_with("user")

    def test_norm_entry_uid(self):
        ptool = self.get_obj()
        ptool._norm_uid = Mock()
        entry = lxml.etree.Element("Path", name="/test", type="file",
                                   group="group", owner="user")
        self.assertEqual(ptool._norm_entry_uid(entry),
                         ptool._norm_uid.return_value)
        ptool._norm_uid.assert_called_with(entry.get("owner"))

        ptool._norm_uid.reset_mock()
        ptool._norm_uid.side_effect = KeyError
        self.assertEqual(ptool._norm_entry_uid(entry), 0)
        ptool._norm_uid.assert_called_with(entry.get("owner"))

    def test_norm_acl_perms(self):
        # there's basically no reasonable way to test the Permset
        # object parsing feature without writing our own Mock object
        # that re-implements Permset.test(). silly pylibacl won't let
        # us create standalone Entry or Permset objects.
        ptool = self.get_obj()
        self.assertEqual(5, ptool._norm_acl_perms("5"))
        self.assertEqual(0, ptool._norm_acl_perms("55"))
        self.assertEqual(5, ptool._norm_acl_perms("rx"))
        self.assertEqual(5, ptool._norm_acl_perms("r-x"))
        self.assertEqual(6, ptool._norm_acl_perms("wr-"))
        self.assertEqual(0, ptool._norm_acl_perms("rwrw"))
        self.assertEqual(0, ptool._norm_acl_perms("-"))
        self.assertEqual(0, ptool._norm_acl_perms("a"))
        self.assertEqual(6, ptool._norm_acl_perms("rwa"))
        self.assertEqual(4, ptool._norm_acl_perms("rr"))

    @patch('os.lstat')
    def test__gather_data(self, mock_lstat):
        ptool = self.get_obj()
        path = '/test'
        mock_lstat.side_effect = OSError
        self.assertFalse(ptool._gather_data(path)[0])
        mock_lstat.assert_called_with(path)

        mock_lstat.reset_mock()
        mock_lstat.side_effect = None
        # create a return value
        stat_rv = MagicMock()
        def stat_getitem(key):
            if int(key) == stat.ST_UID:
                return 0
            elif int(key) == stat.ST_GID:
                return 10
            elif int(key) == stat.ST_MODE:
                # return extra bits in the mode to emulate a device
                # and ensure that they're stripped
                return int('060660', 8)
        stat_rv.__getitem__ = Mock(side_effect=stat_getitem)
        mock_lstat.return_value = stat_rv

        # disable selinux and acls for this call -- we test them
        # separately so that we can skip those tests as appropriate
        states = (Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX,
                  Bcfg2.Client.Tools.POSIX.base.HAS_ACLS)
        Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = False
        Bcfg2.Client.Tools.POSIX.base.HAS_ACLS = False
        self.assertEqual(ptool._gather_data(path),
                         (stat_rv, '0', '10', '0660', None, None))
        Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX, \
            Bcfg2.Client.Tools.POSIX.base.HAS_ACLS = states
        mock_lstat.assert_called_with(path)

    @skipUnless(HAS_SELINUX, "SELinux not found, skipping")
    def test__gather_data_selinux(self):
        ptool = self.get_obj()
        context = 'system_u:object_r:root_t:s0'
        path = '/test'

        @patch('os.lstat')
        @patchIf(HAS_SELINUX, "selinux.lgetfilecon")
        def inner(mock_lgetfilecon, mock_lstat):
            mock_lgetfilecon.return_value = [len(context) + 1, context]
            mock_lstat.return_value = MagicMock()
            mock_lstat.return_value.__getitem__.return_value = MagicMock()
            # disable acls for this call and test them separately
            state = (Bcfg2.Client.Tools.POSIX.base.HAS_ACLS,
                     Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX)
            Bcfg2.Client.Tools.POSIX.base.HAS_ACLS = False
            Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = True
            self.assertEqual(ptool._gather_data(path)[4], 'root_t')
            Bcfg2.Client.Tools.POSIX.base.HAS_ACLS, \
                Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = state
            mock_lgetfilecon.assert_called_with(path)

        inner()

    @skipUnless(HAS_ACLS, "ACLS not found, skipping")
    @patch('os.lstat')
    @patch('stat.S_ISLNK')
    def test__gather_data_acls(self, mock_S_ISLNK, mock_lstat):
        ptool = self.get_obj()
        ptool._list_file_acls = Mock()
        acls = {("default", posix1e.ACL_USER, "testuser"): "rwx",
                ("access", posix1e.ACL_GROUP, "testgroup"): "rx"}
        ptool._list_file_acls.return_value = acls
        path = '/test'
        mock_lstat.return_value = MagicMock()
        mock_lstat.return_value.__getitem__.return_value = MagicMock()
        mock_S_ISLNK.return_value = False
        # disable selinux for this call and test it separately
        state = (Bcfg2.Client.Tools.POSIX.base.HAS_ACLS,
                 Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX)
        Bcfg2.Client.Tools.POSIX.base.HAS_ACLS = True
        Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = False
        self.assertItemsEqual(ptool._gather_data(path)[5], acls)
        ptool._list_file_acls.assert_called_with(path)

        # symlinks can't have their own ACLs, so ensure that the
        # _list_file_acls call is skipped and no ACLs are returned
        mock_S_ISLNK.return_value = True
        ptool._list_file_acls.reset_mock()
        self.assertEqual(ptool._gather_data(path)[5], None)
        self.assertFalse(ptool._list_file_acls.called)

        Bcfg2.Client.Tools.POSIX.base.HAS_ACLS, \
            Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = state

    @patchIf(HAS_SELINUX, "selinux.matchpathcon")
    def test_verify_metadata(self, mock_matchpathcon):
        ptool = self.get_obj()
        ptool._norm_entry_uid = Mock()
        ptool._norm_entry_gid = Mock()
        ptool._verify_acls = Mock()
        ptool._gather_data = Mock()
        entry = lxml.etree.Element("Path", name="/test", type="file",
                                   group="group", owner="user", mode="664",
                                   secontext='unconfined_u:object_r:etc_t:s0')
        # _verify_metadata() mutates the entry, so we keep a backup so we
        # can start fresh every time
        orig_entry = copy.deepcopy(entry)

        def reset():
            ptool._gather_data.reset_mock()
            ptool._verify_acls.reset_mock()
            ptool._norm_entry_uid.reset_mock()
            ptool._norm_entry_gid.reset_mock()
            return copy.deepcopy(orig_entry)

        # test nonexistent file
        ptool._gather_data.return_value = (False, None, None, None, None, None)
        self.assertFalse(ptool._verify_metadata(entry))
        self.assertEqual(entry.get("current_exists", "").lower(), "false")
        ptool._gather_data.assert_called_with(entry.get("name"))

        # expected data.  tuple of attr, return value index, value
        expected = [('current_owner', 1, '0'),
                    ('current_group', 2, '10'),
                    ('current_mode', 3, '0664'),
                    ('current_secontext', 4, 'etc_t')]
        ptool._norm_entry_uid.return_value = 0
        ptool._norm_entry_gid.return_value = 10
        gather_data_rv = [MagicMock(), None, None, None, None, []]
        for attr, idx, val in expected:
            gather_data_rv[idx] = val

        entry = reset()
        ptool._gather_data.return_value = tuple(gather_data_rv)
        self.assertTrue(ptool._verify_metadata(entry))
        ptool._gather_data.assert_called_with(entry.get("name"))
        ptool._verify_acls.assert_called_with(entry, path=entry.get("name"))
        self.assertEqual(entry.get("current_exists", 'true'), 'true')
        for attr, idx, val in expected:
            self.assertEqual(entry.get(attr), val)

        # test when secontext is None
        entry = reset()
        gather_data_rv[4] = None
        sestate = Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX
        Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = False
        ptool._gather_data.return_value = tuple(gather_data_rv)
        self.assertTrue(ptool._verify_metadata(entry))
        ptool._gather_data.assert_called_with(entry.get("name"))
        ptool._verify_acls.assert_called_with(entry, path=entry.get("name"))
        self.assertEqual(entry.get("current_exists", 'true'), 'true')
        for attr, idx, val in expected:
            if attr != 'current_secontext':
                self.assertEqual(entry.get(attr), val)
        Bcfg2.Client.Tools.POSIX.base.HAS_SELINUX = sestate

        gather_data_rv = [MagicMock(), None, None, None, None, []]
        for attr, idx, val in expected:
            gather_data_rv[idx] = val
        ptool._gather_data.return_value = tuple(gather_data_rv)

        stat_mode = 17407
        mtime = 1344430414
        stat_rv = (stat_mode, Mock(), Mock(), Mock(), Mock(), Mock(), Mock(),
                   Mock(), mtime, Mock())
        gather_data_rv[0] = stat_rv
        entry = reset()
        entry.set("mtime", str(mtime))
        ptool._gather_data.return_value = tuple(gather_data_rv)
        self.assertTrue(ptool._verify_metadata(entry))
        ptool._gather_data.assert_called_with(entry.get("name"))
        ptool._verify_acls.assert_called_with(entry, path=entry.get("name"))
        self.assertEqual(entry.get("current_exists", 'true'), 'true')
        for attr, idx, val in expected:
            self.assertEqual(entry.get(attr), val)
        self.assertEqual(entry.get("current_mtime"), str(mtime))

        # failure modes for each checked datum. tuple of changed attr,
        # return value index, new (failing) value
        failures = [('current_owner', 1, '10'),
                    ('current_group', 2, '100'),
                    ('current_mode', 3, '0660')]
        if HAS_SELINUX:
            failures.append(('current_secontext', 4, 'root_t'))

        for fail_attr, fail_idx, fail_val in failures:
            entry = reset()
            entry.set("mtime", str(mtime))
            gather_data_rv = [stat_rv, None, None, None, None, []]
            for attr, idx, val in expected:
                gather_data_rv[idx] = val
            gather_data_rv[fail_idx] = fail_val
            ptool._gather_data.return_value = tuple(gather_data_rv)
            self.assertFalse(ptool._verify_metadata(entry))
            ptool._gather_data.assert_called_with(entry.get("name"))
            ptool._verify_acls.assert_called_with(entry, path=entry.get("name"))
            self.assertEqual(entry.get("current_exists", 'true'), 'true')
            self.assertEqual(entry.get(fail_attr), fail_val)
            for attr, idx, val in expected:
                if attr != fail_attr:
                    self.assertEqual(entry.get(attr), val)
            self.assertEqual(entry.get("current_mtime"), str(mtime))

        # failure mode for mtime
        fail_mtime = 1344431162
        entry = reset()
        entry.set("mtime", str(mtime))
        fail_stat_rv = MagicMock()
        fail_stat_rv.__getitem__.return_value = fail_mtime
        gather_data_rv = [fail_stat_rv, None, None, None, None, []]
        for attr, idx, val in expected:
            gather_data_rv[idx] = val
        ptool._gather_data.return_value = tuple(gather_data_rv)
        self.assertFalse(ptool._verify_metadata(entry))
        ptool._gather_data.assert_called_with(entry.get("name"))
        ptool._verify_acls.assert_called_with(entry, path=entry.get("name"))
        self.assertEqual(entry.get("current_exists", 'true'), 'true')
        for attr, idx, val in expected:
            self.assertEqual(entry.get(attr), val)
        self.assertEqual(entry.get("current_mtime"), str(fail_mtime))

        if HAS_SELINUX:
            # test success and failure for __default__ secontext
            entry = reset()
            entry.set("mtime", str(mtime))
            entry.set("secontext", "__default__")

            context1 = "system_u:object_r:etc_t:s0"
            context2 = "system_u:object_r:root_t:s0"
            mock_matchpathcon.return_value = [1 + len(context1),
                                              context1]
            gather_data_rv = [stat_rv, None, None, None, None, []]
            for attr, idx, val in expected:
                gather_data_rv[idx] = val
            ptool._gather_data.return_value = tuple(gather_data_rv)
            self.assertTrue(ptool._verify_metadata(entry))
            ptool._gather_data.assert_called_with(entry.get("name"))
            ptool._verify_acls.assert_called_with(entry,
                                                path=entry.get("name"))
            mock_matchpathcon.assert_called_with(entry.get("name"), stat_mode)
            self.assertEqual(entry.get("current_exists", 'true'), 'true')
            for attr, idx, val in expected:
                self.assertEqual(entry.get(attr), val)
            self.assertEqual(entry.get("current_mtime"), str(mtime))

            entry = reset()
            entry.set("mtime", str(mtime))
            entry.set("secontext", "__default__")
            mock_matchpathcon.return_value = [1 + len(context2),
                                              context2]
            self.assertFalse(ptool._verify_metadata(entry))
            ptool._gather_data.assert_called_with(entry.get("name"))
            ptool._verify_acls.assert_called_with(entry,
                                                path=entry.get("name"))
            mock_matchpathcon.assert_called_with(entry.get("name"), stat_mode)
            self.assertEqual(entry.get("current_exists", 'true'), 'true')
            for attr, idx, val in expected:
                self.assertEqual(entry.get(attr), val)
            self.assertEqual(entry.get("current_mtime"), str(mtime))

    @skipUnless(HAS_ACLS, "ACLS not found, skipping")
    def test_list_entry_acls(self):
        ptool = self.get_obj()
        entry = lxml.etree.Element("Path", name="/test", type="file")
        lxml.etree.SubElement(entry, "ACL", scope="user", type="default",
                              user="user", perms="rwx")
        lxml.etree.SubElement(entry, "ACL", scope="group", type="access",
                              group="group", perms="5")
        self.assertItemsEqual(ptool._list_entry_acls(entry),
                              {("default", posix1e.ACL_USER, "user"): 7,
                               ("access", posix1e.ACL_GROUP, "group"): 5})

    @skipUnless(HAS_ACLS, "ACLS not found, skipping")
    @patchIf(HAS_ACLS, "posix1e.ACL")
    @patch("pwd.getpwuid")
    @patch("grp.getgrgid")
    @patch("os.path.isdir")
    def test_list_file_acls(self, mock_isdir, mock_getgrgid, mock_getpwuid,
                            mock_ACL):
        ptool = self.get_obj()
        path = '/test'

        # build a set of file ACLs to return from posix1e.ACL(file=...)
        file_acls = []
        acl = Mock()
        acl.tag_type = posix1e.ACL_USER
        acl.qualifier = 10
        # yes, this is a bogus permset.  thanks to _norm_acl_perms
        # it works and is easier than many of the alternatives.
        acl.permset = 'rwx'
        file_acls.append(acl)
        acl = Mock()
        acl.tag_type = posix1e.ACL_GROUP
        acl.qualifier = 100
        acl.permset = 'rx'
        file_acls.append(acl)
        acl = Mock()
        acl.tag_type = posix1e.ACL_MASK
        file_acls.append(acl)
        acls = {("access", posix1e.ACL_USER, "user"): 7,
                ("access", posix1e.ACL_GROUP, "group"): 5}

        # set up the unreasonably complex return value for
        # posix1e.ACL(), which has two separate uses
        fileacl_rv = MagicMock()
        fileacl_rv.valid.return_value = True
        fileacl_rv.__iter__.return_value = iter(file_acls)
        filedef_rv = MagicMock()
        filedef_rv.valid.return_value = True
        filedef_rv.__iter__.return_value = iter(file_acls)
        def mock_acl_rv(file=None, filedef=None):
            if file:
                return fileacl_rv
            elif filedef:
                return filedef_rv
        # other return values
        mock_isdir.return_value = False
        mock_getgrgid.return_value = ("group", "x", 5, [])
        mock_getpwuid.return_value = ("user", "x", 5, 5, "User",
                                      "/home/user", "/bin/zsh")

        def reset():
            mock_isdir.reset_mock()
            mock_getgrgid.reset_mock()
            mock_getpwuid.reset_mock()
            mock_ACL.reset_mock()

        mock_ACL.side_effect = IOError(95, "Operation not supported")
        self.assertItemsEqual(ptool._list_file_acls(path), dict())

        reset()
        mock_ACL.side_effect = IOError
        self.assertItemsEqual(ptool._list_file_acls(path), dict())

        reset()
        mock_ACL.side_effect = mock_acl_rv
        self.assertItemsEqual(ptool._list_file_acls(path), acls)
        mock_isdir.assert_called_with(path)
        mock_getgrgid.assert_called_with(100)
        mock_getpwuid.assert_called_with(10)
        mock_ACL.assert_called_with(file=path)

        reset()
        mock_isdir.return_value = True
        fileacl_rv.__iter__.return_value = iter(file_acls)
        filedef_rv.__iter__.return_value = iter(file_acls)

        defacls = acls
        for akey, perms in list(acls.items()):
            defacls[('default', akey[1], akey[2])] = perms
        self.assertItemsEqual(ptool._list_file_acls(path), defacls)
        mock_isdir.assert_called_with(path)
        self.assertItemsEqual(mock_getgrgid.call_args_list,
                              [call(100), call(100)])
        self.assertItemsEqual(mock_getpwuid.call_args_list,
                              [call(10), call(10)])
        self.assertItemsEqual(mock_ACL.call_args_list,
                              [call(file=path), call(filedef=path)])

    @skipUnless(HAS_ACLS, "ACLS not found, skipping")
    def test_verify_acls(self):
        ptool = self.get_obj()
        ptool._list_file_acls = Mock()
        ptool._list_entry_acls = Mock()
        entry = lxml.etree.Element("Path", name="/test", type="file")
        # we can't test to make sure that errors get properly sorted
        # into (missing, extra, wrong) without refactoring the
        # _verify_acls code, and I don't feel like doing that, so eff
        # it.  let's just test to make sure that failures are
        # identified at all for now.

        acls = {("access", posix1e.ACL_USER, "user"): 7,
                ("default", posix1e.ACL_GROUP, "group"): 5}
        extra_acls = copy.deepcopy(acls)
        extra_acls[("access", posix1e.ACL_USER, "user2")] = 4

        ptool._list_entry_acls.return_value = acls
        ptool._list_file_acls.return_value = acls
        self.assertTrue(ptool._verify_acls(entry))
        ptool._list_entry_acls.assert_called_with(entry)
        ptool._list_file_acls.assert_called_with(entry.get("name"))

        # test missing
        ptool._list_entry_acls.reset_mock()
        ptool._list_file_acls.reset_mock()
        ptool._list_file_acls.return_value = extra_acls
        self.assertFalse(ptool._verify_acls(entry))
        ptool._list_entry_acls.assert_called_with(entry)
        ptool._list_file_acls.assert_called_with(entry.get("name"))

        # test extra
        ptool._list_entry_acls.reset_mock()
        ptool._list_file_acls.reset_mock()
        ptool._list_entry_acls.return_value = extra_acls
        ptool._list_file_acls.return_value = acls
        self.assertFalse(ptool._verify_acls(entry))
        ptool._list_entry_acls.assert_called_with(entry)
        ptool._list_file_acls.assert_called_with(entry.get("name"))

        # test wrong
        wrong_acls = copy.deepcopy(extra_acls)
        wrong_acls[("access", posix1e.ACL_USER, "user2")] = 5
        ptool._list_entry_acls.reset_mock()
        ptool._list_file_acls.reset_mock()
        ptool._list_entry_acls.return_value = extra_acls
        ptool._list_file_acls.return_value = wrong_acls
        self.assertFalse(ptool._verify_acls(entry))
        ptool._list_entry_acls.assert_called_with(entry)
        ptool._list_file_acls.assert_called_with(entry.get("name"))

    @patch("os.makedirs")
    @patch("os.path.exists")
    def test_makedirs(self, mock_exists, mock_makedirs):
        ptool = self.get_obj()
        ptool._set_perms = Mock()
        entry = lxml.etree.Element("Path", name="/test/foo/bar",
                                   type="directory", mode="0644")
        parent_entry = lxml.etree.Element("Path", name="/test/foo/bar",
                                          type="directory", mode="0755")

        def reset():
            mock_exists.reset_mock()
            ptool._set_perms.reset_mock()
            mock_makedirs.reset_mock()

        ptool._set_perms.return_value = True
        def path_exists_rv(path):
            if path == "/test":
                return True
            else:
                return False
        mock_exists.side_effect = path_exists_rv
        self.assertTrue(ptool._makedirs(entry))
        self.assertItemsEqual(mock_exists.call_args_list,
                              [call("/test"), call("/test/foo"),
                               call("/test/foo/bar")])
        for args in ptool._set_perms.call_args_list:
            self.assertXMLEqual(args[0][0], parent_entry)
        self.assertItemsEqual([a[1] for a in ptool._set_perms.call_args_list],
                              [dict(path="/test/foo"),
                               dict(path="/test/foo/bar")])
        mock_makedirs.assert_called_with(entry.get("name"))

        reset()
        mock_makedirs.side_effect = OSError
        self.assertFalse(ptool._makedirs(entry))
        for args in ptool._set_perms.call_args_list:
            self.assertXMLEqual(args[0][0], parent_entry)
        self.assertItemsEqual([a[1] for a in ptool._set_perms.call_args_list],
                              [dict(path="/test/foo"),
                               dict(path="/test/foo/bar")])

        reset()
        mock_makedirs.side_effect = None
        def set_perms_rv(entry, path=None):
            if path == '/test/foo':
                return False
            else:
                return True
        ptool._set_perms.side_effect = set_perms_rv
        self.assertTrue(ptool._makedirs(entry))
        self.assertItemsEqual(mock_exists.call_args_list,
                              [call("/test"), call("/test/foo"),
                               call("/test/foo/bar")])
        for args in ptool._set_perms.call_args_list:
            self.assertXMLEqual(args[0][0], parent_entry)
        self.assertItemsEqual([a[1] for a in ptool._set_perms.call_args_list],
                              [dict(path="/test/foo"),
                               dict(path="/test/foo/bar")])
        mock_makedirs.assert_called_with(entry.get("name"))


class TestPOSIXLinkTool(TestPOSIXTool):
    test_obj = POSIXLinkTool

    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    def test_verify(self, mock_verify):
        entry = lxml.etree.Element("Path", name="/test", type="testlink",
                                   to="/dest")
        ptool = self.get_obj()
        linktype = ptool.__linktype__
        ptool.__linktype__ = "test"
        ptool._verify = Mock()

        ptool._verify.return_value = True
        mock_verify.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        ptool._verify.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])

        ptool._verify.reset_mock()
        mock_verify.reset_mock()
        mock_verify.return_value = True
        self.assertTrue(ptool.verify(entry, []))
        ptool._verify.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])

        ptool._verify.reset_mock()
        mock_verify.reset_mock()
        ptool._verify.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        ptool._verify.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])

        ptool._verify.reset_mock()
        mock_verify.reset_mock()
        ptool._verify.side_effect = OSError
        self.assertFalse(ptool.verify(entry, []))
        ptool._verify.assert_called_with(entry)
        ptool.__linktype__ = linktype

    def test__verify(self):
        ptool = self.get_obj()
        self.assertRaises(NotImplementedError, ptool._verify, Mock())

    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    def test_install(self, mock_install):
        entry = lxml.etree.Element("Path", name="/test", type="symlink",
                                   to="/dest")
        ptool = self.get_obj()
        linktype = ptool.__linktype__
        ptool.__linktype__ = "test"
        ptool._exists = Mock()
        ptool._link = Mock()

        ptool._exists.return_value = False
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        ptool._exists.assert_called_with(entry, remove=True)
        ptool._link.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)

        ptool._link.reset_mock()
        ptool._exists.reset_mock()
        mock_install.reset_mock()
        ptool._link.side_effect = OSError
        self.assertFalse(ptool.install(entry))
        ptool._exists.assert_called_with(entry, remove=True)
        ptool._link.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)
        ptool.__linktype__ = linktype

    def test__link(self):
        ptool = self.get_obj()
        self.assertRaises(NotImplementedError, ptool._link, Mock())
