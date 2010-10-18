"""All POSIX Type client support for Bcfg2."""
__revision__ = '$Revision$'

from datetime import datetime
from stat import S_ISVTX, S_ISGID, S_ISUID, S_IXUSR, S_IWUSR, S_IRUSR, S_IXGRP
from stat import S_IWGRP, S_IRGRP, S_IXOTH, S_IWOTH, S_IROTH, ST_MODE, S_ISDIR
from stat import S_IFREG, ST_UID, ST_GID, S_ISREG, S_IFDIR, S_ISLNK, ST_MTIME
import binascii
import difflib
import errno
import grp
import logging
import os
import pwd
import shutil
import stat
import string
import time
import Bcfg2.Client.Tools
import Bcfg2.Options
from Bcfg2.Client import XML

log = logging.getLogger('posix')

# map between dev_type attribute and stat constants
device_map = {'block': stat.S_IFBLK,
              'char': stat.S_IFCHR,
              'fifo': stat.S_IFIFO}


def calcPerms(initial, perms):
    """This compares ondisk permissions with specified ones."""
    pdisp = [{1:S_ISVTX, 2:S_ISGID, 4:S_ISUID},
             {1:S_IXUSR, 2:S_IWUSR, 4:S_IRUSR},
             {1:S_IXGRP, 2:S_IWGRP, 4:S_IRGRP},
             {1:S_IXOTH, 2:S_IWOTH, 4:S_IROTH}]
    tempperms = initial
    if len(perms) == 3:
        perms = '0%s' % (perms)
    pdigits = [int(perms[digit]) for digit in range(4)]
    for index in range(4):
        for (num, perm) in list(pdisp[index].items()):
            if pdigits[index] & num:
                tempperms |= perm
    return tempperms


def normUid(entry):
    """
       This takes a user name or uid and
       returns the corresponding uid or False.
    """
    try:
        try:
            return int(entry.get('owner'))
        except:
            return int(pwd.getpwnam(entry.get('owner'))[2])
    except (OSError, KeyError):
        log.error('UID normalization failed for %s' % (entry.get('name')))
        return False


def normGid(entry):
    """
       This takes a group name or gid and
       returns the corresponding gid or False.
    """
    try:
        try:
            return int(entry.get('group'))
        except:
            return int(grp.getgrnam(entry.get('group'))[2])
    except (OSError, KeyError):
        log.error('GID normalization failed for %s' % (entry.get('name')))
        return False

text_chars = "".join([chr(y) for y in range(32, 127)] + list("\n\r\t\b"))
notrans = string.maketrans("", "")


def isString(strng):
    """Returns true if a string contains no binary chars."""
    if "\0" in strng:
        return False

    if not strng:
        return True

    return len(strng.translate(notrans, text_chars)) == 0


class POSIX(Bcfg2.Client.Tools.Tool):
    """POSIX File support code."""
    name = 'POSIX'
    __handles__ = [('ConfigFile', None),
                   ('Directory', None),
                   ('Path', 'device'),
                   ('Path', 'directory'),
                   ('Path', 'file'),
                   ('Path', 'hardlink'),
                   ('Path', 'nonexistent'),
                   ('Path', 'permissions'),
                   ('Path', 'symlink'),
                   ('Permissions', None),
                   ('SymLink', None)]
    __req__ = {'ConfigFile': ['name', 'owner', 'group', 'perms'],
               'Directory': ['name', 'owner', 'group', 'perms'],
               'Path': ['name', 'type'],
               'Permissions': ['name', 'owner', 'group', 'perms'],
               'SymLink': ['name', 'to']}

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
            if (entry.tag, entry.text, entry.get('empty', 'false')) == \
               ('ConfigFile', None, 'false'):
                return False
            return True
        else:
            return False

    def VerifySymLink(self, entry, _):
        """Verify SymLink Entry."""
        try:
            sloc = os.readlink(entry.get('name'))
            if sloc == entry.get('to'):
                return True
            self.logger.debug("Symlink %s points to %s, should be %s" % \
                              (entry.get('name'), sloc, entry.get('to')))
            entry.set('current_to', sloc)
            entry.set('qtext', "Link %s to %s? [y/N] " % (entry.get('name'),
                                                   entry.get('to')))
            return False
        except OSError:
            entry.set('current_exists', 'false')
            entry.set('qtext', "Link %s to %s? [y/N] " % (entry.get('name'),
                                                   entry.get('to')))
            return False

    def InstallSymLink(self, entry):
        """Install SymLink entry."""
        self.logger.info("Installing Symlink %s" % (entry.get('name')))
        if os.path.lexists(entry.get('name')):
            try:
                fmode = os.lstat(entry.get('name'))[ST_MODE]
                if S_ISREG(fmode) or S_ISLNK(fmode):
                    self.logger.debug("Non-directory entry already exists at "
                                      "%s. Unlinking entry." % \
                                      (entry.get('name')))
                    os.unlink(entry.get('name'))
                elif S_ISDIR(fmode):
                    self.logger.debug("Directory entry already exists at %s" %\
                                      (entry.get('name')))
                    self.cmd.run("mv %s/ %s.bak" % \
                                 (entry.get('name'),
                                  entry.get('name')))
                else:
                    os.unlink(entry.get('name'))
            except OSError:
                self.logger.info("Symlink %s cleanup failed" %\
                                 (entry.get('name')))
        try:
            os.symlink(entry.get('to'), entry.get('name'))
            return True
        except OSError:
            return False

    def VerifyDirectory(self, entry, modlist):
        """Verify Directory entry."""
        if entry.get('perms') == None or \
           entry.get('owner') == None or \
           entry.get('group') == None:
            return False
        while len(entry.get('perms', '')) < 4:
            entry.set('perms', '0' + entry.get('perms', ''))
        try:
            ondisk = os.stat(entry.get('name'))
        except OSError:
            entry.set('current_exists', 'false')
            self.logger.debug("%s %s does not exist" %
                              (entry.tag, entry.get('name')))
            return False
        try:
            owner = str(ondisk[ST_UID])
            group = str(ondisk[ST_GID])
        except (OSError, KeyError):
            self.logger.error('User/Group resolution failed for path %s' % \
                              entry.get('name'))
            owner = 'root'
            group = '0'
        finfo = os.stat(entry.get('name'))
        perms = oct(finfo[ST_MODE])[-4:]
        if entry.get('mtime', '-1') != '-1':
            mtime = str(finfo[ST_MTIME])
        else:
            mtime = '-1'
        pTrue = ((owner == str(normUid(entry))) and
                 (group == str(normGid(entry))) and
                 (perms == entry.get('perms')) and
                 (mtime == entry.get('mtime', '-1')))

        pruneTrue = True
        ex_ents = []
        if entry.get('prune', 'false') == 'true' \
               and (entry.tag == 'Directory' or
                    entry.get('type') == 'directory'):
               # FIXME: need to verify both old and new POSIX types
            try:
                entries = ['/'.join([entry.get('name'), ent]) \
                           for ent in os.listdir(entry.get('name'))]
                ex_ents = [e for e in entries if e not in modlist]
                if ex_ents:
                    pruneTrue = False
                    self.logger.debug("Directory %s contains extra entries:" % \
                                      entry.get('name'))
                    self.logger.debug(ex_ents)
                    nqtext = entry.get('qtext', '') + '\n'
                    nqtext += "Directory %s contains extra entries:" % \
                              entry.get('name')
                    nqtext += ":".join(ex_ents)
                    entry.set('qtest', nqtext)
                    [entry.append(XML.Element('Prune', path=x)) for x in ex_ents]
            except OSError:
                ex_ents = []
                pruneTrue = True

        if not pTrue:
            if owner != str(normUid(entry)):
                entry.set('current_owner', owner)
                self.logger.debug("%s %s ownership wrong" % \
                                  (entry.tag, entry.get('name')))
                nqtext = entry.get('qtext', '') + '\n'
                nqtext += "%s owner wrong. is %s should be %s" % \
                          (entry.get('name'), owner, entry.get('owner'))
                entry.set('qtext', nqtext)
            if group != str(normGid(entry)):
                entry.set('current_group', group)
                self.logger.debug("%s %s group wrong" % (entry.tag, entry.get('name')))
                nqtext = entry.get('qtext', '') + '\n'
                nqtext += "%s group is %s should be %s" % \
                          (entry.get('name'), group, entry.get('group'))
                entry.set('qtext', nqtext)
            if perms != entry.get('perms'):
                entry.set('current_perms', perms)
                self.logger.debug("%s %s permissions are %s should be %s" %
                               (entry.tag, entry.get('name'), perms, entry.get('perms')))
                nqtext = entry.get('qtext', '') + '\n'
                nqtext += "%s perms are %s should be %s" % \
                          (entry.get('name'), perms, entry.get('perms'))
                entry.set('qtext', nqtext)
            if mtime != entry.get('mtime', '-1'):
                entry.set('current_mtime', mtime)
                self.logger.debug("%s %s mtime is %s should be %s" \
                                  % (entry.tag, entry.get('name'), mtime,
                                     entry.get('mtime')))
                nqtext = entry.get('qtext', '') + '\n'
                nqtext += "%s mtime is %s should be %s" % \
                          (entry.get('name'), mtime, entry.get('mtime'))
                entry.set('qtext', nqtext)
            if entry.tag != 'ConfigFile':
                nnqtext = entry.get('qtext')
                nnqtext += '\nInstall %s %s: (y/N) ' % (entry.tag, entry.get('name'))
                entry.set('qtext', nnqtext)
        return pTrue and pruneTrue

    def InstallDirectory(self, entry):
        """Install Directory entry."""
        if entry.get('perms') == None or \
           entry.get('owner') == None or \
           entry.get('group') == None:
            self.logger.error('Entry %s not completely specified. '
                              'Try running bcfg2-repo-validate.' % (entry.get('name')))
            return False
        self.logger.info("Installing Directory %s" % (entry.get('name')))
        try:
            fmode = os.lstat(entry.get('name'))
            if not S_ISDIR(fmode[ST_MODE]):
                self.logger.debug("Found a non-directory entry at %s" % \
                                  (entry.get('name')))
                try:
                    os.unlink(entry.get('name'))
                    exists = False
                except OSError:
                    self.logger.info("Failed to unlink %s" % (entry.get('name')))
                    return False
            else:
                self.logger.debug("Found a pre-existing directory at %s" % \
                                  (entry.get('name')))
                exists = True
        except OSError:
            # stat failed
            exists = False

        if not exists:
            parent = "/".join(entry.get('name').split('/')[:-1])
            if parent:
                try:
                    os.stat(parent)
                except:
                    self.logger.debug('Creating parent path for directory %s' % (entry.get('name')))
                    for idx in range(len(parent.split('/')[:-1])):
                        current = '/'+'/'.join(parent.split('/')[1:2+idx])
                        try:
                            sloc = os.stat(current)
                        except OSError:
                            try:
                                os.mkdir(current)
                                continue
                            except OSError:
                                return False
                        if not S_ISDIR(sloc[ST_MODE]):
                            try:
                                os.unlink(current)
                                os.mkdir(current)
                            except OSError:
                                return False

            try:
                os.mkdir(entry.get('name'))
            except OSError:
                self.logger.error('Failed to create directory %s' % \
                                  (entry.get('name')))
                return False
        if entry.get('prune', 'false') == 'true' and entry.get("qtest"):
            for pent in entry.findall('Prune'):
                pname = pent.get('path')
                ulfailed = False
                if os.path.isdir(pname):
                    self.logger.info("Not removing extra directory %s, please check and remove manually" % pname)
                    continue
                try:
                    self.logger.debug("Unlinking file %s" % pname)
                    os.unlink(pname)
                except OSError:
                    self.logger.error("Failed to unlink path %s" % pname)
                    ulfailed = True
            if ulfailed:
                return False
        return self.InstallPermissions(entry)

    def VerifyhardLink(self, entry, _):
        """Verify HardLink entry."""
        try:
            if os.path.samefile(entry.get('name'), entry.get('to')):
                return True
            self.logger.debug("Hardlink %s is incorrect" % \
                              entry.get('name'))
            entry.set('qtext', "Link %s to %s? [y/N] " % \
                      (entry.get('name'),
                       entry.get('to')))
            return False
        except OSError:
            entry.set('current_exists', 'false')
            entry.set('qtext', "Link %s to %s? [y/N] " % \
                      (entry.get('name'),
                       entry.get('to')))
            return False

    def InstallhardLink(self, entry):
        """Install HardLink entry."""
        self.logger.info("Installing Hardlink %s" % (entry.get('name')))
        if os.path.lexists(entry.get('name')):
            try:
                fmode = os.lstat(entry.get('name'))[ST_MODE]
                if S_ISREG(fmode) or S_ISLNK(fmode):
                    self.logger.debug("Non-directory entry already exists at "
                                      "%s. Unlinking entry." % (entry.get('name')))
                    os.unlink(entry.get('name'))
                elif S_ISDIR(fmode):
                    self.logger.debug("Directory entry already exists at %s" % \
                                      (entry.get('name')))
                    self.cmd.run("mv %s/ %s.bak" % \
                                 (entry.get('name'),
                                  entry.get('name')))
                else:
                    os.unlink(entry.get('name'))
            except OSError:
                self.logger.info("Hardlink %s cleanup failed" % (entry.get('name')))
        try:
            os.link(entry.get('to'), entry.get('name'))
            return True
        except OSError:
            return False

    def VerifyPermissions(self, entry, _):
        """Verify Permissions entry"""
        return self.VerifyDirectory(entry, _)

    def InstallPermissions(self, entry):
        """Install POSIX permissions"""
        if entry.get('perms') == None or \
           entry.get('owner') == None or \
           entry.get('group') == None:
            self.logger.error('Entry %s not completely specified. '
                              'Try running bcfg2-repo-validate.' % (entry.get('name')))
            return False
        try:
            os.chown(entry.get('name'), normUid(entry), normGid(entry))
            os.chmod(entry.get('name'), calcPerms(S_IFDIR, entry.get('perms')))
            return True
        except (OSError, KeyError):
            self.logger.error('Permission fixup failed for %s' % \
                              (entry.get('name')))
            return False

    def Verifydevice(self, entry, _):
        """Verify device entry."""
        try:
            # check for file existence
            filestat = os.stat(entry.get('name'))
        except OSError:
            entry.set('current_exists', 'false')
            self.logger.debug("%s %s does not exist" %
                              (entry.tag, entry.get('name')))
            return False

        try:
            # attempt to verify device properties as specified in config
            dev_type = entry.get('dev_type')
            mode = calcPerms(device_map[dev_type],
                             entry.get('mode', '0600'))
            owner = entry.get('owner')
            group = entry.get('group')
            if dev_type in ['block', 'char']:
                major = int(entry.get('major'))
                minor = int(entry.get('minor'))
                if major == os.major(filestat.st_rdev) and \
                   minor == os.minor(filestat.st_rdev) and \
                   mode == filestat.st_mode and \
                   owner == filestat.st_uid and \
                   group == filestat.st_gid:
                    return True
                else:
                    return False
            elif dev_type == 'fifo' and \
                 mode == filestat.st_mode and \
                 owner == filestat.st_uid and \
                 group == filestat.st_gid:
                return True
            else:
                self.logger.info('Device properties for %s incorrect' % \
                                 entry.get('name'))
                return False
        except OSError:
            self.logger.debug("%s %s failed to verify" %
                              (entry.tag, entry.get('name')))
            return False

    def Installdevice(self, entry):
        """Install device entries."""
        try:
            # check for existing paths and remove them
            filestat = os.lstat(entry.get('name'))
            try:
                os.unlink(entry.get('name'))
                exists = False
            except OSError:
                self.logger.info('Failed to unlink %s' % \
                                 entry.get('name'))
                return False
        except OSError:
            exists = False

        if not exists:
            try:
                dev_type = entry.get('dev_type')
                mode = calcPerms(device_map[dev_type],
                                 entry.get('mode', '0600'))
                if dev_type in ['block', 'char']:
                    major = int(entry.get('major'))
                    minor = int(entry.get('minor'))
                    device = os.makedev(major, minor)
                    os.mknod(entry.get('name'), mode, device)
                else:
                    os.mknod(entry.get('name'), mode)
                os.chown(entry.get('name'), normUid(entry), normGid(entry))
                return True
            except OSError:
                self.logger.error('Failed to install %s' % entry.get('name'))
                return False

    def Verifynonexistent(self, entry, _):
        """Verify nonexistent entry."""
        # return true if path does _not_ exist
        return not os.path.lexists(entry.get('name'))

    def Installnonexistent(self, entry):
        '''Remove nonexistent entries'''
        try:
            os.remove(entry.get('name'))
            return True
        except OSError:
            self.logger.error('Failed to remove %s' % entry.get('name'))
            return False

    def gatherCurrentData(self, entry):
        if entry.tag == 'ConfigFile':
            try:
                ondisk = os.stat(entry.get('name'))
            except OSError:
                entry.set('current_exists', 'false')
                self.logger.debug("%s %s does not exist" %
                                  (entry.tag, entry.get('name')))
                return False
            try:
                entry.set('current_owner', str(ondisk[ST_UID]))
                entry.set('current_group', str(ondisk[ST_GID]))
            except (OSError, KeyError):
                pass
            entry.set('perms', str(oct(ondisk[ST_MODE])[-4:]))
            try:
                content = open(entry.get('name')).read()
                entry.set('current_bfile', binascii.b2a_base64(content))
            except IOError, error:
                self.logger.error("Failed to read %s: %s" % (error.filename, error.strerror))

    def VerifyConfigFile(self, entry, _):
        """Install ConfigFile entry."""
        # configfile verify is permissions check + content check
        permissionStatus = self.VerifyDirectory(entry, _)
        tbin = False
        if entry.get('encoding', 'ascii') == 'base64':
            tempdata = binascii.a2b_base64(entry.text)
            tbin = True
        elif entry.get('empty', 'false') == 'true':
            tempdata = ''
        else:
            if entry.text == None:
                self.logger.error("Cannot verify incomplete ConfigFile %s" % \
                                  (entry.get('name')))
                return False
            tempdata = entry.text
            if type(tempdata) == unicode:
                try:
                    tempdata = tempdata.encode(self.setup['encoding'])
                except UnicodeEncodeError, e:
                    self.logger.error("Error encoding file %s:\n %s" % \
                                      (entry.get('name'), e))
        try:
            content = open(entry.get('name')).read()
        except IOError, error:
            if error.strerror == "No such file or directory":
                # print diff for files that don't exist (yet)
                content = ''
            else:
                self.logger.error("Failed to read %s: %s" % \
                                  (error.filename, error.strerror))
                return False
        # comparison should be done with fingerprints or
        # md5sum so it would be faster for big binary files
        contentStatus = content == tempdata
        if not contentStatus:
            if tbin or not isString(content):
                entry.set('current_bfile', binascii.b2a_base64(content))
                nqtext = entry.get('qtext', '')
                nqtext += '\nBinary file, no printable diff'
            else:
                do_diff = True
                rawdiff = []
                start = time.time()
                longtime = False
                for x in difflib.ndiff(content.split('\n'), tempdata.split('\n')):
                    now = time.time()
                    rawdiff.append(x)
                    if now - start > 5 and not longtime:
                        self.logger.info("Diff of %s taking a long time" % \
                                         (entry.get('name')))
                        longtime = True
                    elif now - start > 30:
                        self.logger.error("Diff of %s took too long; giving up" % \
                                          (entry.get('name')))
                        do_diff = False
                        break
                if do_diff:
                    diff = '\n'.join(rawdiff)
                    entry.set("current_bdiff", binascii.b2a_base64(diff))
#                    entry.set("current_diff", diff)
                    udiff = '\n'.join([x for x in \
                                       difflib.unified_diff(content.split('\n'), \
                                                            tempdata.split('\n'))])
                    try:
                        eudiff = udiff.encode('ascii')
                    except:
                        eudiff = "Binary file: no diff printed"

                    nqtext = entry.get('qtext', '')

                    if nqtext:
                        nqtext += '\n'
                    nqtext += eudiff
                else:
                    entry.set('current_bfile', binascii.b2a_base64(content))
                    nqtext = entry.get('qtext', '')
                    nqtext += '\nDiff took too long to compute, no printable diff'
            entry.set('qtext', nqtext)
        qtxt = entry.get('qtext', '')
        qtxt += "\nInstall %s %s: (y/N): " % (entry.tag, entry.get('name'))
        entry.set('qtext', qtxt)
        return contentStatus and permissionStatus

    def InstallConfigFile(self, entry):
        """Install ConfigFile entry."""
        self.logger.info("Installing ConfigFile %s" % (entry.get('name')))

        parent = "/".join(entry.get('name').split('/')[:-1])
        if parent:
            try:
                os.stat(parent)
            except:
                self.logger.debug('Creating parent path for config file %s' % \
                                  (entry.get('name')))
                current = '/'
                for next in parent.split('/')[1:]:
                    current += next + '/'
                    try:
                        sloc = os.stat(current)
                        try:
                            if not S_ISDIR(sloc[ST_MODE]):
                                self.logger.debug('%s is not a directory; recreating' \
                                                  % (current))
                                os.unlink(current)
                                os.mkdir(current)
                        except OSError:
                            return False
                    except OSError:
                        try:
                            self.logger.debug("Creating non-existent path %s" % current)
                            os.mkdir(current)
                        except OSError:
                            return False

        # If we get here, then the parent directory should exist
        if (entry.get("paranoid", False) == 'true') and \
           self.setup.get("paranoid", False) and not \
           (entry.get('current_exists', 'true') == 'false'):
            bkupnam = entry.get('name').replace('/', '_')
            # current list of backups for this ConfigFile
            bkuplist = [f for f in os.listdir(self.ppath) if
                              f.startswith(bkupnam)]
            bkuplist.sort()
            if len(bkuplist) == int(self.max_copies):
                # remove the oldest backup available
                oldest = bkuplist.pop(0)
                self.logger.info("Removing %s" % oldest)
                try:
                    os.remove("%s/%s" % (self.ppath, oldest))
                except:
                    self.logger.error("Failed to remove %s/%s" % \
                                      (self.ppath, oldest))
                    return False
            try:
                # backup existing file
                shutil.copy(entry.get('name'),
                            "%s/%s_%s" % (self.ppath, bkupnam, datetime.now()))
                self.logger.info("Backup of %s saved to %s" %
                                 (entry.get('name'), self.ppath))
            except IOError, e:
                self.logger.error("Failed to create backup file for ConfigFile %s" % \
                                  (entry.get('name')))
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
            try:
                os.chown(newfile.name, normUid(entry), normGid(entry))
            except KeyError:
                self.logger.error("Failed to chown %s to %s:%s" % \
                                  (entry.get('name'), entry.get('owner'),
                                   entry.get('group')))
                os.chown(newfile.name, 0, 0)
            os.chmod(newfile.name, calcPerms(S_IFREG, entry.get('perms')))
            os.rename(newfile.name, entry.get('name'))
            if entry.get('mtime', '-1') != '-1':
                try:
                    os.utime(entry.get('name'), (int(entry.get('mtime')),
                                                 int(entry.get('mtime'))))
                except:
                    self.logger.error("ConfigFile %s mtime fix failed" \
                                      % (entry.get('name')))
                    return False
            return True
        except (OSError, IOError), err:
            if err.errno == errno.EACCES:
                self.logger.info("Failed to open %s for writing" % (entry.get('name')))
            else:
                print(err)
            return False

    def Verifydirectory(self, entry, _):
        ret = getattr(self, 'VerifyDirectory')
        return ret(entry, _)

    def Installdirectory(self, entry):
        ret = getattr(self, 'InstallDirectory')
        return ret(entry)

    def Verifyfile(self, entry, _):
        ret = getattr(self, 'VerifyConfigFile')
        return ret(entry, _)

    def Installfile(self, entry):
        ret = getattr(self, 'InstallConfigFile')
        return ret(entry)

    def Verifypermissions(self, entry, _):
        ret = getattr(self, 'VerifyPermissions')
        return ret(entry, _)

    def Installpermissions(self, entry):
        ret = getattr(self, 'InstallPermissions')
        return ret(entry)

    def Verifysymlink(self, entry, _):
        ret = getattr(self, 'VerifySymLink')
        return ret(entry, _)

    def Installsymlink(self, entry):
        ret = getattr(self, 'InstallSymLink')
        return ret(entry)

    def InstallPath(self, entry):
        ret = getattr(self, 'Install%s' % entry.get('type'))
        return ret(entry)

    def VerifyPath(self, entry, _):
        ret = getattr(self, 'Verify%s' % entry.get('type'))
        return ret(entry, _)
