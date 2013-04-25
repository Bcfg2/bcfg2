""" Classes for SELinux entry support """

import os
import re
import sys
import copy
import glob
import struct
import socket
import selinux
import seobject
import Bcfg2.Client.XML
import Bcfg2.Client.Tools
from Bcfg2.Client.Tools.POSIX.File import POSIXFile
from Bcfg2.Compat import long  # pylint: disable=W0622


def pack128(int_val):
    """ pack a 128-bit integer in big-endian format """
    max_word_size = 2 ** 32 - 1

    if int_val <= max_word_size:
        return struct.pack('>L', int_val)

    words = []
    for i in range(4):  # pylint: disable=W0612
        word = int_val & max_word_size
        words.append(int(word))
        int_val >>= 32
    words.reverse()
    return struct.pack('>4I', *words)


def netmask_itoa(netmask, proto="ipv4"):
    """ convert an integer netmask (e.g., /16) to dotted-quad
    notation (255.255.0.0) or IPv6 prefix notation (ffff::) """
    if proto == "ipv4":
        size = 32
        family = socket.AF_INET
    else:  # ipv6
        size = 128
        family = socket.AF_INET6
    try:
        netmask = int(netmask)
    except ValueError:
        return netmask

    if netmask > size:
        raise ValueError("Netmask too large: %s" % netmask)

    res = long(0)
    for i in range(netmask):
        res |= 1 << (size - i - 1)
    netmask = socket.inet_ntop(family, pack128(res))
    return netmask


class SELinux(Bcfg2.Client.Tools.Tool):
    """ SELinux entry support """
    name = 'SELinux'
    __handles__ = [('SEBoolean', None),
                   ('SEFcontext', None),
                   ('SEInterface', None),
                   ('SELogin', None),
                   ('SEModule', None),
                   ('SENode', None),
                   ('SEPermissive', None),
                   ('SEPort', None),
                   ('SEUser', None)]
    __req__ = dict(SEBoolean=['name', 'value'],
                   SEFcontext=['name', 'selinuxtype'],
                   SEInterface=['name', 'selinuxtype'],
                   SELogin=['name', 'selinuxuser'],
                   SEModule=['name'],
                   SENode=['name', 'selinuxtype', 'proto'],
                   SEPermissive=['name'],
                   SEPort=['name', 'selinuxtype'],
                   SEUser=['name', 'roles', 'prefix'])

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.Tool.__init__(self, logger, setup, config)
        self.handlers = {}
        for handler in self.__handles__:
            etype = handler[0]
            self.handlers[etype] = \
                globals()["SELinux%sHandler" % etype.title()](self, logger,
                                                              setup, config)
        self.txn = False
        self.post_txn_queue = []

    def __getattr__(self, attr):
        if attr.startswith("VerifySE"):
            return self.GenericSEVerify
        elif attr.startswith("InstallSE"):
            return self.GenericSEInstall
        # there's no need for an else here, because python checks for
        # an attribute in the "normal" ways first.  i.e., if self.txn
        # is used, __getattr__() is never called because txn exists as
        # a "normal" attribute of this object.  See
        # http://docs.python.org/2/reference/datamodel.html#object.__getattr__
        # for details

    def BundleUpdated(self, _, states):
        for handler in self.handlers.values():
            handler.BundleUpdated(states)

    def FindExtra(self):
        extra = []
        for handler in self.handlers.values():
            extra.extend(handler.FindExtra())
        return extra

    def canInstall(self, entry):
        return (Bcfg2.Client.Tools.Tool.canInstall(self, entry) and
                self.handlers[entry.tag].canInstall(entry))

    def primarykey(self, entry):
        """ return a string that should be unique amongst all entries
        in the specification """
        return self.handlers[entry.tag].primarykey(entry)

    def Install(self, entries, states):
        # start a transaction
        semanage = seobject.semanageRecords("")
        if hasattr(semanage, "start"):
            self.logger.debug("Starting SELinux transaction")
            semanage.start()
            self.txn = True
        else:
            self.logger.debug("SELinux transactions not supported; this may "
                              "slow things down considerably")
        Bcfg2.Client.Tools.Tool.Install(self, entries, states)
        if hasattr(semanage, "finish"):
            self.logger.debug("Committing SELinux transaction")
            semanage.finish()
            self.txn = False
            for func, arg, kwargs in self.post_txn_queue:
                states[arg] = func(*arg, **kwargs)

    def GenericSEInstall(self, entry):
        """Dispatch install to the proper method according to entry tag"""
        return self.handlers[entry.tag].Install(entry)

    def GenericSEVerify(self, entry, _):
        """Dispatch verify to the proper method according to entry tag"""
        rv = self.handlers[entry.tag].Verify(entry)
        if entry.get('qtext') and self.setup['interactive']:
            entry.set('qtext',
                      '%s\nInstall %s: (y/N) ' %
                      (entry.get('qtext'),
                       self.handlers[entry.tag].tostring(entry)))
        return rv

    def Remove(self, entries):
        """Dispatch verify to the proper removal
        method according to entry tag"""
        # sort by type
        types = list()
        for entry in entries:
            if entry.tag not in types:
                types.append(entry.tag)

        for etype in types:
            self.handlers[etype].Remove([e for e in entries
                                         if e.tag == etype])


class SELinuxEntryHandler(object):
    """ Generic handler for all SELinux entries """
    etype = None
    key_format = ("name",)
    value_format = ()
    str_format = '%(name)s'
    custom_re = re.compile(r' (?P<name>\S+)$')
    custom_format = None

    def __init__(self, tool, logger, setup, config):
        self.tool = tool
        self.logger = logger
        self.setup = setup
        self.config = config
        self._records = None
        self._all = None
        if not self.custom_format:
            self.custom_format = self.key_format

    @property
    def records(self):
        """ return the records object for this entry type """
        if self._records is None:
            self._records = getattr(seobject, "%sRecords" % self.etype)("")
        return self._records

    @property
    def all_records(self):
        """ get a dict of all defined records for this entry type """
        if self._all is None:
            self._all = self.records.get_all()
        return self._all

    @property
    def custom_records(self):
        """ try to get a dict of all customized records for this entry
        type, if the records object supports the customized() method
        """
        if hasattr(self.records, "customized") and self.custom_re:
            rv = dict()
            for key in self.custom_keys:
                if key in self.all_records:
                    rv[key] = self.all_records[key]
                else:
                    self.logger.warning("SELinux %s %s customized, but no "
                                        "record found. This may indicate an "
                                        "error in your SELinux policy." %
                                        (self.etype, key))
            return rv
        else:
            # ValueError is really a pretty dumb exception to raise,
            # but that's what the seobject customized() method raises
            # if it's defined but not implemented.  yeah, i know, wtf.
            raise ValueError("custom_records")

    @property
    def custom_keys(self):
        """ get a list of keys for selinux records of this entry type
        that have been customized """
        keys = []
        for cmd in self.records.customized():
            match = self.custom_re.search(cmd)
            if match:
                if (len(self.custom_format) == 1 and
                    self.custom_format[0] == "name"):
                    keys.append(match.group("name"))
                else:
                    keys.append(tuple([match.group(k)
                                       for k in self.custom_format]))
        return keys

    def tostring(self, entry):
        """ transform an XML SELinux entry into a human-readable
        string """
        return self.str_format % entry.attrib

    def keytostring(self, key):
        """ transform a SELinux record key into a human-readable
        string """
        return self.str_format % self._key2attrs(key)

    def _key(self, entry):
        """ Generate an SELinux record key from an XML SELinux entry """
        if len(self.key_format) == 1 and self.key_format[0] == "name":
            return entry.get("name")
        else:
            rv = []
            for key in self.key_format:
                rv.append(entry.get(key))
            return tuple(rv)

    def _key2attrs(self, key):
        """ Generate an XML attribute dict from an SELinux record key """
        if isinstance(key, tuple):
            rv = dict((self.key_format[i], key[i])
                      for i in range(len(self.key_format))
                      if self.key_format[i])
        else:
            rv = dict(name=key)
        if self.value_format:
            vals = self.all_records[key]
            rv.update(dict((self.value_format[i], vals[i])
                           for i in range(len(self.value_format))
                           if self.value_format[i]))
        return rv

    def key2entry(self, key):
        """ Generate an XML entry from an SELinux record key """
        attrs = self._key2attrs(key)
        return Bcfg2.Client.XML.Element("SE%s" % self.etype.title(), **attrs)

    def _args(self, entry, method):
        """ Get the argument list for invoking _modify or _add, or
        _delete methods """
        if hasattr(self, "_%sargs" % method):
            return getattr(self, "_%sargs" % method)(entry)
        elif hasattr(self, "_defaultargs"):
            # default args
            return self._defaultargs(entry)  # pylint: disable=E1101
        else:
            raise NotImplementedError

    def _deleteargs(self, entry):
        """ Get the argument list for invoking delete methods """
        return (self._key(entry))

    def canInstall(self, entry):
        """ return True if this entry is complete and can be installed """
        return bool(self._key(entry))

    def primarykey(self, entry):
        """ return a string that should be unique amongst all entries
        in the specification.  some entry types are not universally
        disambiguated by tag:type:name alone """
        return ":".join([entry.tag, entry.get("name")])

    def exists(self, entry):
        """ return True if the entry already exists in the record list """
        if self._key(entry) not in self.all_records:
            self.logger.debug("SELinux %s %s does not exist" %
                              (self.etype, self.tostring(entry)))
            return False
        return True

    def Verify(self, entry):
        """ verify that the entry is correct on the client system """
        if not self.exists(entry):
            entry.set('current_exists', 'false')
            return False

        errors = []
        current_attrs = self._key2attrs(self._key(entry))
        desired_attrs = entry.attrib
        for attr in self.value_format:
            if not attr:
                continue
            if current_attrs[attr] != desired_attrs[attr]:
                entry.set('current_%s' % attr, current_attrs[attr])
                errors.append("%s %s has wrong %s: %s, should be %s" %
                              (entry.tag, entry.get('name'), attr,
                               current_attrs[attr], desired_attrs[attr]))

        if errors:
            for error in errors:
                self.logger.debug(error)
            entry.set('qtext', "\n".join([entry.get('qtext', '')] + errors))
            return False
        else:
            return True

    def Install(self, entry, method=None):
        """ install the entry on the client system """
        if not method:
            if self.exists(entry):
                method = "modify"
            else:
                method = "add"
        self.logger.debug("%s SELinux %s %s" %
                          (method.title(), self.etype, self.tostring(entry)))

        try:
            getattr(self.records, method)(*self._args(entry, method))
            self._all = None
            return True
        except ValueError:
            err = sys.exc_info()[1]
            self.logger.info("Failed to %s SELinux %s %s: %s" %
                             (method, self.etype, self.tostring(entry), err))
            return False

    def Remove(self, entries):
        """ remove the entry from the client system """
        for entry in entries:
            try:
                self.records.delete(*self._args(entry, "delete"))
                self._all = None
            except ValueError:
                err = sys.exc_info()[1]
                self.logger.info("Failed to remove SELinux %s %s: %s" %
                                 (self.etype, self.tostring(entry), err))

    def FindExtra(self):
        """ find extra entries of this entry type """
        specified = [self._key(e)
                     for e in self.tool.getSupportedEntries()
                     if e.tag == "SE%s" % self.etype.title()]
        try:
            records = self.custom_records
        except ValueError:
            records = self.all_records
        return [self.key2entry(key)
                for key in records.keys()
                if key not in specified]

    def BundleUpdated(self, states):
        """ perform any additional magic tasks that need to be run
        when a bundle is updated """
        pass


class SELinuxSebooleanHandler(SELinuxEntryHandler):
    """ handle SELinux boolean entries """
    etype = "boolean"
    value_format = ("value",)

    @property
    def all_records(self):
        # older versions of selinux return a single 0/1 value for each
        # bool, while newer versions return a list of three 0/1 values
        # representing various states. we don't care about the latter
        # two values, but it's easier to coerce the older format into
        # the newer format as far as interoperation with the rest of
        # SELinuxEntryHandler goes
        rv = SELinuxEntryHandler.all_records.fget(self)
        if rv.values()[0] in [0, 1]:
            for key, val in rv.items():
                rv[key] = [val, val, val]
        return rv

    def _key2attrs(self, key):
        rv = SELinuxEntryHandler._key2attrs(self, key)
        status = self.all_records[key][0]
        if status:
            rv['value'] = "on"
        else:
            rv['value'] = "off"
        return rv

    def _defaultargs(self, entry):
        """ argument list for adding, modifying and deleting entries """
        # the only values recognized by both new and old versions of
        # selinux are the strings "0" and "1".  old selinux accepts
        # ints or bools as well, new selinux accepts "on"/"off"
        if entry.get("value").lower() == "on":
            value = "1"
        else:
            value = "0"
        return (entry.get("name"), value)

    def canInstall(self, entry):
        if entry.get("value").lower() not in ["on", "off"]:
            self.logger.debug("SELinux %s %s has a bad value: %s" %
                              (self.etype, self.tostring(entry),
                               entry.get("value")))
            return False
        return (self.exists(entry) and
                SELinuxEntryHandler.canInstall(self, entry))


class SELinuxSeportHandler(SELinuxEntryHandler):
    """ handle SELinux port entries """
    etype = "port"
    value_format = ('selinuxtype', None)
    custom_re = re.compile(r'-p (?P<proto>tcp|udp).*? '
                           r'(?P<start>\d+)(?:-(?P<end>\d+))?$')

    @property
    def custom_keys(self):
        keys = []
        for cmd in self.records.customized():
            match = self.custom_re.search(cmd)
            if match:
                if match.group('end'):
                    keys.append((int(match.group('start')),
                                 int(match.group('end')),
                                 match.group('proto')))
                else:
                    keys.append((int(match.group('start')),
                                 int(match.group('start')),
                                 match.group('proto')))
        return keys

    @property
    def all_records(self):
        if self._all is None:
            # older versions of selinux use (startport, endport) as
            # they key for the ports.get_all() dict, and (type, proto,
            # level) as the value; this is obviously broken, so newer
            # versions use (startport, endport, proto) as the key, and
            # (type, level) as the value.  abstracting around this
            # sucks.
            ports = self.records.get_all()
            if len(ports.keys()[0]) == 3:
                self._all = ports
            else:
                # uglist list comprehension ever?
                self._all = dict([((k[0], k[1], v[1]), (v[0], v[2]))
                                  for k, v in ports.items()])
        return self._all

    def _key(self, entry):
        try:
            (port, proto) = entry.get("name").split("/")
        except ValueError:
            self.logger.error("Invalid SELinux node %s: no protocol specified"
                              % entry.get("name"))
            return
        if "-" in port:
            start, end = port.split("-")
        else:
            start = port
            end = port
        return (int(start), int(end), proto)

    def _key2attrs(self, key):
        if key[0] == key[1]:
            port = str(key[0])
        else:
            port = "%s-%s" % (key[0], key[1])
        vals = self.all_records[key]
        return dict(name="%s/%s" % (port, key[2]), selinuxtype=vals[0])

    def _defaultargs(self, entry):
        """ argument list for adding and modifying entries """
        (port, proto) = entry.get("name").split("/")
        return (port, proto, entry.get("mlsrange", ""),
                entry.get("selinuxtype"))

    def _deleteargs(self, entry):
        return tuple(entry.get("name").split("/"))


class SELinuxSefcontextHandler(SELinuxEntryHandler):
    """ handle SELinux file context entries """

    etype = "fcontext"
    key_format = ("name", "filetype")
    value_format = (None, None, "selinuxtype", None)
    filetypeargs = dict(all="",
                        regular="--",
                        directory="-d",
                        symlink="-l",
                        pipe="-p",
                        socket="-s",
                        block="-b",
                        char="-c",
                        door="-D")
    filetypenames = dict(all="all files",
                         regular="regular file",
                         directory="directory",
                         symlink="symbolic link",
                         pipe="named pipe",
                         socket="socket",
                         block="block device",
                         char="character device",
                         door="door")
    filetypeattrs = dict([v, k] for k, v in filetypenames.iteritems())
    custom_re = re.compile(r'-f \'(?P<filetype>[a-z ]+)\'.*? \'(?P<name>.*)\'')

    @property
    def all_records(self):
        if self._all is None:
            # on older selinux, fcontextRecords.get_all() returns a
            # list of tuples of (filespec, filetype, seuser, serole,
            # setype, level); on newer selinux, get_all() returns a
            # dict of (filespec, filetype) => (seuser, serole, setype,
            # level).
            fcontexts = self.records.get_all()
            if isinstance(fcontexts, dict):
                self._all = fcontexts
            else:
                self._all = dict([(f[0:2], f[2:]) for f in fcontexts])
        return self._all

    def _key(self, entry):
        ftype = entry.get("filetype", "all")
        return (entry.get("name"),
                self.filetypenames.get(ftype, ftype))

    def _key2attrs(self, key):
        rv = dict(name=key[0], filetype=self.filetypeattrs[key[1]])
        vals = self.all_records[key]
        # in older versions of selinux, an fcontext with no selinux
        # type is the single value None; in newer versions, it's a
        # tuple whose 0th (and only) value is None.
        if vals and vals[0]:
            rv["selinuxtype"] = vals[2]
        else:
            rv["selinuxtype"] = "<<none>>"
        return rv

    def canInstall(self, entry):
        return (entry.get("filetype", "all") in self.filetypeargs and
                SELinuxEntryHandler.canInstall(self, entry))

    def _defaultargs(self, entry):
        """ argument list for adding, modifying, and deleting entries """
        return (entry.get("name"), entry.get("selinuxtype"),
                self.filetypeargs[entry.get("filetype", "all")],
                entry.get("mlsrange", ""), '')

    def primarykey(self, entry):
        return ":".join([entry.tag, entry.get("name"),
                         entry.get("filetype", "all")])


class SELinuxSenodeHandler(SELinuxEntryHandler):
    """ handle SELinux node entries """

    etype = "node"
    value_format = (None, None, "selinuxtype", None)
    str_format = '%(name)s (%(proto)s)'
    custom_re = re.compile(r'-M (?P<netmask>\S+).*?'
                           r'-p (?P<proto>ipv\d).*? (?P<addr>\S+)$')
    custom_format = ('addr', 'netmask', 'proto')

    def _key(self, entry):
        try:
            (addr, netmask) = entry.get("name").split("/")
        except ValueError:
            self.logger.error("Invalid SELinux node %s: no netmask specified" %
                              entry.get("name"))
            return
        netmask = netmask_itoa(netmask, proto=entry.get("proto"))
        return (addr, netmask, entry.get("proto"))

    def _key2attrs(self, key):
        vals = self.all_records[key]
        return dict(name="%s/%s" % (key[0], key[1]), proto=key[2],
                    selinuxtype=vals[2])

    def _defaultargs(self, entry):
        """ argument list for adding, modifying, and deleting entries """
        (addr, netmask) = entry.get("name").split("/")
        return (addr, netmask, entry.get("proto"), entry.get("mlsrange", ""),
                entry.get("selinuxtype"))


class SELinuxSeloginHandler(SELinuxEntryHandler):
    """ handle SELinux login entries """

    etype = "login"
    value_format = ("selinuxuser", None)

    def _defaultargs(self, entry):
        """ argument list for adding, modifying, and deleting entries """
        return (entry.get("name"), entry.get("selinuxuser"),
                entry.get("mlsrange", ""))


class SELinuxSeuserHandler(SELinuxEntryHandler):
    """ handle SELinux user entries """

    etype = "user"
    value_format = ("prefix", None, None, "roles")

    def __init__(self, tool, logger, setup, config):
        SELinuxEntryHandler.__init__(self, tool, logger, setup, config)
        self.needs_prefix = False

    @property
    def records(self):
        if self._records is None:
            self._records = seobject.seluserRecords()
        return self._records

    def Install(self, entry, method=None):
        # in older versions of selinux, modify() is broken if you
        # provide a prefix _at all_, so we try to avoid giving the
        # prefix.  however, in newer versions, prefix is _required_,
        # so we a) try without a prefix; b) catch TypeError, which
        # indicates that we had the wrong number of args (ValueError
        # is thrown by the bug in older versions of selinux); and c)
        # try with prefix.
        try:
            SELinuxEntryHandler.Install(self, entry, method=method)
        except TypeError:
            self.needs_prefix = True
            SELinuxEntryHandler.Install(self, entry, method=method)

    def _defaultargs(self, entry):
        """ argument list for adding, modifying, and deleting entries """
        # in older versions of selinux, modify() is broken if you
        # provide a prefix _at all_, so we try to avoid giving the
        # prefix.  see the comment in Install() above for more
        # details.
        rv = [entry.get("name"),
              entry.get("roles", "").replace(" ", ",").split(","),
              '', entry.get("mlsrange", "")]
        if self.needs_prefix:
            rv.append(entry.get("prefix"))
        else:
            key = self._key(entry)
            if key in self.all_records:
                attrs = self._key2attrs(key)
                if attrs['prefix'] != entry.get("prefix"):
                    rv.append(entry.get("prefix"))
        return tuple(rv)


class SELinuxSeinterfaceHandler(SELinuxEntryHandler):
    """ handle SELinux interface entries """

    etype = "interface"
    value_format = (None, None, "selinuxtype", None)

    def _defaultargs(self, entry):
        """ argument list for adding, modifying, and deleting entries """
        return (entry.get("name"), entry.get("mlsrange", ""),
                entry.get("selinuxtype"))


class SELinuxSepermissiveHandler(SELinuxEntryHandler):
    """ handle SELinux permissive domain entries """

    etype = "permissive"

    @property
    def records(self):
        try:
            return SELinuxEntryHandler.records.fget(self)
        except AttributeError:
            self.logger.info("Permissive domains not supported by this "
                             "version of SELinux")
            self._records = None
            return self._records

    @property
    def all_records(self):
        if self._all is None:
            if self.records is None:
                self._all = dict()
            else:
                # permissiveRecords.get_all() returns a list, so we just
                # make it into a dict so that the rest of
                # SELinuxEntryHandler works
                self._all = dict([(d, d) for d in self.records.get_all()])
        return self._all

    def _defaultargs(self, entry):
        """ argument list for adding, modifying, and deleting entries """
        return (entry.get("name"),)


class SELinuxSemoduleHandler(SELinuxEntryHandler):
    """ handle SELinux module entries """

    etype = "module"
    value_format = (None, "disabled")

    def __init__(self, tool, logger, setup, config):
        SELinuxEntryHandler.__init__(self, tool, logger, setup, config)
        self.filetool = POSIXFile(logger, setup, config)
        try:
            self.setype = selinux.selinux_getpolicytype()[1]
        except IndexError:
            self.logger.error("Unable to determine SELinux policy type")
            self.setype = None

    @property
    def all_records(self):
        if self._all is None:
            try:
                # we get a list of tuples back; coerce it into a dict
                self._all = dict([(m[0], (m[1], m[2]))
                                  for m in self.records.get_all()])
            except AttributeError:
                # early versions of seobject don't have moduleRecords,
                # so we parse the output of `semodule` >_<
                self._all = dict()
                self.logger.debug("SELinux: Getting modules from semodule")
                try:
                    rv = self.tool.cmd.run(['semodule', '-l'])
                except OSError:
                    # semanage failed; probably not in $PATH.  try to
                    # get the list of modules from the filesystem
                    err = sys.exc_info()[1]
                    self.logger.debug("SELinux: Failed to run semodule: %s" %
                                      err)
                    self._all.update(self._all_records_from_filesystem())
                else:
                    if rv.success:
                        # ran semodule successfully
                        for line in rv.stdout.splitlines():
                            mod, version = line.split()
                            self._all[mod] = (version, 1)

                        # get other (disabled) modules from the filesystem
                        for mod in self._all_records_from_filesystem().keys():
                            if mod not in self._all:
                                self._all[mod] = ('', 0)
                    else:
                        self.logger.error("SELinux: Failed to run semodule: %s"
                                          % rv.error)
                        self._all.update(self._all_records_from_filesystem())
        return self._all

    def _all_records_from_filesystem(self):
        """ the seobject API doesn't support modules and semodule is
        broken or missing, so just list modules on the filesystem.
        this is terrible. """
        self.logger.debug("SELinux: Getting modules from filesystem")
        rv = dict()
        for mod in glob.glob(os.path.join("/usr/share/selinux", self.setype,
                                          "*.pp")):
            rv[os.path.basename(mod)[:-3]] = ('', 1)
        return rv

    def _key(self, entry):
        name = entry.get("name").lstrip("/")
        if name.endswith(".pp"):
            return name[:-3]
        else:
            return name

    def _key2attrs(self, key):
        rv = SELinuxEntryHandler._key2attrs(self, key)
        status = self.all_records[key][1]
        if status:
            rv['disabled'] = "false"
        else:
            rv['disabled'] = "true"
        return rv

    def _filepath(self, entry):
        """ get the path to the .pp module file for this module entry
        """
        return os.path.join("/usr/share/selinux", self.setype,
                            entry.get("name") + '.pp')

    def _pathentry(self, entry):
        """ Get an XML Path entry based on this SELinux module entry,
        suitable for installing the module .pp file itself to the
        filesystem """
        pathentry = copy.deepcopy(entry)
        pathentry.set("name", self._filepath(pathentry))
        pathentry.set("mode", "0644")
        pathentry.set("owner", "root")
        pathentry.set("group", "root")
        pathentry.set("secontext", "__default__")
        return pathentry

    def Verify(self, entry):
        if not entry.get("disabled"):
            entry.set("disabled", "false")
        return (SELinuxEntryHandler.Verify(self, entry) and
                self.filetool.verify(self._pathentry(entry), []))

    def canInstall(self, entry):
        return (entry.text and self.setype and
                SELinuxEntryHandler.canInstall(self, entry))

    def Install(self, entry, _=None):
        if not self.filetool.install(self._pathentry(entry)):
            return False
        if hasattr(seobject, 'moduleRecords'):
            # if seobject has the moduleRecords attribute, install the
            # module using the seobject library
            return self._install_seobject(entry)
        else:
            # seobject doesn't have the moduleRecords attribute, so
            # install the module using `semodule`
            self.logger.debug("Installing %s using semodule" %
                              entry.get("name"))
            self._all = None
            return self._install_semodule(entry)

    def _install_seobject(self, entry):
        """ Install an SELinux module using the seobject library """
        try:
            if not SELinuxEntryHandler.Install(self, entry):
                return False
        except NameError:
            # some versions of selinux have a bug in seobject that
            # makes modify() calls fail.  add() seems to have the same
            # effect as modify, but without the bug
            if self.exists(entry):
                if not SELinuxEntryHandler.Install(self, entry, method="add"):
                    return False

        if entry.get("disabled", "false").lower() == "true":
            method = "disable"
        else:
            method = "enable"
        return SELinuxEntryHandler.Install(self, entry, method=method)

    def _install_semodule(self, entry, fromqueue=False):
        """ Install an SELinux module using the semodule command """
        if fromqueue:
            self.logger.debug("Installing SELinux module %s from "
                              "post-transaction queue" % entry.get("name"))
        elif self.tool.txn:
            # we've started a transaction, so if we run semodule -i
            # then it'll fail with lock errors.  so we add this
            # installation to a queue to be run after the transaction
            # is closed.
            self.logger.debug("Waiting to install SELinux module %s until "
                              "SELinux transaction is finished" %
                              entry.get('name'))
            self.tool.post_txn_queue.append((self._install_semodule,
                                             (entry,),
                                             dict(fromqueue=True)))
            return False
        self.logger.debug("Install SELinux module %s with semodule -i %s" %
                          (entry.get('name'), self._filepath(entry)))
        try:
            rv = self.tool.cmd.run(['semodule', '-i', self._filepath(entry)])
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("Failed to install SELinux module %s with "
                              "semodule: %s" % (entry.get("name"), err))
            return False
        if rv.success:
            if entry.get("disabled", "false").lower() == "true":
                self.logger.warning("SELinux: Cannot disable modules with "
                                    "semodule")
                return False
            else:
                return True
        else:
            self.logger.error("Failed to install SELinux module %s with "
                              "semodule: %s" % (entry.get("name"), rv.error))
            return False

    def _addargs(self, entry):
        """ argument list for adding entries """
        return (self._filepath(entry),)

    def _defaultargs(self, entry):
        """ argument list for modifying and deleting entries """
        return (entry.get("name"),)

    def FindExtra(self):
        specified = [self._key(e)
                     for e in self.tool.getSupportedEntries()]
        rv = []
        for module in self._all_records_from_filesystem().keys():
            if module not in specified:
                rv.append(self.key2entry(module))
        return rv
