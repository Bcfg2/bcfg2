""" Miscellaneous useful utility functions, classes, etc., that are
used by both client and server.  Stuff that doesn't fit anywhere
else. """

import fcntl
import logging
import os
import re
import select
import shlex
import sys
import subprocess
import threading
from Bcfg2.Compat import input, any  # pylint: disable=W0622


class ClassName(object):
    """ This very simple descriptor class exists only to get the name
    of the owner class.  This is used because, for historical reasons,
    we expect every server plugin and every client tool to have a
    ``name`` attribute that is in almost all cases the same as the
    ``__class__.__name__`` attribute of the plugin object.  This makes
    that more dynamic so that each plugin and tool isn't repeating its own
    name."""

    def __get__(self, inst, owner):
        return owner.__name__


class PackedDigitRange(object):  # pylint: disable=E0012,R0924
    """ Representation of a set of integer ranges. A range is
    described by a comma-delimited string of integers and ranges,
    e.g.::

        1,10-12,15-20

    Ranges are inclusive on both bounds, and may include 0.  Negative
    numbers are not supported."""

    def __init__(self, *ranges):
        """ May be instantiated in one of two ways::

            PackedDigitRange(<comma-delimited list of ranges>)

        Or::

            PackedDigitRange(<int_or_range>[, <int_or_range>[, ...]])

        E.g., both of the following are valid::

            PackedDigitRange("1-5,7, 10-12")
            PackedDigitRange("1-5", 7, "10-12")
        """
        self.ranges = []
        self.ints = []
        self.str = ",".join(str(r) for r in ranges)
        if len(ranges) == 1 and "," in ranges[0]:
            ranges = ranges[0].split(",")
        for item in ranges:
            item = str(item).strip()
            if item.endswith("-"):
                self.ranges.append((int(item[:-1]), None))
            elif '-' in str(item):
                self.ranges.append(tuple(int(x) for x in item.split('-')))
            else:
                self.ints.append(int(item))

    def includes(self, other):
        """ Return True if ``other`` is included in this range.
        Functionally equivalent to ``other in range``, which should be
        used instead. """
        return other in self

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


def locked(fd):
    """ Acquire a lock on a file.

    :param fd: The file descriptor to lock
    :type fd: int
    :returns: bool - True if the file is already locked, False
              otherwise """
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return True
    return False


class ExecutorResult(object):
    """ Returned as the result of a call to
    :func:`Bcfg2.Utils.Executor.run`. The result can be accessed via
    the instance variables, documented below, as a boolean (which is
    equivalent to :attr:`Bcfg2.Utils.ExecutorResult.success`), or as a
    tuple, which, for backwards compatibility, is equivalent to
    ``(result.retval, result.stdout.splitlines())``."""

    def __init__(self, stdout, stderr, retval):
        #: The output of the command
        if isinstance(stdout, str):
            self.stdout = stdout
        else:
            self.stdout = stdout.decode('utf-8')

        #: The error produced by the command
        if isinstance(stdout, str):
            self.stderr = stderr
        else:
            self.stderr = stderr.decode('utf-8')

        #: The return value of the command.
        self.retval = retval

        #: Whether or not the command was successful.  If the
        #: ExecutorResult is used as a boolean, ``success`` is
        #: returned.
        self.success = retval == 0

        #: A friendly error message
        self.error = None
        if self.retval:
            if self.stderr:
                self.error = "%s (rv: %s)" % (self.stderr, self.retval)
            elif self.stdout:
                self.error = "%s (rv: %s)" % (self.stdout, self.retval)
            else:
                self.error = "No output or error; return value %s" % \
                    self.retval

    def __repr__(self):
        if self.error:
            return "Errored command result: %s" % self.error
        elif self.stdout:
            return "Successful command result: %s" % self.stdout
        else:
            return "Successful command result: No output"

    def __getitem__(self, idx):
        """ This provides compatibility with the old Executor, which
        returned a tuple of (return value, stdout split by lines). """
        return (self.retval, self.stdout.splitlines())[idx]

    def __len__(self):
        """ This provides compatibility with the old Executor, which
        returned a tuple of (return value, stdout split by lines). """
        return 2

    def __delitem__(self, _):
        raise TypeError("'%s' object doesn't support item deletion" %
                        self.__class__.__name__)

    def __setitem__(self, idx, val):
        raise TypeError("'%s' object does not support item assignment" %
                        self.__class__.__name__)

    def __nonzero__(self):
        return self.__bool__()

    def __bool__(self):
        return self.success


class Executor(object):
    """ A convenient way to run external commands with
    :class:`subprocess.Popen` """

    def __init__(self, timeout=None):
        """
        :param timeout: Set a default timeout for all commands run by
                        this Executor object
        :type timeout: float
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.timeout = timeout

    def _timeout(self, proc):
        """ A function suitable for passing to
        :class:`threading.Timer` that kills the given process.

        :param proc: The process to kill upon timeout.
        :type proc: subprocess.Popen
        :returns: None """
        if proc.poll() is None:
            try:
                proc.kill()
                self.logger.warning("Process exceeeded timeout, killing")
            except OSError:
                pass

    def run(self, command, inputdata=None, timeout=None, **kwargs):
        """ Run a command, given as a list, optionally giving it the
        specified input data.  All additional keyword arguments are
        passed through to :class:`subprocess.Popen`.

        :param command: The command to run, as a list (preferred) or
                        as a string.  See :class:`subprocess.Popen` for
                        details.
        :type command: list or string
        :param inputdata: Data to pass to the command on stdin
        :type inputdata: string
        :param timeout: Kill the command if it runs longer than this
                        many seconds.  Set to 0 or -1 to explicitly
                        override a default timeout.
        :type timeout: float
        :returns: :class:`Bcfg2.Utils.ExecutorResult`
        """
        shell = False
        if 'shell' in kwargs:
            shell = kwargs['shell']
        if isinstance(command, str):
            cmdstr = command
            if not shell:
                command = shlex.split(cmdstr)
        else:
            cmdstr = " ".join(command)
        self.logger.debug("Running: %s" % cmdstr)
        args = dict(shell=shell, bufsize=16384, close_fds=True)
        args.update(kwargs)
        args.update(stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
        proc = subprocess.Popen(command, **args)
        if timeout is None:
            timeout = self.timeout
        if timeout is not None:
            timer = threading.Timer(float(timeout), self._timeout, [proc])
            timer.start()
        try:
            if inputdata:
                for line in inputdata.splitlines():
                    self.logger.debug('> %s' % line)
            (stdout, stderr) = proc.communicate(input=inputdata)

            # py3k fixes
            if not isinstance(stdout, str):
                stdout = stdout.decode('utf-8')  # pylint: disable=E1103
            if not isinstance(stderr, str):
                stderr = stderr.decode('utf-8')  # pylint: disable=E1103

            for line in stdout.splitlines():  # pylint: disable=E1103
                self.logger.debug('< %s' % line)
            for line in stderr.splitlines():  # pylint: disable=E1103
                self.logger.info(line)
            return ExecutorResult(stdout, stderr,
                                  proc.wait())  # pylint: disable=E1101
        finally:
            if timeout is not None:
                timer.cancel()


def list2range(lst):
    ''' convert a list of integers to a set of human-readable ranges.  e.g.:

    [1, 2, 3, 6, 9, 10, 11] -> "[1-3,6,9-11]" '''
    ilst = sorted(int(i) for i in lst)
    ranges = []
    start = None
    last = None
    for i in ilst:
        if not last or i != last + 1:
            if start:
                if start == last:
                    ranges.append(str(start))
                else:
                    ranges.append("%d-%d" % (start, last))
            start = i
        last = i
    if start:
        if start == last:
            ranges.append(str(start))
        else:
            ranges.append("%d-%d" % (start, last))
    if not ranges:
        return ""
    elif len(ranges) > 1 or "-" in ranges[0]:
        return "[%s]" % ",".join(ranges)
    else:
        # only one range consisting of only a single number
        return ranges[0]


def hostnames2ranges(hostnames):
    ''' convert a list of hostnames to a set of human-readable ranges.  e.g.:

    ["foo1.example.com", "foo2.example.com", "foo3.example.com",
        "foo6.example.com"] -> ["foo[1-3,6].example.com"]'''
    hosts = {}
    hostre = re.compile(r'(\w+?)(\d+)(\..*)$')
    for host in hostnames:
        match = hostre.match(host)
        if match:
            key = (match.group(1), match.group(3))
            try:
                hosts[key].append(match.group(2))
            except KeyError:
                hosts[key] = [match.group(2)]

    ranges = []
    for name, nums in hosts.items():
        ranges.append(name[0] + list2range(nums) + name[1])
    return ranges


def safe_input(msg):
    """ input() that flushes the input buffer before accepting input """
    # flush input buffer
    while len(select.select([sys.stdin.fileno()], [], [], 0.0)[0]) > 0:
        os.read(sys.stdin.fileno(), 4096)
    return input(msg)


class classproperty(object):  # pylint: disable=C0103
    """ Decorator that can be used to create read-only class
    properties. """

    def __init__(self, getter):
        self.getter = getter

    def __get__(self, instance, owner):
        return self.getter(owner)
