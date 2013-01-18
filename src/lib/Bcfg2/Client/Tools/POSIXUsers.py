""" A tool to handle creating users and groups with useradd/mod/del
and groupadd/mod/del """

import sys
import pwd
import grp
import subprocess
import Bcfg2.Client.XML
import Bcfg2.Client.Tools
from Bcfg2.Compat import any  # pylint: disable=W0622


class IDRangeSet(object):
    """ Representation of a set of integer ranges.  Used to describe
    which UID/GID ranges are managed or unmanaged. """

    def __init__(self, *ranges):
        self.ranges = []
        self.ints = []
        self.str = ",".join(str(r) for r in ranges)
        for item in ranges:
            item = str(item).strip()
            if item.endswith("-"):
                self.ranges.append((int(item[:-1]), None))
            elif '-' in str(item):
                self.ranges.append(tuple(int(x) for x in item.split('-')))
            else:
                self.ints.append(int(item))

    def __contains__(self, other):
        other = int(other)
        if other in self.ints:
            return True
        return any((end is None and other >= start) or
                   (end is not None and other >= start and other <= end)
                   for start, end in self.ranges)

    def __repr__(self):
        return "%s:%s" % (self.__class__.__name__, str(self))

    def __str__(self):
        return "[%s]" % self.str

    def __len__(self):
        return len(self.ranges) + len(self.ints)


class ExecutionError(Exception):
    """ Raised when running an external command fails """

    def __init__(self, msg, retval=None):
        Exception.__init__(self, msg)
        self.retval = retval

    def __str__(self):
        return "%s (rv: %s)" % (Exception.__str__(self),
                                          self.retval)


class Executor(object):
    """ A better version of Bcfg2.Client.Tool.Executor, which captures
    stderr, raises exceptions on error, and doesn't use the shell to
    execute by default """

    def __init__(self, logger):
        self.logger = logger
        self.stdout = None
        self.stderr = None
        self.retval = None

    def run(self, command, inputdata=None, shell=False):
        """ Run a command, given as a list, optionally giving it the
        specified input data """
        self.logger.debug("Running: %s" % " ".join(command))
        proc = subprocess.Popen(command, shell=shell, bufsize=16384,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, close_fds=True)
        if inputdata:
            for line in inputdata.splitlines():
                self.logger.debug('> %s' % line)
            (self.stdout, self.stderr) = proc.communicate(inputdata)
        else:
            (self.stdout, self.stderr) = proc.communicate()
        for line in self.stdout.splitlines():  # pylint: disable=E1103
            self.logger.debug('< %s' % line)
        self.retval = proc.wait()
        if self.retval == 0:
            for line in self.stderr.splitlines():  # pylint: disable=E1103
                self.logger.warning(line)
            return True
        else:
            raise ExecutionError(self.stderr, self.retval)


class POSIXUsers(Bcfg2.Client.Tools.Tool):
    """ A tool to handle creating users and groups with
    useradd/mod/del and groupadd/mod/del """
    __execs__ = ['/usr/sbin/useradd', '/usr/sbin/usermod', '/usr/sbin/userdel',
                 '/usr/sbin/groupadd', '/usr/sbin/groupmod',
                 '/usr/sbin/groupdel']
    __handles__ = [('POSIXUser', None),
                   ('POSIXGroup', None)]
    __req__ = dict(POSIXUser=['name'],
                   POSIXGroup=['name'])
    experimental = True

    #: A mapping of XML entry attributes to the indexes of
    #: corresponding values in the get{pw|gr}all data structures
    attr_mapping = dict(POSIXUser=dict(name=0, uid=2, gecos=4, home=5,
                                       shell=6),
                        POSIXGroup=dict(name=0, gid=2))

    #: A mapping that describes the attribute name of the id of a given
    #: user or group
    id_mapping = dict(POSIXUser="uid", POSIXGroup="gid")

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.Tool.__init__(self, logger, setup, config)
        self.set_defaults = dict(POSIXUser=self.populate_user_entry,
                                 POSIXGroup=lambda g: g)
        self.cmd = Executor(logger)
        self._existing = None
        self._whitelist = dict(POSIXUser=None, POSIXGroup=None)
        self._blacklist = dict(POSIXUser=None, POSIXGroup=None)
        if self.setup['posix_uid_whitelist']:
            self._whitelist['POSIXUser'] = \
                IDRangeSet(*self.setup['posix_uid_whitelist'])
        else:
            self._blacklist['POSIXUser'] = \
                IDRangeSet(*self.setup['posix_uid_blacklist'])
        if self.setup['posix_gid_whitelist']:
            self._whitelist['POSIXGroup'] = \
                IDRangeSet(*self.setup['posix_gid_whitelist'])
        else:
            self._blacklist['POSIXGroup'] = \
                IDRangeSet(*self.setup['posix_gid_blacklist'])

    @property
    def existing(self):
        """ Get a dict of existing users and groups """
        if self._existing is None:
            self._existing = dict(POSIXUser=dict([(u[0], u)
                                                  for u in pwd.getpwall()]),
                                  POSIXGroup=dict([(g[0], g)
                                                   for g in grp.getgrall()]))
        return self._existing

    def _in_managed_range(self, tag, eid):
        """ Check if the given uid or gid is in the appropriate
        managed range.  This means that either a) a whitelist is
        defined, and the uid/gid is in that whitelist; or b) no
        whitelist is defined, and the uid/gid is not in the
        blacklist. """
        if self._whitelist[tag] is None:
            return eid not in self._blacklist[tag]
        else:
            return eid in self._whitelist[tag]

    def canInstall(self, entry):
        if not Bcfg2.Client.Tools.Tool.canInstall(self, entry):
            return False
        eid = entry.get(self.id_mapping[entry.tag])
        if eid is not None and not self._in_managed_range(entry.tag, eid):
            if self._whitelist[entry.tag] is not None:
                err = "not in whitelist"
            else:  # blacklisted
                err = "in blacklist"
            self.logger.debug("%s: %s %s %s: %s" %
                              (self.primarykey(entry), err,
                               self.id_mapping[entry.tag], eid,
                               self._blacklist[entry.tag]))
            return False
        return True

    def Inventory(self, states, structures=None):
        if not structures:
            structures = self.config.getchildren()
        # we calculate a list of all POSIXUser and POSIXGroup entries,
        # and then add POSIXGroup entries that are required to create
        # the primary group for each user to the structures.  this is
        # sneaky and possibly evil, but it works great.
        groups = []
        for struct in structures:
            groups.extend([e.get("name")
                           for e in struct.findall("POSIXGroup")])
        for struct in structures:
            for entry in struct.findall("POSIXUser"):
                group = self.set_defaults[entry.tag](entry).get('group')
                if group and group not in groups:
                    self.logger.debug("POSIXUsers: Adding POSIXGroup entry "
                                      "'%s' for user '%s'" %
                                      (group, entry.get("name")))
                    struct.append(Bcfg2.Client.XML.Element("POSIXGroup",
                                                           name=group))
        return Bcfg2.Client.Tools.Tool.Inventory(self, states, structures)

    def FindExtra(self):
        extra = []
        for handles in self.__handles__:
            tag = handles[0]
            specified = []
            for entry in self.getSupportedEntries():
                if entry.tag == tag:
                    specified.append(entry.get("name"))
            for name, data in self.existing[tag].items():
                eid = data[self.attr_mapping[tag][self.id_mapping[tag]]]
                if name not in specified and self._in_managed_range(tag, eid):
                    extra.append(Bcfg2.Client.XML.Element(tag, name=name))

        return extra

    def populate_user_entry(self, entry):
        """ Given a POSIXUser entry, set all of the 'missing' attributes
        with their defaults """
        defaults = dict(group=entry.get('name'),
                        gecos=entry.get('name'),
                        shell='/bin/bash')
        if entry.get('name') == 'root':
            defaults['home'] = '/root'
        else:
            defaults['home'] = '/home/%s' % entry.get('name')
        for key, val in defaults.items():
            if entry.get(key) is None:
                entry.set(key, val)
        if entry.get('group') in self.existing['POSIXGroup']:
            entry.set('gid',
                      str(self.existing['POSIXGroup'][entry.get('group')][2]))
        return entry

    def user_supplementary_groups(self, entry):
        """ Get a list of supplmentary groups that the user in the
        given entry is a member of """
        return [g for g in self.existing['POSIXGroup'].values()
                if entry.get("name") in g[3] and g[0] != entry.get("group")]

    def VerifyPOSIXUser(self, entry, _):
        """ Verify a POSIXUser entry """
        rv = self._verify(self.populate_user_entry(entry))
        if entry.get("current_exists", "true") == "true":
            # verify supplemental groups
            actual = [g[0] for g in self.user_supplementary_groups(entry)]
            expected = [e.text for e in entry.findall("MemberOf")]
            if set(expected) != set(actual):
                entry.set('qtext',
                          "\n".join([entry.get('qtext', '')] +
                                    ["%s %s has incorrect supplemental group "
                                     "membership. Currently: %s. Should be: %s"
                                     % (entry.tag, entry.get("name"),
                                        actual, expected)]))
                rv = False
        if self.setup['interactive'] and not rv:
            entry.set('qtext',
                      '%s\nInstall %s %s: (y/N) ' %
                      (entry.get('qtext', ''), entry.tag, entry.get('name')))
        return rv

    def VerifyPOSIXGroup(self, entry, _):
        """ Verify a POSIXGroup entry """
        rv = self._verify(entry)
        if self.setup['interactive'] and not rv:
            entry.set('qtext',
                      '%s\nInstall %s %s: (y/N) ' %
                      (entry.get('qtext', ''), entry.tag, entry.get('name')))
        return rv

    def _verify(self, entry):
        """ Perform most of the actual work of verification """
        errors = []
        if entry.get("name") not in self.existing[entry.tag]:
            entry.set('current_exists', 'false')
            errors.append("%s %s does not exist" % (entry.tag,
                                                    entry.get("name")))
        else:
            for attr, idx in self.attr_mapping[entry.tag].items():
                val = str(self.existing[entry.tag][entry.get("name")][idx])
                entry.set("current_%s" % attr, val)
                if attr in ["uid", "gid"]:
                    if entry.get(attr) is None:
                        # no uid/gid specified, so we let the tool
                        # automatically determine one -- i.e., it always
                        # verifies
                        continue
                if val != entry.get(attr):
                    errors.append("%s for %s %s is incorrect.  Current %s is "
                                  "%s, but should be %s" %
                                  (attr.title(), entry.tag, entry.get("name"),
                                   attr, val, entry.get(attr)))

        if errors:
            for error in errors:
                self.logger.debug("%s: %s" % (self.name, error))
            entry.set('qtext', "\n".join([entry.get('qtext', '')] + errors))
        return len(errors) == 0

    def Install(self, entries, states):
        for entry in entries:
            # install groups first, so that all groups exist for
            # users that might need them
            if entry.tag == 'POSIXGroup':
                states[entry] = self._install(entry)
        for entry in entries:
            if entry.tag == 'POSIXUser':
                states[entry] = self._install(entry)
        self._existing = None

    def _install(self, entry):
        """ add or modify a user or group using the appropriate command """
        if entry.get("name") not in self.existing[entry.tag]:
            action = "add"
        else:
            action = "mod"
        try:
            self.cmd.run(self._get_cmd(action,
                                       self.set_defaults[entry.tag](entry)))
            self.modified.append(entry)
            return True
        except ExecutionError:
            self.logger.error("POSIXUsers: Error creating %s %s: %s" %
                              (entry.tag, entry.get("name"),
                               sys.exc_info()[1]))
            return False

    def _get_cmd(self, action, entry):
        """ Get a command to perform the appropriate action (add, mod,
        del) on the given entry.  The command is always the same; we
        set all attributes on a given user or group when modifying it
        rather than checking which ones need to be changed.  This
        makes things fail as a unit (e.g., if a user is logged in, you
        can't change its home dir, but you could change its GECOS, but
        the whole operation fails), but it also makes this function a
        lot, lot easier and simpler."""
        cmd = ["/usr/sbin/%s%s" % (entry.tag[5:].lower(), action)]
        if action != 'del':
            if entry.tag == 'POSIXGroup':
                if entry.get('gid'):
                    cmd.extend(['-g', entry.get('gid')])
            elif entry.tag == 'POSIXUser':
                cmd.append('-m')
                if entry.get('uid'):
                    cmd.extend(['-u', entry.get('uid')])
                cmd.extend(['-g', entry.get('group')])
                extras = [e.text for e in entry.findall("MemberOf")]
                if extras:
                    cmd.extend(['-G', ",".join(extras)])
                cmd.extend(['-d', entry.get('home')])
                cmd.extend(['-s', entry.get('shell')])
                cmd.extend(['-c', entry.get('gecos')])
        cmd.append(entry.get('name'))
        return cmd

    def Remove(self, entries):
        for entry in entries:
            # remove users first, so that all users have been removed
            # from groups before we remove them
            if entry.tag == 'POSIXUser':
                self._remove(entry)
        for entry in entries:
            if entry.tag == 'POSIXGroup':
                try:
                    grp.getgrnam(entry.get("name"))
                    self._remove(entry)
                except KeyError:
                    # at least some versions of userdel automatically
                    # remove the primary group for a user if the group
                    # name is the same as the username, and no other
                    # users are in the group
                    self.logger.info("POSIXUsers: Group %s does not exist. "
                                     "It may have already been removed when "
                                     "its users were deleted" %
                                     entry.get("name"))
        self._existing = None
        self.extra = self.FindExtra()

    def _remove(self, entry):
        """ Remove an entry """
        try:
            self.cmd.run(self._get_cmd("del", entry))
            return True
        except ExecutionError:
            self.logger.error("POSIXUsers: Error deleting %s %s: %s" %
                              (entry.tag, entry.get("name"),
                               sys.exc_info()[1]))
            return False
