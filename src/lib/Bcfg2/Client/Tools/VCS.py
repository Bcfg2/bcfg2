"""VCS support."""

# TODO:
#   * add svn support
#   * integrate properly with reports
missing = []

import errno
import os
import shutil
import sys
import stat

# python-dulwich git imports
try:
    import dulwich
    import dulwich.index
    from dulwich.errors import NotGitRepository
except ImportError:
    missing.append('git')
# subversion import
try:
    import pysvn
except ImportError:
    missing.append('svn')

import Bcfg2.Client.Tools


def cleanup_mode(mode):
    """Cleanup a mode value.

    This will return a mode that can be stored in a tree object.

    :param mode: Mode to clean up.
    """
    if stat.S_ISLNK(mode):
        return stat.S_IFLNK
    elif stat.S_ISDIR(mode):
        return stat.S_IFDIR
    elif dulwich.index.S_ISGITLINK(mode):
        return dulwich.index.S_IFGITLINK
    ret = stat.S_IFREG | int('644', 8)
    ret |= (mode & int('111', 8))
    return ret


def index_entry_from_stat(stat_val, hex_sha, flags, mode=None):
    """Create a new index entry from a stat value.

    :param stat_val: POSIX stat_result instance
    :param hex_sha: Hex sha of the object
    :param flags: Index flags
    """
    if mode is None:
        mode = cleanup_mode(stat_val.st_mode)
    return (stat_val.st_ctime, stat_val.st_mtime, stat_val.st_dev,
            stat_val.st_ino, mode, stat_val.st_uid,
            stat_val.st_gid, stat_val.st_size, hex_sha, flags)


class VCS(Bcfg2.Client.Tools.Tool):
    """VCS support."""
    __handles__ = [('Path', 'vcs')]
    __req__ = {'Path': ['name',
                        'type',
                        'vcstype',
                        'sourceurl',
                        'revision']}

    def git_write_index(self, entry):
        """Write the git index"""
        pass

    def Verifygit(self, entry, _):
        """Verify git repositories"""
        try:
            repo = dulwich.repo.Repo(entry.get('name'))
        except NotGitRepository:
            self.logger.info("Repository %s does not exist" %
                             entry.get('name'))
            return False

        try:
            expected_rev = entry.get('revision')
            cur_rev = repo.head()
        except:
            return False

        try:
            client, path = dulwich.client.get_transport_and_path(entry.get('sourceurl'))
            remote_refs = client.fetch_pack(path, (lambda x: None), None, None, None)
            if expected_rev in remote_refs:
                expected_rev = remote_refs[expected_rev]
        except:
            pass

        if cur_rev != expected_rev:
            self.logger.info("At revision %s need to go to revision %s" %
                             (cur_rev.strip(), expected_rev.strip()))
            return False

        return True

    def Installgit(self, entry):
        """Checkout contents from a git repository"""
        destname = entry.get('name')
        if os.path.lexists(destname):
            # remove incorrect contents
            try:
                if os.path.isdir(destname):
                    shutil.rmtree(destname)
                else:
                    os.remove(destname)
            except OSError:
                self.logger.info('Failed to remove %s' %
                                 destname)
                return False

        dulwich.file.ensure_dir_exists(destname)
        destr = dulwich.repo.Repo.init(destname)
        cl, host_path = dulwich.client.get_transport_and_path(entry.get('sourceurl'))
        remote_refs = cl.fetch(host_path,
                               destr,
                               determine_wants=destr.object_store.determine_wants_all,
                               progress=sys.stdout.write)

        if entry.get('revision') in remote_refs:
            destr.refs['HEAD'] = remote_refs[entry.get('revision')]
        else:
            destr.refs['HEAD'] = entry.get('revision')

        dtree = destr['HEAD'].tree
        index = dulwich.index.Index(destr.index_path())
        for fname, mode, sha in destr.object_store.iter_tree_contents(dtree):
            full_path = os.path.join(destname, fname)
            dulwich.file.ensure_dir_exists(os.path.dirname(full_path))

            if stat.S_ISLNK(mode):
                src_path = destr[sha].as_raw_string()
                try:
                    os.symlink(src_path, full_path)
                except OSError:
                    e = sys.exc_info()[1]
                    if e.errno == errno.EEXIST:
                        os.unlink(full_path)
                        os.symlink(src_path, full_path)
                    else:
                        raise
            else:
                file = open(full_path, 'wb')
                file.write(destr[sha].as_raw_string())
                file.close()
                os.chmod(full_path, mode)

            st = os.lstat(full_path)
            index[fname] = index_entry_from_stat(st, sha, 0)

        index.write()
        return True

    def Verifysvn(self, entry, _):
        """Verify svn repositories"""
        headrev = pysvn.Revision( pysvn.opt_revision_kind.head )
        client = pysvn.Client()
        try:
            cur_rev = str(client.info(entry.get('name')).revision.number)
            server = client.info2(entry.get('sourceurl'), headrev, recurse=False)
            if server:
                server_rev = str(server[0][1].rev.number)
        except:
            self.logger.info("Repository %s does not exist" % entry.get('name'))
            return False

        if entry.get('revision') == 'latest' and cur_rev == server_rev:
            return True

        if cur_rev != entry.get('revision'):
            self.logger.info("At revision %s need to go to revision %s" %
                             (cur_rev, entry.get('revision')))
            return False

        return True

    def Installsvn(self, entry):
        """Checkout contents from a svn repository"""
        # pylint: disable=E1101
        client = pysvn.Client()
        try:
            client.update(entry.get('name'), recurse=True)
        except pysvn.ClientError:
            self.logger.error("Failed to update repository", exc_info=1)
            return False
        return True
        # pylint: enable=E1101

    def VerifyPath(self, entry, _):
        vcs = entry.get('vcstype')
        if vcs in missing:
            self.logger.error("Missing %s python libraries. Cannot verify" %
                              vcs)
            return False
        ret = getattr(self, 'Verify%s' % vcs)
        return ret(entry, _)

    def InstallPath(self, entry):
        vcs = entry.get('vcstype')
        if vcs in missing:
            self.logger.error("Missing %s python libraries. "
                              "Unable to install" % vcs)
            return False
        ret = getattr(self, 'Install%s' % vcs)
        return ret(entry)
