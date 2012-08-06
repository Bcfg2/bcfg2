"""All POSIX Type client support for Bcfg2."""

import binascii
from datetime import datetime
import difflib
import errno
import grp
import logging
import os
import pwd
import shutil
import stat
import sys
import time
# py3k compatibility
if sys.hexversion >= 0x03000000:
    unicode = str

import Bcfg2.Client.Tools
import Bcfg2.Options
from Bcfg2.Client import XML

log = logging.getLogger(__name__)

try:
    import selinux
    has_selinux = True
except ImportError:
    has_selinux = False

try:
    import posix1e
    has_acls = True
except ImportError:
    has_acls = False


# map between dev_type attribute and stat constants
device_map = {'block': stat.S_IFBLK,
              'char': stat.S_IFCHR,
              'fifo': stat.S_IFIFO}

# map between permissions characters and numeric ACL constants
acl_map = dict(r=posix1e.ACL_READ,
               w=posix1e.ACL_WRITE,
               x=posix1e.ACL_EXECUTE)


class POSIX(Bcfg2.Client.Tools.Tool):
    """POSIX File support code."""
    name = 'POSIX'
    __handles__ = [('Path', 'device'),
                   ('Path', 'directory'),
                   ('Path', 'file'),
                   ('Path', 'hardlink'),
                   ('Path', 'nonexistent'),
                   ('Path', 'permissions'),
                   ('Path', 'symlink')]
    __req__ = dict(Path=dict(
            device=['name', 'dev_type', 'perms', 'owner', 'group'],
            directory=['name', 'perms', 'owner', 'group'],
            file=['name', 'perms', 'owner', 'group'],
            hardlink=['name', 'to'],
            nonexistent=['name'],
            permissions=['name', 'perms', 'owner', 'group'],
            symlink=['name', 'to']))

    # grab paranoid options from /etc/bcfg2.conf
    opts = {'ppath': Bcfg2.Options.PARANOID_PATH,
            'max_copies': Bcfg2.Options.PARANOID_MAX_COPIES}
    setup = Bcfg2.Options.OptionParser(opts)
    setup.parse([])
    ppath = setup['ppath']
    max_copies = setup['max_copies']

    def canInstall(self, entry):
        """Check if entry is complete for installation."""
        if Bcfg2.Client.Tools.Tool.canInstall(self, entry):
            if (entry.get('type') == 'file' and
                entry.text is None and
                entry.get('empty', 'false') == 'false'):
                return False
            return True
        else:
            return False

    def gatherCurrentData(self, entry):
        if entry.tag == 'Path' and entry.get('type') == 'file':
            try:
                ondisk = os.stat(entry.get('name'))
            except OSError:
                entry.set('current_exists', 'false')
                self.logger.debug("%s %s does not exist" %
                                  (entry.tag, entry.get('name')))
                return False
            try:
                entry.set('current_owner', str(ondisk[stat.ST_UID]))
                entry.set('current_group', str(ondisk[stat.ST_GID]))
            except (OSError, KeyError):
                pass

            if has_selinux:
                try:
                    entry.set('current_secontext',
                              selinux.getfilecon(entry.get('name'))[1])
                except (OSError, KeyError):
                    pass
            entry.set('perms', str(oct(ondisk[stat.ST_MODE])[-4:]))

    def _set_perms(self, entry, path=None):
        if path is None:
            path = entry.get("name")

        if (entry.get('perms') == None or
            entry.get('owner') == None or
            entry.get('group') == None):
            self.logger.error('Entry %s not completely specified. '
                              'Try running bcfg2-lint.' % entry.get('name'))
            return False

        rv = True
        # split this into multiple try...except blocks so that even if a
        # chown fails, the chmod can succeed -- get as close to the
        # desired state as we can
        try:
            self.logger.debug("Setting ownership of %s to %s:%s" %
                              (path,
                               self._norm_entry_uid(entry),
                               self._norm_entry_gid(entry)))
            os.chown(path, self._norm_entry_uid(entry),
                     self._norm_entry_gid(entry))
        except KeyError:
            self.logger.error('Failed to change ownership of %s' % path)
            rv = False
            os.chown(path, 0, 0)
        except OSError:
            self.logger.error('Failed to change ownership of %s' % path)
            rv = False

        configPerms = int(entry.get('perms'), 8)
        if entry.get('dev_type'):
            configPerms |= device_map[entry.get('dev_type')]
        try:
            self.logger.debug("Setting permissions on %s to %s" %
                              (path, oct(configPerms)))
            os.chmod(path, configPerms)
        except (OSError, KeyError):
            self.logger.error('Failed to change permissions mode of %s' % path)
            rv = False

        recursive = entry.get("recursive", "false").lower() == "true"
        return (self._set_secontext(entry, path=path, recursive=recursive) and
                self._set_acls(entry, path=path, recursive=recursive) and
                rv)

    def _set_acls(self, entry, path=None, recursive=True):
        """ set POSIX ACLs on the file on disk according to the config """
        if not has_acls:
            if entry.findall("ACL"):
                self.logger.debug("ACLs listed for %s but no pylibacl library "
                                  "installed" % entry.get('name'))
            return True

        if path is None:
            path = entry.get("name")

        acl = posix1e.ACL(file=path)
        # clear ACLs out so we start fresh -- way easier than trying
        # to add/remove/modify ACLs
        for aclentry in acl:
            if aclentry.tag_type in [posix1e.ACL_USER, posix1e.ACL_GROUP]:
                acl.delete_entry(aclentry)
        if os.path.isdir(path):
            defacl = posix1e.ACL(filedef=path)
            if not defacl.valid():
                # when a default ACL is queried on a directory that
                # has no default ACL entries at all, you get an empty
                # ACL, which is not valid.  in this circumstance, we
                # just copy the access ACL to get a base valid ACL
                # that we can add things to.
                defacl = posix1e.ACL(acl=acl)
            else:
                for aclentry in defacl:
                    if aclentry.tag_type in [posix1e.ACL_USER,
                                             posix1e.ACL_GROUP]:
                        defacl.delete_entry(aclentry)
        else:
            defacl = None

        for aclkey, perms in self._list_entry_acls(entry).items():
            atype, scope, qualifier = aclkey
            if atype == "default":
                if defacl is None:
                    self.logger.warning("Cannot set default ACLs on "
                                        "non-directory %s" % path)
                    continue
                entry = posix1e.Entry(defacl)
            else:
                entry = posix1e.Entry(acl)
            for perm in acl_map.values():
                if perm & perms:
                    entry.permset.add(perm)
            entry.tag_type = scope
            try:
                if scope == posix1e.ACL_USER:
                    scopename = "user"
                    entry.qualifier = self._norm_uid(qualifier)
                elif scope == posix1e.ACL_GROUP:
                    scopename = "group"
                    entry.qualifier = self._norm_gid(qualifier)
            except (OSError, KeyError):
                err = sys.exc_info()[1]
                self.logger.error("Could not resolve %s %s: %s" %
                                  (scopename, qualifier, err))
                continue
        acl.calc_mask()

        def _apply_acl(acl, path, atype=posix1e.ACL_TYPE_ACCESS):
            if atype == posix1e.ACL_TYPE_ACCESS:
                atype_str = "access"
            else:
                atype_str = "default"
            if acl.valid():
                self.logger.debug("Applying %s ACL to %s:" % (atype_str, path))
                for line in str(acl).splitlines():
                    self.logger.debug("  " + line)
                try:
                    acl.applyto(path, atype)
                    return True
                except:
                    err = sys.exc_info()[1]
                    self.logger.error("Failed to set ACLs on %s: %s" %
                                      (path, err))
                    return False
            else:
                self.logger.warning("%s ACL created for %s was invalid:" % 
                                    (atype_str.title(), path))
                for line in str(acl).splitlines():
                    self.logger.warning("  " + line)
                return False

        rv = _apply_acl(acl, path)
        if defacl:
            defacl.calc_mask()
            rv &= _apply_acl(defacl, path, posix1e.ACL_TYPE_DEFAULT)
        if recursive:
            for root, dirs, files in os.walk(path):
                for p in dirs + files:
                    rv &= _apply_acl(acl, p)
                    if defacl:
                        rv &= _apply_acl(defacl, p, posix1e.ACL_TYPE_DEFAULT)
        return rv

    def _set_secontext(self, entry, path=None, recursive=False):
        """ set the SELinux context of the file on disk according to the
        config"""
        if not has_selinux:
            return True

        if path is None:
            path = entry.get("name")
        context = entry.get("secontext")
        if context is None:
            # no context listed
            return True

        rv = True
        if context == '__default__':
            try:
                selinux.restorecon(path, recursive=recursive)
            except:
                err = sys.exc_info()[1]
                self.logger.error("Failed to restore SELinux context for %s: %s"
                                  % (path, err))
                rv = False
        else:
            try:
                rv &= selinux.lsetfilecon(path, context) == 0
            except:
                err = sys.exc_info()[1]
                self.logger.error("Failed to restore SELinux context for %s: %s"
                                  % (path, err))
                rv = False

            if recursive:
                for root, dirs, files in os.walk(path):
                    for p in dirs + files:
                        try:
                            rv &= selinux.lsetfilecon(p, context) == 0
                        except:
                            err = sys.exc_info()[1]
                            self.logger.error("Failed to restore SELinux "
                                              "context for %s: %s" %
                                              (path, err))
                            rv = False
        return rv

    def _secontext_matches(self, entry):
        """ determine if the SELinux context of the file on disk matches
        the desired context """
        if not has_selinux:
            # no selinux libraries
            return True

        path = entry.get("path")
        context = entry.get("secontext")
        if context is None:
            # no context listed
            return True

        if context == '__default__':
            if selinux.getfilecon(entry.get('name'))[1] == \
               selinux.matchpathcon(entry.get('name'), 0)[1]:
                return True
            else:
                return False
        elif selinux.getfilecon(entry.get('name'))[1] == context:
            return True
        else:
            return False

    def _norm_gid(self, gid):
        """ This takes a group name or gid and returns the
        corresponding gid. """
        try:
            return int(gid)
        except ValueError:
            return int(grp.getgrnam(gid)[2])

    def _norm_entry_gid(self, entry):
        try:
            return self._norm_gid(entry.get('group'))
        except (OSError, KeyError):
            err = sys.exc_info()[1]
            self.logger.error('GID normalization failed for %s on %s: %s' %
                              (entry.get('group'), entry.get('name'), err))
            return False

    def _norm_uid(self, uid):
        """ This takes a username or uid and returns the
        corresponding uid. """
        try:
            return int(uid)
        except ValueError:
            return int(pwd.getpwnam(uid)[2])

    def _norm_entry_uid(self, entry):
        try:
            return self._norm_uid(entry.get("owner"))
        except (OSError, KeyError):
            err = sys.exc_info()[1]
            self.logger.error('UID normalization failed for %s on %s: %s' %
                              (entry.get('owner'), entry.get('name'), err))
            return False

    def _norm_acl_perms(self, perms):
        """ takes a representation of an ACL permset and returns a digit
        representing the permissions entailed by it.  representations can
        either be a single octal digit, a string of up to three 'r',
        'w', 'x', or '-' characters, or a posix1e.Permset object"""
        if hasattr(perms, 'test'):
            # Permset object
            return sum([p for p in acl_map.values()
                        if perms.test(p)])

        try:
            # single octal digit
            return int(perms)
        except ValueError:
            # couldn't be converted to an int; process as a string
            rv = 0
            for char in perms:
                if char == '-':
                    continue
                elif char not in acl_map:
                    self.logger.error("Unknown permissions character in ACL: %s"
                                      % char)
                    return 0
                else:
                    rv |= acl_map[char]
            return rv

    def _acl2string(self, aclkey, perms):
        atype, scope, qualifier = aclkey
        acl_str = []
        if atype == 'default':
            acl_str.append(atype)
        if scope == posix1e.ACL_USER:
            acl_str.append("user")
        elif scope == posix1e.ACL_GROUP:
            acl_str.append("group")
        acl_str.append(qualifier)
        acl_str.append(self._acl_perm2string(perms))
        return ":".join(acl_str)

    def _acl_perm2string(self, perm):
        rv = []
        for char in 'rwx':
            if acl_map[char] & perm:
                rv.append(char)
            else:
                rv.append('-')
        return ''.join(rv)

    def _is_string(self, strng, encoding):
        """ Returns true if the string contains no ASCII control
        characters and can be decoded from the specified encoding. """
        for char in strng:
            if ord(char) < 9 or ord(char) > 13 and ord(char) < 32:
                return False
        try:
            strng.decode(encoding)
            return True
        except:
            return False

    def Verifydevice(self, entry, _):
        """Verify device entry."""
        if entry.get('dev_type') in ['block', 'char']:
            # check if major/minor are properly specified
            if (entry.get('major') == None or
                entry.get('minor') == None):
                self.logger.error('Entry %s not completely specified. '
                                  'Try running bcfg2-lint.' %
                                  (entry.get('name')))
                return False

        try:
            ondisk = os.stat(path)
        except OSError:
            entry.set('current_exists', 'false')
            self.logger.debug("%s %s does not exist" %
                              (entry.tag, path))
            return False

        rv = self._verify_metadata(entry)
        
        # attempt to verify device properties as specified in config
        dev_type = entry.get('dev_type')
        if dev_type in ['block', 'char']:
            major = int(entry.get('major'))
            minor = int(entry.get('minor'))
            if major != os.major(ondisk.st_rdev):
                entry.set('current_mtime', mtime)
                msg = ("Major number for device %s is incorrect. "
                       "Current major is %s but should be %s" %
                       (path, os.major(ondisk.st_rdev), major))
                self.logger.debug(msg)
                entry.set('qtext', entry.get('qtext') + "\n" + msg)
                rv = False

            if minor != os.minor(ondisk.st_rdev):
                entry.set('current_mtime', mtime)
                msg = ("Minor number for device %s is incorrect. "
                       "Current minor is %s but should be %s" %
                       (path, os.minor(ondisk.st_rdev), minor))
                self.logger.debug(msg)
                entry.set('qtext', entry.get('qtext') + "\n" + msg)
                rv = False

        return rv

    def Installdevice(self, entry):
        """Install device entries."""
        try:
            # check for existing paths and remove them
            os.lstat(entry.get('name'))
            try:
                os.unlink(entry.get('name'))
                exists = False
            except OSError:
                self.logger.info('Failed to unlink %s' %
                                 entry.get('name'))
                return False
        except OSError:
            exists = False

        if not exists:
            try:
                dev_type = entry.get('dev_type')
                mode = device_map[dev_type] | int(entry.get('mode', '0600'), 8)
                if dev_type in ['block', 'char']:
                    # check if major/minor are properly specified
                    if (entry.get('major') == None or
                        entry.get('minor') == None):
                        self.logger.error('Entry %s not completely specified. '
                                          'Try running bcfg2-lint.' %
                                          entry.get('name'))
                        return False
                    major = int(entry.get('major'))
                    minor = int(entry.get('minor'))
                    device = os.makedev(major, minor)
                    os.mknod(entry.get('name'), mode, device)
                else:
                    os.mknod(entry.get('name'), mode)
                return self._set_perms(entry)
            except KeyError:
                self.logger.error('Failed to install %s' % entry.get('name'))
            except OSError:
                self.logger.error('Failed to install %s' % entry.get('name'))
                return False

    def Verifydirectory(self, entry, modlist):
        """Verify Path type='directory' entry."""
        pruneTrue = True
        ex_ents = []
        if (entry.get('prune', 'false') == 'true'
            and (entry.tag == 'Path' and entry.get('type') == 'directory')):
            # check for any extra entries when prune='true' attribute is set
            try:
                entries = ['/'.join([entry.get('name'), ent])
                           for ent in os.listdir(entry.get('name'))]
                ex_ents = [e for e in entries if e not in modlist]
                if ex_ents:
                    pruneTrue = False
                    self.logger.info("POSIX: Directory %s contains "
                                     "extra entries:" % entry.get('name'))
                    self.logger.info(ex_ents)
                    nqtext = entry.get('qtext', '') + '\n'
                    nqtext += "Directory %s contains extra entries: " % \
                              entry.get('name')
                    nqtext += ":".join(ex_ents)
                    entry.set('qtext', nqtext)
                    [entry.append(XML.Element('Prune', path=x))
                     for x in ex_ents]
            except OSError:
                ex_ents = []
                pruneTrue = True

        return pruneTrue and self._verify_metadata(entry)

    def Installdirectory(self, entry):
        """Install Path type='directory' entry."""
        self.logger.info("Installing directory %s" % entry.get('name'))
        try:
            fmode = os.lstat(entry.get('name'))
        except OSError:
            # stat failed
            exists = False

        if not stat.S_ISDIR(fmode[stat.ST_MODE]):
            self.logger.debug("Found a non-directory entry at %s" %
                              entry.get('name'))
            try:
                os.unlink(entry.get('name'))
                exists = False
            except OSError:
                self.logger.info("Failed to unlink %s" % entry.get('name'))
                return False
        else:
            self.logger.debug("Found a pre-existing directory at %s" %
                              entry.get('name'))
            exists = True

        if not exists:
            parent = "/".join(entry.get('name').split('/')[:-1])
            if parent:
                try:
                    os.stat(parent)
                except:
                    self.logger.debug('Creating parent path for directory %s' %
                                      entry.get('name'))
                    for idx in range(len(parent.split('/')[:-1])):
                        current = '/' + '/'.join(parent.split('/')[1:2+idx])
                        try:
                            sloc = os.stat(current)
                        except OSError:
                            try:
                                os.mkdir(current)
                                continue
                            except OSError:
                                return False
                        if not stat.S_ISDIR(sloc[stat.ST_MODE]):
                            try:
                                os.unlink(current)
                                os.mkdir(current)
                            except OSError:
                                return False

            try:
                os.mkdir(entry.get('name'))
            except OSError:
                self.logger.error('Failed to create directory %s' %
                                  entry.get('name'))
                return False
        if entry.get('prune', 'false') == 'true' and entry.get("qtext"):
            for pent in entry.findall('Prune'):
                pname = pent.get('path')
                ulfailed = False
                if os.path.isdir(pname):
                    self.logger.info("Not removing extra directory %s, "
                                     "please check and remove manually" % pname)
                    continue
                try:
                    self.logger.debug("Unlinking file %s" % pname)
                    os.unlink(pname)
                except OSError:
                    self.logger.error("Failed to unlink path %s" % pname)
                    ulfailed = True
            if ulfailed:
                return False
        return self.Installpermissions(entry)

    def Verifyfile(self, entry, _):
        """Verify Path type='file' entry."""
        # permissions check + content check
        permissionStatus = self._verify_metadata(entry)
        tbin = False
        if entry.text == None and entry.get('empty', 'false') == 'false':
            self.logger.error("Cannot verify incomplete Path type='%s' %s" %
                              (entry.get('type'), entry.get('name')))
            return False
        if entry.get('encoding', 'ascii') == 'base64':
            tempdata = binascii.a2b_base64(entry.text)
            tbin = True
        elif entry.get('empty', 'false') == 'true':
            tempdata = ''
        else:
            tempdata = entry.text
            if type(tempdata) == unicode:
                try:
                    tempdata = tempdata.encode(self.setup['encoding'])
                except UnicodeEncodeError:
                    e = sys.exc_info()[1]
                    self.logger.error("Error encoding file %s:\n %s" %
                                      (entry.get('name'), e))

        different = False
        content = None
        if not os.path.exists(entry.get("name")):
            # first, see if the target file exists at all; if not,
            # they're clearly different
            different = True
            content = ""
        else:
            # next, see if the size of the target file is different
            # from the size of the desired content
            try:
                estat = os.stat(entry.get('name'))
            except OSError:
                err = sys.exc_info()[1]
                self.logger.error("Failed to stat %s: %s" %
                                  (err.filename, err))
                return False
            if len(tempdata) != estat[stat.ST_SIZE]:
                different = True
            else:
                # finally, read in the target file and compare them
                # directly. comparison could be done with a checksum,
                # which might be faster for big binary files, but
                # slower for everything else
                try:
                    content = open(entry.get('name')).read()
                except IOError:
                    err = sys.exc_info()[1]
                    self.logger.error("Failed to read %s: %s" %
                                      (err.filename, err))
                    return False
                different = content != tempdata

        if different:
            if self.setup['interactive']:
                prompt = [entry.get('qtext', '')]
                if not tbin and content is None:
                    # it's possible that we figured out the files are
                    # different without reading in the local file.  if
                    # the supplied version of the file is not binary,
                    # we now have to read in the local file to figure
                    # out if _it_ is binary, and either include that
                    # fact or the diff in our prompts for -I
                    try:
                        content = open(entry.get('name')).read()
                    except IOError:
                        err = sys.exc_info()[1]
                        self.logger.error("Failed to read %s: %s" %
                                          (err.filename, err))
                        return False
                if tbin or not self._is_string(content, self.setup['encoding']):
                    # don't compute diffs if the file is binary
                    prompt.append('Binary file, no printable diff')
                else:
                    diff = self._diff(content, tempdata,
                                      difflib.unified_diff,
                                      filename=entry.get("name"))
                    if diff:
                        udiff = '\n'.join(diff)
                        try:
                            prompt.append(udiff.decode(self.setup['encoding']))
                        except UnicodeDecodeError:
                            prompt.append("Binary file, no printable diff")
                    else:
                        prompt.append("Diff took too long to compute, no "
                                      "printable diff")
                entry.set("qtext", "\n".join(prompt))

            if entry.get('sensitive', 'false').lower() != 'true':
                if content is None:
                    # it's possible that we figured out the files are
                    # different without reading in the local file.  we
                    # now have to read in the local file to figure out
                    # if _it_ is binary, and either include the whole
                    # file or the diff for reports
                    try:
                        content = open(entry.get('name')).read()
                    except IOError:
                        err = sys.exc_info()[1]
                        self.logger.error("Failed to read %s: %s" %
                                          (err.filename, err))
                        return False

                if tbin or not self._is_string(content, self.setup['encoding']):
                    # don't compute diffs if the file is binary
                    entry.set('current_bfile', binascii.b2a_base64(content))
                else:
                    diff = self._diff(content, tempdata, difflib.ndiff,
                                      filename=entry.get("name"))
                    if diff:
                        entry.set("current_bdiff",
                                  binascii.b2a_base64("\n".join(diff)))
                    elif not tbin and self._is_string(content,
                                                      self.setup['encoding']):
                        entry.set('current_bfile', binascii.b2a_base64(content))

        return permissionStatus and not different

    def Installfile(self, entry):
        """Install Path type='file' entry."""
        self.logger.info("Installing file %s" % (entry.get('name')))

        parent = "/".join(entry.get('name').split('/')[:-1])
        if parent:
            try:
                os.stat(parent)
            except:
                self.logger.debug('Creating parent path for config file %s' %
                                  entry.get('name'))
                current = '/'
                for next in parent.split('/')[1:]:
                    current += next + '/'
                    try:
                        sloc = os.stat(current)
                        try:
                            if not stat.S_ISDIR(sloc[stat.ST_MODE]):
                                self.logger.debug('%s is not a directory; recreating'
                                                  % current)
                                os.unlink(current)
                                os.mkdir(current)
                        except OSError:
                            return False
                    except OSError:
                        try:
                            self.logger.debug("Creating non-existent path %s" %
                                              current)
                            os.mkdir(current)
                        except OSError:
                            return False

        # If we get here, then the parent directory should exist
        if (entry.get("paranoid", 'false').lower() == 'true' and
            self.setup.get("paranoid", False) and
            entry.get('current_exists', 'true') != 'false'):
            bkupnam = entry.get('name').replace('/', '_')
            # current list of backups for this file
            try:
                bkuplist = [f for f in os.listdir(self.ppath) if
                            f.startswith(bkupnam)]
            except OSError:
                e = sys.exc_info()[1]
                self.logger.error("Failed to create backup list in %s: %s" %
                                  (self.ppath, e.strerror))
                return False
            bkuplist.sort()
            while len(bkuplist) >= int(self.max_copies):
                # remove the oldest backup available
                oldest = bkuplist.pop(0)
                self.logger.info("Removing %s" % oldest)
                try:
                    os.remove("%s/%s" % (self.ppath, oldest))
                except:
                    self.logger.error("Failed to remove %s/%s" %
                                      (self.ppath, oldest))
                    return False
            try:
                # backup existing file
                shutil.copy(entry.get('name'),
                            "%s/%s_%s" % (self.ppath, bkupnam,
                                          datetime.isoformat(datetime.now())))
                self.logger.info("Backup of %s saved to %s" %
                                 (entry.get('name'), self.ppath))
            except IOError:
                e = sys.exc_info()[1]
                self.logger.error("Failed to create backup file for %s" %
                                  entry.get('name'))
                self.logger.error(e)
                return False
        try:
            newfile = open("%s.new"%(entry.get('name')), 'w')
            if entry.get('encoding', 'ascii') == 'base64':
                filedata = binascii.a2b_base64(entry.text)
            elif entry.get('empty', 'false') == 'true':
                filedata = ''
            else:
                if type(entry.text) == unicode:
                    filedata = entry.text.encode(self.setup['encoding'])
                else:
                    filedata = entry.text
            newfile.write(filedata)
            newfile.close()

            rv = self._set_perms(entry, newfile.name)
            os.rename(newfile.name, entry.get('name'))
            if entry.get('mtime'):
                try:
                    os.utime(entry.get('name'), (int(entry.get('mtime')),
                                                 int(entry.get('mtime'))))
                except:
                    self.logger.error("Failed to set mtime of %s" % path)
                    rv = False
            return rv
        except (OSError, IOError):
            err = sys.exc_info()[1]
            self.logger.error("Failed to open %s for writing: %s" %
                              (entry.get('name'), err))
            return False

    def Verifyhardlink(self, entry, _):
        """Verify HardLink entry."""
        rv = True

        try:
            if not os.path.samefile(entry.get('name'), entry.get('to')):
                msg = "Hardlink %s is incorrect." % entry.get('name')
                self.logger.debug(msg)
                entry.set('qtext', "\n".join([entry.get('qtext', ''), msg]))
                rv = False
        except OSError:
            entry.set('current_exists', 'false')
            return False

        rv &= self._verify_secontext(entry)
        return rv

    def Installhardlink(self, entry):
        """Install HardLink entry."""
        self.logger.info("Installing Hardlink %s" % entry.get('name'))
        if os.path.lexists(entry.get('name')):
            try:
                fmode = os.lstat(entry.get('name'))[stat.ST_MODE]
                if stat.S_ISREG(fmode) or stat.S_ISLNK(fmode):
                    self.logger.debug("Non-directory entry already exists at "
                                      "%s. Unlinking entry." %
                                      entry.get('name'))
                    os.unlink(entry.get('name'))
                elif stat.S_ISDIR(fmode):
                    self.logger.debug("Directory already exists at %s" %
                                      entry.get('name'))
                    self.cmd.run("mv %s/ %s.bak" % (entry.get('name'),
                                                    entry.get('name')))
                else:
                    os.unlink(entry.get('name'))
            except OSError:
                self.logger.info("Hardlink %s cleanup failed" % \
                                 (entry.get('name')))
        try:
            os.link(entry.get('to'), entry.get('name'))
            return self._set_perms(entry)
        except OSError:
            return False

    def Verifynonexistent(self, entry, _):
        """Verify nonexistent entry."""
        # return true if path does _not_ exist
        return not os.path.lexists(entry.get('name'))

    def Installnonexistent(self, entry):
        '''Remove nonexistent entries'''
        ename = entry.get('name')
        if entry.get('recursive').lower() == 'true':
            # ensure that configuration spec is consistent first
            if [e for e in self.buildModlist() \
                if e.startswith(ename) and e != ename]:
                self.logger.error('Not installing %s. One or more files '
                                  'in this directory are specified in '
                                  'your configuration.' % ename)
                return False
            try:
                shutil.rmtree(ename)
            except OSError:
                e = sys.exc_info()[1]
                self.logger.error('Failed to remove %s: %s' % (ename,
                                                               e.strerror))
        else:
            if os.path.islink(ename):
                os.remove(ename)
                return True
            elif os.path.isdir(ename):
                try:
                    os.rmdir(ename)
                    return True
                except OSError:
                    e = sys.exc_info()[1]
                    self.logger.error('Failed to remove %s: %s' % (ename,
                                                                   e.strerror))
                    return False
            try:
                os.remove(ename)
                return True
            except OSError:
                e = sys.exc_info()[1]
                self.logger.error('Failed to remove %s: %s' % (ename,
                                                               e.strerror))
                return False

    def Verifypermissions(self, entry, _):
        """Verify Path type='permissions' entry"""
        rv = self._verify_metadata(entry)
        
        if entry.get('recursive', 'false').lower() == 'true':
            # verify ownership information recursively
            for root, dirs, files in os.walk(entry.get('name')):
                for p in dirs + files:
                    rv &= self._verify_metadata(entry,
                                                path=os.path.join(root, p))
        return rv

    def Installpermissions(self, entry):
        """Install POSIX permissions"""
        plist = [entry.get('name')]
        if entry.get('recursive', 'false').lower() == 'true':
            # verify ownership information recursively
            for root, dirs, files in os.walk(entry.get('name')):
                for p in dirs + files:
                    if not self._verify_metadata(entry,
                                                 path=os.path.join(root, p),
                                                 checkonly=True):
                        plist.append(path)
        rv = True
        for path in plist:
            rv &= self._set_perms(entry, path)
        return rv

    def Verifysymlink(self, entry, _):
        """Verify Path type='symlink' entry."""
        if entry.get('to') == None:
            self.logger.error('Entry %s not completely specified. '
                              'Try running bcfg2-lint.' %
                              (entry.get('name')))
            return False

        rv = True

        try:
            sloc = os.readlink(entry.get('name'))
            if sloc != entry.get('to'):
                entry.set('current_to', sloc)
                msg = ("Symlink %s points to %s, should be %s" %
                       (entry.get('name'), sloc, entry.get('to')))
                self.logger.debug(msg)
                entry.set('qtext', "\n".join([entry.get('qtext', ''), msg]))
                rv = False
        except OSError:
            entry.set('current_exists', 'false')
            return False

        rv &= self._verify_secontext(entry)
        return rv

    def Installsymlink(self, entry):
        """Install Path type='symlink' entry."""
        if entry.get('to') == None:
            self.logger.error('Entry %s not completely specified. '
                              'Try running bcfg2-lint.' % entry.get('name'))
            return False
        self.logger.info("Installing symlink %s" % (entry.get('name')))
        if os.path.lexists(entry.get('name')):
            try:
                fmode = os.lstat(entry.get('name'))[stat.ST_MODE]
                if stat.S_ISREG(fmode) or stat.S_ISLNK(fmode):
                    self.logger.debug("Non-directory entry already exists at "
                                      "%s. Unlinking entry." %
                                      entry.get('name'))
                    os.unlink(entry.get('name'))
                elif stat.S_ISDIR(fmode):
                    self.logger.debug("Directory already exists at %s" %
                                      entry.get('name'))
                    self.cmd.run("mv %s/ %s.bak" % (entry.get('name'),
                                                    entry.get('name')))
                else:
                    os.unlink(entry.get('name'))
            except OSError:
                self.logger.info("Symlink %s cleanup failed" %
                                 (entry.get('name')))
        try:
            os.symlink(entry.get('to'), entry.get('name'))
            return self._set_setcontext(entry)
        except OSError:
            return False

    def InstallPath(self, entry):
        """Dispatch install to the proper method according to type"""
        ret = getattr(self, 'Install%s' % entry.get('type'))
        return ret(entry)

    def VerifyPath(self, entry, _):
        """Dispatch verify to the proper method according to type"""
        ret = getattr(self, 'Verify%s' % entry.get('type'))(entry, _)
        if entry.get('qtext') and self.setup['interactive']:
            entry.set('qtext',
                      '%s\nInstall %s %s: (y/N) ' %
                      (entry.get('qtext'),
                       entry.get('type'), entry.get('name')))
        return ret

    def _verify_metadata(self, entry, path=None, checkonly=False):
        """ generic method to verify perms, owner, group, secontext,
        and mtime """

        # allow setting an alternate path for recursive permissions checking
        if path is None:
            path = entry.get('name')
        
        while len(entry.get('perms', '')) < 4:
            entry.set('perms', '0' + entry.get('perms', ''))

        try:
            ondisk = os.stat(path)
        except OSError:
            entry.set('current_exists', 'false')
            self.logger.debug("POSIX: %s %s does not exist" %
                              (entry.tag, path))
            return False

        try:
            owner = str(ondisk[stat.ST_UID])
            group = str(ondisk[stat.ST_GID])
        except (OSError, KeyError):
            self.logger.error('POSIX: User/Group resolution failed for path %s'
                              % path)
            owner = 'root'
            group = '0'

        perms = oct(ondisk[stat.ST_MODE])[-4:]
        if entry.get('mtime', '-1') != '-1':
            mtime = str(ondisk[stat.ST_MTIME])
        else:
            mtime = '-1'

        configOwner = str(self._norm_entry_uid(entry))
        configGroup = str(self._norm_entry_gid(entry))
        configPerms = int(entry.get('perms'), 8)
        if entry.get('dev_type'):
            configPerms |= device_map[entry.get('dev_type')]
        if has_selinux:
            if entry.get("secontext") == "__default__":
                try:
                    configContext = selinux.matchpathcon(path, 0)[1]
                except OSError:
                    self.logger.warning("Failed to get default SELinux context "
                                        "for %s; missing fcontext rule?" %
                                        path)
                    return False
            else:
                configContext = entry.get("secontext")

        errors = []
        if owner != configOwner:
            if checkonly:
                return False
            entry.set('current_owner', owner)
            errors.append("POSIX: Owner for path %s is incorrect. "
                          "Current owner is %s but should be %s" %
                          (path, ondisk.st_uid, entry.get('owner')))
                        
        if group != configGroup:
            if checkonly:
                return False
            entry.set('current_group', group)
            errors.append("POSIX: Group for path %s is incorrect. "
                          "Current group is %s but should be %s" %
                          (path, ondisk.st_gid, entry.get('group')))

        if oct(int(perms, 8)) != oct(configPerms):
            if checkonly:
                return False
            entry.set('current_perms', perms)
            errors.append("POSIX: Permissions for path %s are incorrect. "
                          "Current permissions are %s but should be %s" %
                          (path, perms, entry.get('perms')))

        if entry.get('mtime') and mtime != entry.get('mtime', '-1'):
            if checkonly:
                return False
            entry.set('current_mtime', mtime)
            errors.append("POSIX: mtime for path %s is incorrect. "
                          "Current mtime is %s but should be %s" %
                          (path, mtime, entry.get('mtime')))

        seVerifies = self._verify_secontext(entry)
        aclVerifies = self._verify_acls(entry)

        if errors:
            for error in errors:
                self.logger.debug(error)
            entry.set('qtext', "\n".join([entry.get('qtext', '')] + errors))
            return False
        else:
            return seVerifies and aclVerifies

    def _list_entry_acls(self, entry):
        wanted = dict()
        for acl in entry.findall("ACL"):
            if acl.get("scope") == "user":
                scope = posix1e.ACL_USER
            elif acl.get("scope") == "group":
                scope = posix1e.ACL_GROUP
            else:
                self.logger.error("Unknown ACL scope %s" % acl.get("scope"))
                continue
            wanted[(acl.get("type"), scope, acl.get(acl.get("scope")))] = \
                self._norm_acl_perms(acl.get('perms'))
        return wanted

    def _list_file_acls(self, entry):
        def _process_acl(acl, atype):
            try:
                if acl.tag_type == posix1e.ACL_USER:
                    qual = pwd.getpwuid(acl.qualifier)[0]
                elif acl.tag_type == posix1e.ACL_GROUP:
                    qual = grp.getgrgid(acl.qualifier)[0]
                else:
                    return
            except (OSError, KeyError):
                err = sys.exc_info()[1]
                self.logger.error("Lookup of %s %s failed: %s" %
                                  (scope, acl.qualifier, err))
                qual = acl.qualifier
            existing[(atype, acl.tag_type, qual)] = \
                self._norm_acl_perms(acl.permset)

        existing = dict()
        for acl in posix1e.ACL(file=entry.get("name")):
            _process_acl(acl, "access")
        if os.path.isdir(entry.get("name")):
            for acl in posix1e.ACL(filedef=entry.get("name")):
                _process_acl(acl, "default")
        return existing

    def _verify_acls(self, entry):
        if not has_acls:
            if entry.findall("ACL"):
                self.logger.debug("ACLs listed for %s but no pylibacl library "
                                  "installed" % entry.get('name'))
            return True

        # create lists of normalized representations of the ACLs we want
        # and the ACLs we have.  this will make them easier to compare
        # than trying to mine that data out of the ACL objects and XML
        # objects and compare it at the same time.
        wanted = self._list_entry_acls(entry)
        existing = self._list_file_acls(entry)

        missing = []
        extra = []
        wrong = []
        for aclkey, perms in wanted.items():
            acl_str = self._acl2string(aclkey, perms)
            if aclkey not in existing:
                missing.append(acl_str)
            elif existing[aclkey] != perms:
                wrong.append((acl_str,
                              self._acl2string(aclkey, existing[aclkey])))

        for aclkey, perms in existing.items():
            if aclkey not in wanted:
                extra.append(self._acl2string(aclkey, perms))
        
        msg = []
        if missing:
            msg.append("%s ACLs are missing: %s" % (len(missing),
                                                    ", ".join(missing)))
        if wrong:
            msg.append("%s ACLs are wrong: %s" %
                       (len(wrong),
                        "; ".join(["%s should be %s" % (e, w)
                                   for w, e in wrong])))
        if extra:
            msg.append("%s extra ACLs: %s" % (len(extra), ", ".join(extra)))

        if msg:
            msg.insert(0,
                       "POSIX ACLs for path %s are incorrect." %
                       entry.get("name"))
            self.logger.debug(msg[0])
            for line in msg[1:]:
                self.logger.debug("  " + line)
            entry.set('qtext', "\n".join([entry.get("qtext", '')] + msg))
            return False
        return True

    def _verify_secontext(self, entry):
        if not self._secontext_matches(entry):
            path = entry.get("name")
            if entry.get("secontext") == "__default__":
                configContext = selinux.matchpathcon(path, 0)[1]
            else:
                configContext = entry.get("secontext")
            pcontext = selinux.getfilecon(path)[1]
            entry.set('current_secontext', pcontext)
            msg = ("SELinux context for path %s is incorrect. "
                   "Current context is %s but should be %s" %
                   (path, pcontext, configContext))
            self.logger.debug("POSIX: " + msg)
            entry.set('qtext', "\n".join([entry.get("qtext", ''), msg]))
            return False
        return True
            
    def _diff(self, content1, content2, difffunc, filename=None):
        rv = []
        start = time.time()
        longtime = False
        for diffline in difffunc(content1.split('\n'),
                                 content2.split('\n')):
            now = time.time()
            rv.append(diffline)
            if now - start > 5 and not longtime:
                if filename:
                    self.logger.info("Diff of %s taking a long time" %
                                     filename)
                else:
                    self.logger.info("Diff taking a long time")
                longtime = True
            elif now - start > 30:
                if filename:
                    self.logger.error("Diff of %s took too long; giving up" %
                                      filename)
                else:
                    self.logger.error("Diff took too long; giving up")
                return False
        return rv
