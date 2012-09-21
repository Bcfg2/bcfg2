import os
import sys
import pwd
import grp
import stat
import shutil
import Bcfg2.Client.Tools
import Bcfg2.Client.XML

try:
    import selinux
    has_selinux = True
except ImportError:
    has_selinux = False

try:
    import posix1e
    has_acls = True

    # map between permissions characters and numeric ACL constants
    acl_map = dict(r=posix1e.ACL_READ,
                   w=posix1e.ACL_WRITE,
                   x=posix1e.ACL_EXECUTE)
except ImportError:
    has_acls = False
    acl_map = dict(r=4, w=2, x=1)

# map between dev_type attribute and stat constants
device_map = dict(block=stat.S_IFBLK,
                  char=stat.S_IFCHR,
                  fifo=stat.S_IFIFO)


class POSIXTool(Bcfg2.Client.Tools.Tool):
    def fully_specified(self, entry):
        # checking is done by __req__
        return True

    def verify(self, entry, modlist):
        if not self._verify_metadata(entry):
            return False
        if entry.get('recursive', 'false').lower() == 'true':
            # verify ownership information recursively
            for root, dirs, files in os.walk(entry.get('name')):
                for p in dirs + files:
                    if not self._verify_metadata(entry,
                                                 path=os.path.join(root, p)):
                        return False
        return True

    def install(self, entry):
        plist = [entry.get('name')]
        rv = True
        rv &= self._set_perms(entry)
        if entry.get('recursive', 'false').lower() == 'true':
            # set metadata recursively
            for root, dirs, files in os.walk(entry.get('name')):
                for path in dirs + files:
                    rv &= self._set_perms(entry, path=os.path.join(root, path))
        return rv

    def _exists(self, entry, remove=False):
        try:
            # check for existing paths and optionally remove them
            ondisk = os.lstat(entry.get('name'))
            if remove:
                if os.path.isdir(entry.get('name')):
                    rm = shutil.rmtree
                else:
                    rm = os.unlink
                try:
                    rm(entry.get('name'))
                    return False
                except OSError:
                    err = sys.exc_info()[1]
                    self.logger.warning('POSIX: Failed to unlink %s: %s' %
                                        (entry.get('name'), err))
                    return ondisk # probably still exists
            else:
                return ondisk
        except OSError:
            return False

    def _set_perms(self, entry, path=None):
        if path is None:
            path = entry.get("name")

        rv = True
        if entry.get("owner") and entry.get("group"):
            try:
                self.logger.debug("POSIX: Setting ownership of %s to %s:%s" %
                                  (path,
                                   self._norm_entry_uid(entry),
                                   self._norm_entry_gid(entry)))
                os.chown(path, self._norm_entry_uid(entry),
                         self._norm_entry_gid(entry))
            except KeyError:
                self.logger.error('POSIX: Failed to change ownership of %s' %
                                  path)
                rv = False
                os.chown(path, 0, 0)
            except OSError:
                self.logger.error('POSIX: Failed to change ownership of %s' %
                                  path)
                rv = False

        if entry.get("perms"):
            configPerms = int(entry.get('perms'), 8)
            if entry.get('dev_type'):
                configPerms |= device_map[entry.get('dev_type')]
            try:
                self.logger.debug("POSIX: Setting permissions on %s to %s" %
                                  (path, oct(configPerms)))
                os.chmod(path, configPerms)
            except (OSError, KeyError):
                self.logger.error('POSIX: Failed to change permissions on %s' %
                                  path)
                rv = False

        if entry.get('mtime'):
            try:
                os.utime(entry.get('name'), (int(entry.get('mtime')),
                                             int(entry.get('mtime'))))
            except OSError:
                self.logger.error("POSIX: Failed to set mtime of %s" % path)
                rv = False

        rv &= self._set_secontext(entry, path=path)
        rv &= self._set_acls(entry, path=path)
        return rv


    def _set_acls(self, entry, path=None):
        """ set POSIX ACLs on the file on disk according to the config """
        if not has_acls:
            if entry.findall("ACL"):
                self.logger.debug("POSIX: ACLs listed for %s but no pylibacl "
                                  "library installed" % entry.get('name'))
            return True

        if path is None:
            path = entry.get("name")

        try:
            acl = posix1e.ACL(file=path)
        except IOError:
            err = sys.exc_info()[1]
            if err.errno == 95:
                # fs is mounted noacl
                self.logger.error("POSIX: Cannot set ACLs on filesystem "
                                  "mounted without ACL support: %s" % path)
            else:
                self.logger.error("POSIX: Error getting current ACLS on %s: %s"
                                  % (path, err))
            return False
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
                    self.logger.warning("POSIX: Cannot set default ACLs on "
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
                self.logger.error("POSIX: Could not resolve %s %s: %s" %
                                  (scopename, qualifier, err))
                continue
        acl.calc_mask()

        def _apply_acl(acl, path, atype=posix1e.ACL_TYPE_ACCESS):
            if atype == posix1e.ACL_TYPE_ACCESS:
                atype_str = "access"
            else:
                atype_str = "default"
            if acl.valid():
                self.logger.debug("POSIX: Applying %s ACL to %s:" % (atype_str,
                                                                     path))
                for line in str(acl).splitlines():
                    self.logger.debug("  " + line)
                try:
                    acl.applyto(path, atype)
                    return True
                except:
                    err = sys.exc_info()[1]
                    self.logger.error("POSIX: Failed to set ACLs on %s: %s" %
                                      (path, err))
                    return False
            else:
                self.logger.warning("POSIX: %s ACL created for %s was invalid:"
                                    % (atype_str.title(), path))
                for line in str(acl).splitlines():
                    self.logger.warning("  " + line)
                return False

        rv = _apply_acl(acl, path)
        if defacl:
            defacl.calc_mask()
            rv &= _apply_acl(defacl, path, posix1e.ACL_TYPE_DEFAULT)
        return rv

    def _set_secontext(self, entry, path=None):
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

        if context == '__default__':
            try:
                selinux.restorecon(path)
                rv = True
            except:
                err = sys.exc_info()[1]
                self.logger.error("POSIX: Failed to restore SELinux context "
                                  "for %s: %s" % (path, err))
                rv = False
        else:
            try:
                rv = selinux.lsetfilecon(path, context) == 0
            except:
                err = sys.exc_info()[1]
                self.logger.error("POSIX: Failed to restore SELinux context "
                                  "for %s: %s" % (path, err))
                rv = False
        return rv

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
            self.logger.error('POSIX: GID normalization failed for %s on %s: %s'
                              % (entry.get('group'), entry.get('name'), err))
            return 0

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
            self.logger.error('POSIX: UID normalization failed for %s on %s: %s'
                              % (entry.get('owner'), entry.get('name'), err))
            return 0

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
            rv = int(perms)
            if rv > 0 and rv < 8:
                return rv
            else:
                self.logger.error("POSIX: Permissions digit out of range in "
                                  "ACL: %s" % perms)
                return 0
        except ValueError:
            # couldn't be converted to an int; process as a string
            if len(perms) > 3:
                self.logger.error("POSIX: Permissions string too long in ACL: "
                                  "%s" % perms)
                return 0
            rv = 0
            for char in perms:
                if char == '-':
                    continue
                elif char not in acl_map:
                    self.logger.warning("POSIX: Unknown permissions character "
                                        "in ACL: %s" % char)
                elif rv & acl_map[char]:
                    self.logger.warning("POSIX: Duplicate permissions "
                                        "character in ACL: %s" % perms)
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

    def _gather_data(self, path):
        try:
            ondisk = os.stat(path)
        except OSError:
            self.logger.debug("POSIX: %s does not exist" % path)
            return (False, None, None, None, None, None)

        try:
            owner = str(ondisk[stat.ST_UID])
        except OSError:
            err = sys.exc_info()[1]
            self.logger.debug("POSIX: Could not get current owner of %s: %s" %
                              (path, err))
            owner = None
        except KeyError:
            self.logger.error('POSIX: User resolution failed for %s' % path)
            owner = None

        try:
            group = str(ondisk[stat.ST_GID])
        except (OSError, KeyError):
            err = sys.exc_info()[1]
            self.logger.debug("POSIX: Could not get current group of %s: %s" %
                              (path, err))
            group = None
        except KeyError:
            self.logger.error('POSIX: Group resolution failed for %s' % path)
            group = None

        try:
            perms = oct(ondisk[stat.ST_MODE])[-4:]
        except (OSError, KeyError, TypeError):
            err = sys.exc_info()[1]
            self.logger.debug("POSIX: Could not get current permissions of %s: "
                              "%s" % (path, err))
            perms = None

        if has_selinux:
            try:
                secontext = selinux.getfilecon(path)[1].split(":")[2]
            except (OSError, KeyError):
                err = sys.exc_info()[1]
                self.logger.debug("POSIX: Could not get current SELinux "
                                  "context of %s: %s" % (path, err))
                secontext = None
        else:
            secontext = None

        if has_acls:
            acls = self._list_file_acls(path)
        else:
            acls = None
        return (ondisk, owner, group, perms, secontext, acls)

    def _verify_metadata(self, entry, path=None):
        """ generic method to verify perms, owner, group, secontext, acls,
        and mtime """
        # allow setting an alternate path for recursive permissions checking
        if path is None:
            path = entry.get('name')
        attrib = dict()
        ondisk, attrib['current_owner'], attrib['current_group'], \
            attrib['current_perms'], attrib['current_secontext'], acls = \
            self._gather_data(path)
        
        if not ondisk:
            entry.set('current_exists', 'false')
            return False

        # we conditionally verify every bit of metadata only if it's
        # specified on the entry.  consequently, canVerify() and
        # fully_specified() are preconditions of _verify_metadata(),
        # since they will ensure that everything that needs to be
        # specified actually is.  this lets us gracefully handle
        # symlink and hardlink entries, which have SELinux contexts
        # but not other permissions, optional secontext and mtime
        # attrs, and so on.
        configOwner, configGroup, configPerms, mtime = None, None, None, -1
        if entry.get('mtime', '-1') != '-1':
            mtime = str(ondisk[stat.ST_MTIME])
        if entry.get("owner"):
            configOwner = str(self._norm_entry_uid(entry))
        if entry.get("group"):
            configGroup = str(self._norm_entry_gid(entry))
        if entry.get("perms"):
            while len(entry.get('perms', '')) < 4:
                entry.set('perms', '0' + entry.get('perms', ''))
            configPerms = int(entry.get('perms'), 8)

        errors = []
        if configOwner and attrib['current_owner'] != configOwner:
            errors.append("Owner for path %s is incorrect. "
                          "Current owner is %s but should be %s" %
                          (path, attrib['current_owner'], entry.get('owner')))

        if configGroup and attrib['current_group'] != configGroup:
            errors.append("Group for path %s is incorrect. "
                          "Current group is %s but should be %s" %
                          (path, attrib['current_group'], entry.get('group')))

        if (configPerms and
            oct(int(attrib['current_perms'], 8)) != oct(configPerms)):
            errors.append("Permissions for path %s are incorrect. "
                          "Current permissions are %s but should be %s" %
                          (path, attrib['current_perms'], entry.get('perms')))

        if entry.get('mtime'):
            attrib['current_mtime'] = mtime
            if mtime != entry.get('mtime', '-1'):
                errors.append("mtime for path %s is incorrect. "
                              "Current mtime is %s but should be %s" %
                              (path, mtime, entry.get('mtime')))

        if has_selinux and entry.get("secontext"):
            if entry.get("secontext") == "__default__":
                configContext = selinux.matchpathcon(path, 0)[1].split(":")[2]
            else:
                configContext = entry.get("secontext")
            if attrib['current_secontext'] != configContext:
                errors.append("SELinux context for path %s is incorrect. "
                              "Current context is %s but should be %s" %
                              (path, attrib['current_secontext'],
                               configContext))

        if errors:
            for error in errors:
                self.logger.debug("POSIX: " + error)
            entry.set('qtext', "\n".join([entry.get('qtext', '')] + errors))
        if path == entry.get("name"):
            for attr, val in attrib.items():
                if val is not None:
                    entry.set(attr, str(val))

        aclVerifies = self._verify_acls(entry, path=path)
        return aclVerifies and len(errors) == 0

    def _list_entry_acls(self, entry):
        wanted = dict()
        for acl in entry.findall("ACL"):
            if acl.get("scope") == "user":
                scope = posix1e.ACL_USER
            elif acl.get("scope") == "group":
                scope = posix1e.ACL_GROUP
            else:
                self.logger.error("POSIX: Unknown ACL scope %s" %
                                  acl.get("scope"))
                continue
            wanted[(acl.get("type"), scope, acl.get(acl.get("scope")))] = \
                self._norm_acl_perms(acl.get('perms'))
        return wanted

    def _list_file_acls(self, path):
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
                self.logger.error("POSIX: Lookup of %s %s failed: %s" %
                                  (atype, acl.qualifier, err))
                qual = acl.qualifier
            existing[(atype, acl.tag_type, qual)] = \
                self._norm_acl_perms(acl.permset)

        existing = dict()
        try:
            for acl in posix1e.ACL(file=path):
                _process_acl(acl, "access")
        except IOError:
            err = sys.exc_info()[1]
            if err.errno == 95:
                # fs is mounted noacl
                self.logger.debug("POSIX: Filesystem mounted without ACL "
                                  "support: %s" % path)
            else:
                self.logger.error("POSIX: Error getting current ACLS on %s: %s"
                                  % (path, err))
            return existing

        if os.path.isdir(path):
            for acl in posix1e.ACL(filedef=path):
                _process_acl(acl, "default")
        return existing

    def _verify_acls(self, entry, path=None):
        if not has_acls:
            if entry.findall("ACL"):
                self.logger.debug("POSIX: ACLs listed for %s but no pylibacl "
                                  "library installed" % entry.get('name'))
            return True

        if path is None:
            path = entry.get("name")

        # create lists of normalized representations of the ACLs we want
        # and the ACLs we have.  this will make them easier to compare
        # than trying to mine that data out of the ACL objects and XML
        # objects and compare it at the same time.
        wanted = self._list_entry_acls(entry)
        existing = self._list_file_acls(path)

        missing = []
        extra = []
        wrong = []
        for aclkey, perms in wanted.items():
            if aclkey not in existing:
                missing.append(self._acl2string(aclkey, perms))
            elif existing[aclkey] != perms:
                wrong.append((self._acl2string(aclkey, perms),
                              self._acl2string(aclkey, existing[aclkey])))
            if path == entry.get("name"):
                atype, scope, qual = aclkey
                aclentry = Bcfg2.Client.XML.Element("ACL", type=atype,
                                                    perms=str(perms))
                if scope == posix1e.ACL_USER:
                    aclentry.set("scope", "user")
                elif scope == posix1e.ACL_GROUP:
                    aclentry.set("scope", "group")
                else:
                    self.logger.debug("POSIX: Unknown ACL scope %s on %s" %
                                      (scope, path))
                    continue
                aclentry.set(aclentry.get("scope"), qual)
                entry.append(aclentry)

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
            msg.insert(0, "POSIX: ACLs for %s are incorrect." % path)
            self.logger.debug(msg[0])
            for line in msg[1:]:
                self.logger.debug("  " + line)
            entry.set('qtext', "\n".join([entry.get("qtext", '')] + msg))
            return False
        return True

    def _makedirs(self, entry, path=None):
        """ os.makedirs helpfully creates all parent directories for
        us, but it sets permissions according to umask, which is
        probably wrong.  we need to find out which directories were
        created and set permissions on those
        (http://trac.mcs.anl.gov/projects/bcfg2/ticket/1125) """
        created = []
        if path is None:
            path = entry.get("name")
        cur = path
        while cur != '/':
            if not os.path.exists(cur):
                created.append(cur)
            cur = os.path.dirname(cur)
        rv = True
        try:
            os.makedirs(path)
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error('POSIX: Failed to create directory %s: %s' %
                              (path, err))
            rv = False
        for cpath in created:
            rv &= self._set_perms(entry, path=cpath)
        return rv
