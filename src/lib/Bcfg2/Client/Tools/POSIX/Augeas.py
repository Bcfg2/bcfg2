""" Augeas driver """

import sys
import Bcfg2.Client.XML
from augeas import Augeas
from Bcfg2.Client.Tools.POSIX.base import POSIXTool
from Bcfg2.Client.Tools.POSIX.File import POSIXFile


class AugeasCommand(object):
    """ Base class for all Augeas command objects """

    def __init__(self, command, augeas_obj, logger):
        self._augeas = augeas_obj
        self.command = command
        self.entry = self.command.getparent()
        self.logger = logger

    def get_path(self, attr="path"):
        """ Get a fully qualified path from the name of the parent entry and
        the path given in this command tag.

        @param attr: The attribute to get the relative path from
        @type attr: string
        @returns: string - the fully qualified Augeas path

        """
        return "/files/%s/%s" % (self.entry.get("name").strip("/"),
                                 self.command.get(attr).lstrip("/"))

    def _exists(self, path):
        """ Return True if a path exists in Augeas, False otherwise.

        Note that a False return can mean many things: A file that
        doesn't exist, a node within the file that doesn't exist, no
        lens to parse the file, etc. """
        return len(self._augeas.match(path)) > 1

    def _verify_exists(self, path=None):
        """ Verify that the given path exists, with friendly debug
        logging.

        @param path: The path to verify existence of.  Defaults to the
                     result of
                     :func:`Bcfg2.Client.Tools.POSIX.Augeas.AugeasCommand.getpath`.
        @type path: string
        @returns: bool - Whether or not the path exists
        """
        if path is None:
            path = self.get_path()
        self.logger.debug("Augeas: Verifying that '%s' exists" % path)
        return self._exists(path)

    def _verify_not_exists(self, path=None):
        """ Verify that the given path does not exist, with friendly
        debug logging.

        @param path: The path to verify existence of.  Defaults to the
                     result of
                     :func:`Bcfg2.Client.Tools.POSIX.Augeas.AugeasCommand.getpath`.
        @type path: string
        @returns: bool - Whether or not the path does not exist.
                  (I.e., True if it does not exist, False if it does
                  exist.)
        """
        if path is None:
            path = self.get_path()
        self.logger.debug("Augeas: Verifying that '%s' does not exist" % path)
        return not self._exists(path)

    def _verify_set(self, expected, path=None):
        """ Verify that the given path is set to the given value, with
        friendly debug logging.

        @param expected: The expected value of the node.
        @param path: The path to verify existence of.  Defaults to the
                     result of
                     :func:`Bcfg2.Client.Tools.POSIX.Augeas.AugeasCommand.getpath`.
        @type path: string
        @returns: bool - Whether or not the path matches the expected value.

        """
        if path is None:
            path = self.get_path()
        self.logger.debug("Augeas: Verifying '%s' == '%s'" % (path, expected))
        actual = self._augeas.get(path)
        if actual == expected:
            return True
        else:
            self.logger.debug("Augeas: '%s' failed verification: '%s' != '%s'"
                              % (path, actual, expected))
            return False

    def __str__(self):
        return Bcfg2.Client.XML.tostring(self.command)

    def verify(self):
        """ Verify that the command has been applied. """
        raise NotImplementedError

    def install(self):
        """ Run the command. """
        raise NotImplementedError


class Remove(AugeasCommand):
    """ Augeas ``rm`` command """
    def verify(self):
        return self._verify_not_exists()

    def install(self):
        self.logger.debug("Augeas: Removing %s" % self.get_path())
        return self._augeas.remove(self.get_path())


class Move(AugeasCommand):
    """ Augeas ``move`` command """
    def __init__(self, command, augeas_obj, logger):
        AugeasCommand.__init__(self, command, augeas_obj, logger)
        self.source = self.get_path("source")
        self.dest = self.get_path("destination")

    def verify(self):
        return (self._verify_not_exists(self.source),
                self._verify_exists(self.dest))

    def install(self):
        self.logger.debug("Augeas: Moving %s to %s" % (self.source, self.dest))
        return self._augeas.move(self.source, self.dest)


class Set(AugeasCommand):
    """ Augeas ``set`` command """
    def __init__(self, command, augeas_obj, logger):
        AugeasCommand.__init__(self, command, augeas_obj, logger)
        self.value = self.command.get("value")

    def verify(self):
        return self._verify_set(self.value)

    def install(self):
        self.logger.debug("Augeas: Setting %s to %s" % (self.get_path(),
                                                        self.value))
        return self._augeas.set(self.get_path(), self.value)


class Clear(Set):
    """ Augeas ``clear`` command """
    def __init__(self, command, augeas_obj, logger):
        Set.__init__(self, command, augeas_obj, logger)
        self.value = None


class SetMulti(AugeasCommand):
    """ Augeas ``setm`` command """
    def __init__(self, command, augeas_obj, logger):
        AugeasCommand.__init__(self, command, augeas_obj, logger)
        self.sub = self.command.get("sub")
        self.value = self.command.get("value")
        self.base = self.get_path("base")

    def verify(self):
        return all(self._verify_set(self.value,
                                    path="%s/%s" % (path, self.sub))
                   for path in self._augeas.match(self.base))

    def install(self):
        return self._augeas.setm(self.base, self.sub, self.value)


class Insert(AugeasCommand):
    """ Augeas ``ins`` command """
    def __init__(self, command, augeas_obj, logger):
        AugeasCommand.__init__(self, command, augeas_obj, logger)
        self.label = self.command.get("label")
        self.where = self.command.get("where", "before")
        self.before = self.where == "before"

    def verify(self):
        return self._verify_exists("%s/../%s" % (self.get_path(), self.label))

    def install(self):
        self.logger.debug("Augeas: Inserting new %s %s %s" %
                          (self.label, self.where, self.get_path()))
        return self._augeas.insert(self.get_path(), self.label, self.before)


class POSIXAugeas(POSIXTool):
    """ Handle <Path type='augeas'...> entries.  See
    :ref:`client-tools-augeas`. """
    __req__ = ['name', 'mode', 'owner', 'group']

    def __init__(self, logger, setup, config):
        POSIXTool.__init__(self, logger, setup, config)
        self._augeas = dict()
        # file tool for setting initial values of files that don't
        # exist
        self.filetool = POSIXFile(logger, setup, config)

    def get_augeas(self, entry):
        """ Get an augeas object for the given entry. """
        if entry.get("name") not in self._augeas:
            aug = Augeas()
            if entry.get("lens"):
                self.logger.debug("Augeas: Adding %s to include path for %s" %
                                  (entry.get("name"), entry.get("lens")))
                incl = "/augeas/load/%s/incl" % entry.get("lens")
                ilen = len(aug.match(incl))
                if ilen == 0:
                    self.logger.error("Augeas: Lens %s does not exist" %
                                      entry.get("lens"))
                else:
                    aug.set("%s[%s]" % (incl, ilen + 1), entry.get("name"))
                    aug.load()
            self._augeas[entry.get("name")] = aug
        return self._augeas[entry.get("name")]

    def fully_specified(self, entry):
        return len(entry.getchildren()) != 0

    def get_commands(self, entry):
        """ Get a list of commands to verify or install.

        @param entry: The entry to get commands from.
        @type entry: lxml.etree._Element
        @param unverified: Only get commands that failed verification.
        @type unverified: bool
        @returns: list of
                  :class:`Bcfg2.Client.Tools.POSIX.Augeas.AugeasCommand`
                  objects representing the commands.
        """
        rv = []
        for cmd in entry.iterchildren():
            if cmd.tag == "Initial":
                continue
            if cmd.tag in globals():
                rv.append(globals()[cmd.tag](cmd, self.get_augeas(entry),
                                             self.logger))
            else:
                err = "Augeas: Unknown command %s in %s" % (cmd.tag,
                                                            entry.get("name"))
                self.logger.error(err)
                entry.set('qtext', "\n".join([entry.get('qtext', ''), err]))
        return rv

    def verify(self, entry, modlist):
        rv = True
        for cmd in self.get_commands(entry):
            try:
                if not cmd.verify():
                    err = "Augeas: Command has not been applied to %s: %s" % \
                          (entry.get("name"), cmd)
                    self.logger.debug(err)
                    entry.set('qtext', "\n".join([entry.get('qtext', ''),
                                                  err]))
                    rv = False
                    cmd.command.set("verified", "false")
                else:
                    cmd.command.set("verified", "true")
            except:  # pylint: disable=W0702
                err = "Augeas: Unexpected error verifying %s: %s: %s" % \
                      (entry.get("name"), cmd, sys.exc_info()[1])
                self.logger.error(err)
                entry.set('qtext', "\n".join([entry.get('qtext', ''), err]))
                rv = False
                cmd.command.set("verified", "false")
        return POSIXTool.verify(self, entry, modlist) and rv

    def install(self, entry):
        rv = True
        if entry.get("current_exists", "true") == "false":
            initial = entry.find("Initial")
            if initial is not None:
                self.logger.debug("Augeas: Setting initial data for %s" %
                                  entry.get("name"))
                file_entry = Bcfg2.Client.XML.Element("Path",
                                                      **dict(entry.attrib))
                file_entry.text = initial.text
                self.filetool.install(file_entry)
                # re-parse the file
                self.get_augeas(entry).load()
        for cmd in self.get_commands(entry):
            try:
                cmd.install()
            except:  # pylint: disable=W0702
                self.logger.error(
                    "Failure running Augeas command on %s: %s: %s" %
                    (entry.get("name"), cmd, sys.exc_info()[1]))
                rv = False
        try:
            self.get_augeas(entry).save()
        except:  # pylint: disable=W0702
            self.logger.error("Failure saving Augeas changes to %s: %s" %
                              (entry.get("name"), sys.exc_info()[1]))
            rv = False
        return POSIXTool.install(self, entry) and rv
