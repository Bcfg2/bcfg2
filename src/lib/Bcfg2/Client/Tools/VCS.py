"""VCS support."""

# TODO:
#   * git_write_index
#   * add svn support
#   * integrate properly with reports
missing = []

import os
import shutil
import sys
# python-dulwich git imports
try:
    import dulwich
    import dulwich.index
    from dulwich.errors import NotGitRepository
except:
    missing.append('git')
# subversion import
try:
    import pysvn
except:
    missing.append('svn')

import Bcfg2.Client.Tools


class VCS(Bcfg2.Client.Tools.Tool):
    """VCS support."""
    name = 'VCS'
    __handles__ = [('Path', 'vcs')]
    __req__ = {'Path': ['name',
                        'type',
                        'vcstype',
                        'sourceurl',
                        'revision']}

    def __init__(self, logger, cfg, setup):
        Bcfg2.Client.Tools.Tool.__init__(self, logger, cfg, setup)
        self.cfg = cfg

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
        cur_rev = repo.head()

        if cur_rev != entry.get('revision'):
            self.logger.info("At revision %s need to go to revision %s" %
                             (cur_rev, entry.get('revision')))
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
                self.logger.info('Failed to remove %s' % \
                                 destname)
                return False

        destr = dulwich.repo.Repo.init(destname, mkdir=True)
        cl, host_path = dulwich.client.get_transport_and_path(entry.get('sourceurl'))
        remote_refs = cl.fetch(host_path,
                               destr,
                               determine_wants=destr.object_store.determine_wants_all,
                               progress=sys.stdout.write)
        destr.refs['refs/heads/master'] = entry.get('revision')
        dtree = destr[entry.get('revision')].tree
        obj_store = destr.object_store
        for fname, mode, sha in obj_store.iter_tree_contents(dtree):
            fullpath = os.path.join(destname, fname)
            try:
                f = open(os.path.join(destname, fname), 'wb')
            except IOError:
                dir = os.path.split(fullpath)[0]
                os.makedirs(dir)
                f = open(os.path.join(destname, fname), 'wb')
            f.write(destr[sha].data)
            f.close()
            os.chmod(os.path.join(destname, fname), mode)
        return True
        # FIXME: figure out how to write the git index properly
        #iname = "%s/.git/index" % entry.get('name')
        #f = open(iname, 'w+')
        #entries = obj_store[sha].iteritems()
        #try:
        #    dulwich.index.write_index(f, entries)
        #finally:
        #    f.close()

    def Verifysvn(self, entry, _):
        """Verify svn repositories"""
        client = pysvn.Client()
        try:
            cur_rev = str(client.info(entry.get('name')).revision.number)
        except:
            self.logger.info("Repository %s does not exist" % entry.get('name'))
            return False

        if cur_rev != entry.get('revision'):
            self.logger.info("At revision %s need to go to revision %s" %
                             (cur_rev, entry.get('revision')))
            return False

        return True

    def Installsvn(self, entry):
        """Checkout contents from a svn repository"""
        try:
            client = pysvn.Client.update(entry.get('name'), recurse=True)
        except:
            self.logger.error("Failed to update repository", exc_info=1)
            return False

        return True

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
